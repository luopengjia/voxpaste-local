#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "whisper_model": "mlx-community/whisper-large-v3-turbo",
    "lm_studio_url": "http://localhost:1234/v1",
    "llm_model": "local-model",
    "use_llm_polish": False,
    "sample_rate": 16000,
    "trigger_key": "alt_r",
    "trigger_mouse_button": "middle",
    "language": "zh",
    "hold_threshold_sec": 0.3,
    "paste_delay_sec": 0.1,
}

POLISH_PROMPT = (
    "You are a speech cleanup assistant. Rewrite spoken text into clean written "
    "language, keep all meaning, add line breaks when helpful, and output only "
    "the final text."
)


def log(message: str) -> None:
    print(message, flush=True)


def load_config(path: Path) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            user_config = json.load(file)
        if not isinstance(user_config, dict):
            raise ValueError(f"{path} must contain a JSON object")
        config.update(user_config)
    return config


def write_default_config(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    with path.open("w", encoding="utf-8") as file:
        json.dump(DEFAULT_CONFIG, file, ensure_ascii=False, indent=2)
        file.write("\n")


def check_import(module_name: str) -> tuple[bool, str]:
    code = f"import {module_name}; print('ok')"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode == 0:
        return True, "ok"
    detail = (result.stderr or result.stdout).strip().splitlines()
    return False, detail[-1] if detail else f"exit code {result.returncode}"


def check_lm_studio(url: str) -> tuple[bool, str]:
    endpoint = url.rstrip("/") + "/models"
    request = urllib.request.Request(endpoint, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.URLError as error:
        return False, str(error.reason)
    except Exception as error:
        return False, str(error)


def run_checks(config: dict[str, Any]) -> int:
    log("VoxPaste Local environment check")
    log(f"Python: {sys.version.split()[0]}")
    log(f"Platform: {platform.system()} {platform.machine()}")

    expected = platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}
    log(f"Apple Silicon macOS: {'ok' if expected else 'not detected'}")

    modules = ["numpy", "sounddevice", "pyperclip", "pynput", "openai"]
    failed = False
    for module_name in modules:
        ok, detail = check_import(module_name)
        failed = failed or not ok
        log(f"{module_name}: {'ok' if ok else 'failed'} ({detail})")

    ok, detail = check_import("mlx_whisper")
    failed = failed or not ok
    log(f"mlx_whisper: {'ok' if ok else 'failed'} ({detail})")

    if config.get("use_llm_polish"):
        ok, detail = check_lm_studio(str(config["lm_studio_url"]))
        failed = failed or not ok
        log(f"LM Studio: {'ok' if ok else 'unreachable'} ({detail})")
    else:
        log("LM Studio: skipped (use_llm_polish=false)")

    return 1 if failed else 0


class Recorder:
    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate
        self.recording = False
        self.frames: list[Any] = []
        self.thread: threading.Thread | None = None
        self.error: Exception | None = None

    def start(self) -> None:
        import sounddevice as sd

        self.recording = True
        self.frames = []
        self.error = None
        log("Recording... release the trigger to transcribe.")

        def record_loop() -> None:
            try:
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                ) as stream:
                    while self.recording:
                        data, _ = stream.read(1024)
                        self.frames.append(data.copy())
            except Exception as error:
                self.error = error
                self.recording = False

        self.thread = threading.Thread(target=record_loop, daemon=True)
        self.thread.start()

    def stop(self):
        import numpy as np

        self.recording = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.error is not None:
            raise RuntimeError(f"recording failed: {self.error}") from self.error
        if not self.frames:
            return None
        audio = np.concatenate(self.frames, axis=0).flatten()
        if len(audio) < self.sample_rate * 0.5:
            return None
        return audio


class VoxPasteApp:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.recorder = Recorder(int(config["sample_rate"]))
        self.processing = False
        self.mouse_held = False
        self.llm_client = None

    def start_recording(self) -> None:
        if self.recorder.recording or self.processing:
            return
        self.recorder.start()

    def process_recording(self) -> None:
        if self.processing:
            return
        self.processing = True
        try:
            audio = self.recorder.stop()
            if audio is None:
                log("Recording too short or empty; skipped.")
                return
            text = self.transcribe(audio)
            if not text:
                log("Transcript is empty; skipped.")
                return
            final_text = self.polish(text)
            self.paste(final_text)
        except Exception as error:
            log(f"Error: {error}")
        finally:
            self.processing = False

    def transcribe(self, audio: Any) -> str:
        import mlx_whisper

        log("Transcribing with Whisper...")
        kwargs: dict[str, Any] = {
            "path_or_hf_repo": self.config["whisper_model"],
            "verbose": False,
        }
        if self.config.get("language"):
            kwargs["language"] = self.config["language"]
        result = mlx_whisper.transcribe(audio, **kwargs)
        text = str(result.get("text", "")).strip()
        log(f"Transcript: {text}")
        return text

    def polish(self, text: str) -> str:
        if not self.config.get("use_llm_polish") or len(text) < 5:
            return text

        from openai import OpenAI

        if self.llm_client is None:
            self.llm_client = OpenAI(
                base_url=self.config["lm_studio_url"],
                api_key="lm-studio",
            )
        log("Polishing with local LLM...")
        try:
            response = self.llm_client.chat.completions.create(
                model=self.config["llm_model"],
                messages=[
                    {"role": "system", "content": POLISH_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            content = response.choices[0].message.content or ""
            return content.strip() or text
        except Exception as error:
            log(f"LLM polish failed; using raw transcript. Detail: {error}")
            return text

    def paste(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)
        time.sleep(float(self.config["paste_delay_sec"]))
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        log("Pasted to cursor.")

    def run(self) -> None:
        from pynput import keyboard, mouse

        trigger_key = parse_keyboard_key(keyboard, self.config.get("trigger_key"))
        trigger_mouse = parse_mouse_button(mouse, self.config.get("trigger_mouse_button"))

        def on_press(key: Any) -> None:
            if trigger_key is not None and key == trigger_key:
                self.start_recording()

        def on_release(key: Any) -> None:
            if trigger_key is not None and key == trigger_key and self.recorder.recording:
                threading.Thread(target=self.process_recording, daemon=True).start()

        def on_mouse_click(x: int, y: int, button: Any, pressed: bool) -> None:
            if trigger_mouse is None or button != trigger_mouse:
                return
            if pressed and not self.recorder.recording and not self.processing:
                self.mouse_held = True

                def check_hold() -> None:
                    time.sleep(float(self.config["hold_threshold_sec"]))
                    if self.mouse_held:
                        self.start_recording()

                threading.Thread(target=check_hold, daemon=True).start()
            elif not pressed:
                self.mouse_held = False
                if self.recorder.recording:
                    threading.Thread(target=self.process_recording, daemon=True).start()

        log("VoxPaste Local is running.")
        log(f"Keyboard trigger: {self.config.get('trigger_key') or 'disabled'}")
        log(f"Mouse trigger: {self.config.get('trigger_mouse_button') or 'disabled'}")
        log("Press Ctrl+C to quit.")

        mouse_listener = mouse.Listener(on_click=on_mouse_click)
        mouse_listener.daemon = True
        mouse_listener.start()
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                log("Quit.")
            finally:
                mouse_listener.stop()


def parse_keyboard_key(keyboard_module: Any, value: Any) -> Any:
    if value in {None, "", False}:
        return None
    name = str(value).lower()
    if hasattr(keyboard_module.Key, name):
        return getattr(keyboard_module.Key, name)
    if len(name) == 1:
        return keyboard_module.KeyCode.from_char(name)
    raise ValueError(f"unknown keyboard trigger: {value}")


def parse_mouse_button(mouse_module: Any, value: Any) -> Any:
    if value in {None, "", False}:
        return None
    name = str(value).lower()
    if hasattr(mouse_module.Button, name):
        return getattr(mouse_module.Button, name)
    raise ValueError(f"unknown mouse trigger: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local voice-to-paste tool for macOS.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.local.json"),
        help="Path to local JSON config. Defaults to ./config.local.json",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create a config file with default values and exit.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check platform, Python dependencies, and optional LM Studio endpoint.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the resolved config and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.init_config:
        write_default_config(args.config)
        log(f"Created {args.config}")
        return 0

    config = load_config(args.config)

    if args.print_config:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    if args.check:
        return run_checks(config)

    VoxPasteApp(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
