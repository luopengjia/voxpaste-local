#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import re
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
    "use_local_llm": False,
    "output_mode": "polished",
    "structured_template": "summary_action_items",
    "use_audio_pause_segmentation": True,
    "use_word_timestamps": True,
    "pause_comma_sec": 0.45,
    "pause_period_sec": 0.85,
    "pause_min_chunk_sec": 0.45,
    "pause_max_segments": 8,
    "sample_rate": 16000,
    "trigger_key": "alt_r",
    "trigger_mouse_button": "side",
    "language": "zh",
    "hold_threshold_sec": 0.3,
    "paste_delay_sec": 0.1,
}

POLISH_PROMPT = (
    "You are a speech cleanup assistant. Rewrite spoken text into clean written "
    "language, keep all meaning, add line breaks when helpful, and output only "
    "the final text."
)

STRUCTURED_PROMPTS = {
    "summary_action_items": (
        "Turn the transcribed speech into concise Markdown with exactly these "
        "sections: Summary, Key Points, Action Items. Do not invent facts. If a "
        "section has no clear content, write '- None'. Output only Markdown."
    ),
    "meeting_notes": (
        "Turn the transcribed speech into concise meeting notes in Markdown with "
        "exactly these sections: Summary, Discussion Notes, Decisions, Action "
        "Items. Do not invent facts. If a section has no clear content, write "
        "'- None'. Output only Markdown."
    ),
    "jd_analysis": (
        "Turn the transcribed speech or pasted job description into concise "
        "Markdown with exactly these sections: Role Summary, Requirements, "
        "Signals To Highlight, Questions To Clarify. Do not invent facts. If a "
        "section has no clear content, write '- None'. Output only Markdown."
    ),
}

VALID_OUTPUT_MODES = {"raw", "polished", "structured"}


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


def validate_config(config: dict[str, Any]) -> None:
    output_mode = str(config.get("output_mode", "")).lower()
    if output_mode not in VALID_OUTPUT_MODES:
        valid = ", ".join(sorted(VALID_OUTPUT_MODES))
        raise ValueError(f"output_mode must be one of: {valid}")

    structured_template = str(config.get("structured_template", "")).lower()
    if structured_template not in STRUCTURED_PROMPTS:
        valid = ", ".join(sorted(STRUCTURED_PROMPTS))
        raise ValueError(f"structured_template must be one of: {valid}")


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


def uses_local_llm(config: dict[str, Any]) -> bool:
    return bool(config.get("use_local_llm") or config.get("use_llm_polish"))


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

    if uses_local_llm(config):
        ok, detail = check_lm_studio(str(config["lm_studio_url"]))
        failed = failed or not ok
        log(f"LM Studio: {'ok' if ok else 'unreachable'} ({detail})")
    else:
        log("LM Studio: skipped (use_local_llm=false)")

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
            final_text = self.format_output(text)
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
            "word_timestamps": bool(self.config.get("use_word_timestamps", True)),
        }
        if self.config.get("language"):
            kwargs["language"] = self.config["language"]
        if self.config.get("use_audio_pause_segmentation", True):
            segmented_text = transcribe_audio_pause_segments(
                mlx_whisper,
                audio,
                kwargs,
                int(self.config["sample_rate"]),
                float(self.config.get("pause_comma_sec", 0.45)),
                float(self.config.get("pause_period_sec", 0.85)),
                float(self.config.get("pause_min_chunk_sec", 0.45)),
                int(self.config.get("pause_max_segments", 8)),
            )
            if segmented_text:
                log("Transcript strategy: audio pause segmentation")
                log(f"Transcript: {segmented_text}")
                return segmented_text

        result = mlx_whisper.transcribe(audio, **kwargs)
        text = str(result.get("text", "")).strip()
        if self.config.get("use_word_timestamps", True):
            text = add_pause_punctuation_from_segments(
                result,
                text,
                float(self.config.get("pause_comma_sec", 0.45)),
                float(self.config.get("pause_period_sec", 0.85)),
            )
            log("Transcript strategy: word timestamps")
        else:
            log("Transcript strategy: full audio")
        log(f"Transcript: {text}")
        return text

    def format_output(self, text: str) -> str:
        mode = str(self.config.get("output_mode", "polished")).lower()
        if mode == "raw":
            return text
        if mode == "polished":
            return self.polish_with_llm(text)
        if mode == "structured":
            return self.structure(text)
        raise ValueError(f"unknown output_mode: {mode}")

    def polish_with_llm(self, text: str) -> str:
        language = self.config.get("language")
        if not uses_local_llm(self.config) or len(text) < 5:
            return clean_speech_without_llm(text, language)
        return self.try_local_llm(POLISH_PROMPT, text, "LLM polish") or clean_speech_without_llm(text, language)

    def structure(self, text: str) -> str:
        template = str(self.config.get("structured_template", "summary_action_items")).lower()
        if uses_local_llm(self.config) and len(text) >= 5:
            prompt = STRUCTURED_PROMPTS[template]
            structured_text = self.try_local_llm(prompt, text, "LLM structure")
            if structured_text:
                return structured_text
        log("Structuring without LLM; using rule-based Markdown fallback.")
        return structure_without_llm(text, template)

    def try_local_llm(self, system_prompt: str, text: str, task_name: str) -> str | None:
        from openai import OpenAI

        if self.llm_client is None:
            self.llm_client = OpenAI(
                base_url=self.config["lm_studio_url"],
                api_key="lm-studio",
            )
        log(f"{task_name} with local LLM...")
        try:
            response = self.llm_client.chat.completions.create(
                model=self.config["llm_model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
                max_tokens=900,
            )
            content = response.choices[0].message.content or ""
            return content.strip() or None
        except Exception as error:
            log(f"{task_name} failed; using fallback. Detail: {error}")
            return None

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

    alias_groups = {
        "side": ("x1", "unknown", "middle"),
        "side1": ("x1", "unknown", "middle"),
        "back": ("x1", "unknown", "middle"),
        "mouse4": ("x1", "unknown", "middle"),
        "side2": ("x2", "unknown", "middle"),
        "forward": ("x2", "unknown", "middle"),
        "mouse5": ("x2", "unknown", "middle"),
    }
    for candidate in alias_groups.get(name, ()):
        if hasattr(mouse_module.Button, candidate):
            return getattr(mouse_module.Button, candidate)
    raise ValueError(f"unknown mouse trigger: {value}")


def structure_without_llm(text: str, template: str) -> str:
    cleaned = clean_speech_without_llm(text)
    sentences = split_sentences(cleaned)
    key_points = sentences[:6] or [cleaned]
    action_items = find_action_items(sentences)

    if template == "meeting_notes":
        sections = [
            ("Summary", [cleaned]),
            ("Discussion Notes", key_points),
            ("Decisions", ["None"]),
            ("Action Items", action_items or ["None"]),
        ]
    elif template == "jd_analysis":
        sections = [
            ("Role Summary", [cleaned]),
            ("Requirements", key_points),
            ("Signals To Highlight", ["None"]),
            ("Questions To Clarify", ["None"]),
        ]
    else:
        sections = [
            ("Summary", [cleaned]),
            ("Key Points", key_points),
            ("Action Items", action_items or ["None"]),
        ]

    return "\n\n".join(format_markdown_section(title, items) for title, items in sections)


def transcribe_audio_pause_segments(
    mlx_whisper_module: Any,
    audio: Any,
    base_kwargs: dict[str, Any],
    sample_rate: int,
    comma_sec: float,
    period_sec: float,
    min_chunk_sec: float,
    max_segments: int,
) -> str | None:
    intervals = detect_speech_intervals(audio, sample_rate, comma_sec, min_chunk_sec)
    if len(intervals) < 2 or len(intervals) > max_segments:
        return None

    parts: list[str] = []
    previous_end: int | None = None
    chunk_kwargs = base_kwargs.copy()
    chunk_kwargs["word_timestamps"] = False

    for start, end in intervals:
        chunk = audio[start:end]
        if len(chunk) < sample_rate * min_chunk_sec:
            continue

        result = mlx_whisper_module.transcribe(chunk, **chunk_kwargs)
        chunk_text = str(result.get("text", "")).strip()
        if not chunk_text:
            continue

        if parts and previous_end is not None:
            gap = (start - previous_end) / sample_rate
            mark = "。" if gap >= period_sec else "，"
            append_boundary_mark(parts, mark)

        parts.append(chunk_text)
        previous_end = end

    if len(parts) < 2:
        return None

    return normalize_timestamp_text("".join(parts))


def detect_speech_intervals(
    audio: Any,
    sample_rate: int,
    split_pause_sec: float,
    min_chunk_sec: float,
) -> list[tuple[int, int]]:
    import numpy as np

    waveform = np.asarray(audio, dtype="float32").flatten()
    if waveform.size < sample_rate * min_chunk_sec:
        return []

    frame_size = max(1, int(sample_rate * 0.03))
    frame_count = waveform.size // frame_size
    if frame_count < 3:
        return []

    trimmed = waveform[: frame_count * frame_size]
    frames = trimmed.reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    if float(np.max(rms)) < 1e-4:
        return []

    noise_floor = float(np.percentile(rms, 20))
    active_level = float(np.percentile(rms, 90))
    threshold = max(0.006, noise_floor * 2.5, active_level * 0.08)
    speech = rms > threshold
    speech = smooth_speech_mask(speech, max(1, int(0.09 / 0.03)))

    raw_intervals: list[tuple[int, int]] = []
    start_frame: int | None = None
    for index, is_speech in enumerate(speech):
        if is_speech and start_frame is None:
            start_frame = index
        elif not is_speech and start_frame is not None:
            raw_intervals.append((start_frame * frame_size, index * frame_size))
            start_frame = None
    if start_frame is not None:
        raw_intervals.append((start_frame * frame_size, frame_count * frame_size))

    if not raw_intervals:
        return []

    speech_intervals = [
        (start, end)
        for start, end in raw_intervals
        if end - start >= sample_rate * 0.12
    ]
    merged = merge_and_filter_intervals(
        speech_intervals,
        sample_rate,
        split_pause_sec,
        min_chunk_sec,
    )
    pad = int(sample_rate * 0.04)
    return [(max(0, start - pad), min(waveform.size, end + pad)) for start, end in merged]


def smooth_speech_mask(mask: Any, max_gap_frames: int) -> Any:
    import numpy as np

    smoothed = np.asarray(mask, dtype=bool).copy()
    last_speech: int | None = None
    gap_start: int | None = None
    for index, value in enumerate(smoothed):
        if value:
            if last_speech is not None and gap_start is not None:
                gap = index - gap_start
                if gap <= max_gap_frames:
                    smoothed[gap_start:index] = True
            last_speech = index
            gap_start = None
        elif last_speech is not None and gap_start is None:
            gap_start = index
    return smoothed


def merge_and_filter_intervals(
    intervals: list[tuple[int, int]],
    sample_rate: int,
    split_pause_sec: float,
    min_chunk_sec: float,
) -> list[tuple[int, int]]:
    if not intervals:
        return []

    merged: list[tuple[int, int]] = [intervals[0]]
    for start, end in intervals[1:]:
        previous_start, previous_end = merged[-1]
        gap = (start - previous_end) / sample_rate
        if gap < split_pause_sec:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))

    min_samples = int(sample_rate * min_chunk_sec)
    return [(start, end) for start, end in merged if end - start >= min_samples]


def append_boundary_mark(parts: list[str], mark: str) -> None:
    if not parts:
        return
    text = parts[-1].rstrip()
    if not text:
        return
    if text[-1] in "？！!?":
        parts[-1] = text
        return
    parts[-1] = text.rstrip("，。；：,.!?;:") + mark


def add_pause_punctuation_from_segments(
    result: dict[str, Any],
    fallback_text: str,
    comma_sec: float,
    period_sec: float,
) -> str:
    words = extract_timestamp_words(result)
    if len(words) < 2:
        return fallback_text

    pieces: list[str] = []
    for index, word in enumerate(words):
        text = str(word.get("word", ""))
        if not text.strip():
            continue
        pieces.append(text)

        if index >= len(words) - 1:
            continue
        end = safe_float(word.get("end"))
        next_start = safe_float(words[index + 1].get("start"))
        if end is None or next_start is None:
            continue

        gap = next_start - end
        if gap >= period_sec:
            append_pause_mark(pieces, "。")
        elif gap >= comma_sec:
            append_pause_mark(pieces, "，")

    rebuilt = normalize_timestamp_text("".join(pieces))
    if not rebuilt:
        return fallback_text
    if too_different_from_fallback(rebuilt, fallback_text):
        return fallback_text
    return rebuilt


def extract_timestamp_words(result: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in result.get("segments", []) or []:
        if not isinstance(segment, dict):
            continue
        for word in segment.get("words", []) or []:
            if isinstance(word, dict):
                words.append(word)
    return words


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def append_pause_mark(pieces: list[str], mark: str) -> None:
    while pieces and not pieces[-1]:
        pieces.pop()
    if not pieces:
        return
    pieces[-1] = pieces[-1].rstrip()
    if not pieces[-1] or pieces[-1][-1] in "，。！？；：,.!?;:":
        return
    pieces.append(mark)


def normalize_timestamp_text(text: str) -> str:
    text = re.sub(r"\s*([，。！？；：,.!?;:])\s*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", text)
    text = re.sub(r"\s*([，。！？；：])\s*", r"\1", text)
    return text


def too_different_from_fallback(rebuilt: str, fallback: str) -> bool:
    rebuilt_plain = re.sub(r"[\s，。！？；：,.!?;:]", "", rebuilt)
    fallback_plain = re.sub(r"[\s，。！？；：,.!?;:]", "", fallback)
    if not fallback_plain:
        return False
    lower_bound = len(fallback_plain) * 0.55
    upper_bound = len(fallback_plain) * 1.45
    return not (lower_bound <= len(rebuilt_plain) <= upper_bound)


def clean_speech_without_llm(text: str, language: Any = None) -> str:
    cleaned = normalize_spaces(text)
    if not cleaned:
        return cleaned

    if is_chinese_text(cleaned, language):
        cleaned = clean_chinese_speech(cleaned)
    else:
        cleaned = clean_english_speech(cleaned)
    return cleaned.strip()


def normalize_spaces(text: str) -> str:
    text = text.replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_chinese_text(text: str, language: Any = None) -> bool:
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    if not chinese_chars:
        return False
    if str(language).lower().startswith("zh"):
        return True
    return len(chinese_chars) >= max(2, len(text) // 5)


def clean_chinese_speech(text: str) -> str:
    text = normalize_chinese_punctuation(text)
    text = remove_chinese_fillers(text)
    text = normalize_chinese_speech_markers(text)
    text = add_chinese_phrase_commas(text)
    text = add_chinese_clause_commas(text)
    text = add_chinese_question_marks(text)
    text = add_chinese_sentence_breaks(text)
    text = re.sub(r"[，,]\s*[，,]+", "，", text)
    text = re.sub(r"\s*([，。！？；：])\s*", r"\1", text)
    text = re.sub(r"([。！？；：])，", r"\1", text)
    text = re.sub(r"：，", "：", text)
    text = re.sub(r"(所以)，(我想|我觉得|我认为|我们需要)", r"\1\2", text)
    if text and text[-1] not in "。！？；：":
        text += "。"
    return text


def normalize_chinese_punctuation(text: str) -> str:
    replacements = {
        ",": "，",
        ".": "。",
        "?": "？",
        "!": "！",
        ";": "；",
        ":": "：",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def remove_chinese_fillers(text: str) -> str:
    boundary = r"(^|[，。！？；：\s])"
    fillers = (
        r"怎么说呢",
        r"就是说",
        r"嗯+",
        r"呃+",
        r"额+",
        r"就是",
    )
    filler_group = "|".join(fillers)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(rf"{boundary}(?:那个|这个)(?=就是|嗯|呃|额)", r"\1", text)
        text = re.sub(rf"{boundary}(?:{filler_group})(?:[，\s]*)", r"\1", text)
    text = re.sub(r"(然后)(?:，?然后)+", r"\1", text)
    text = re.sub(
        r"(?<=[\u4e00-\u9fff])的话(?=[，。！？；：]|$|第[一二三四五六七八九十]|首先|其次|最后|下一步|接下来)",
        "",
        text,
    )
    text = re.sub(r"(，)?(对吧|你知道吧|是不是|啊|呀|吧|呢)([。！？；：]|$)", r"\3", text)
    return text.strip("， ")


def normalize_chinese_speech_markers(text: str) -> str:
    text = re.sub(r"然后，?(?:我觉得|我感觉)?，?(下一步|接下来)", r"\1", text)
    text = re.sub(r"然后，?(下一步|接下来)", r"\1", text)
    text = re.sub(r"然后，?(第一|第二|第三|第四|第五)", r"\1", text)
    text = re.sub(r"(我觉得|我感觉)，?(下一步|接下来)", r"\2", text)
    text = re.sub(r"(?<![\u4e00-\u9fff])(其实|大概)(?=[\u4e00-\u9fff])", "", text)
    return text


def add_chinese_phrase_commas(text: str) -> str:
    markers = (
        "但是",
        "所以",
        "因为",
        "另外",
        "然后",
        "不过",
        "而且",
        "首先",
        "其次",
        "最后",
        "同时",
        "实际上",
        "其实",
        "比如",
        "比如说",
        "以及",
        "还有",
        "包括",
        "尤其是",
        "特别是",
        "如果",
        "虽然",
        "只要",
        "并且",
        "或者",
        "我觉得",
        "我认为",
        "我感觉",
        "我想",
        "我们需要",
        "第一",
        "第二",
        "第三",
        "第四",
        "第五",
    )
    for marker in markers:
        text = re.sub(rf"(?<!^)(?<![，。！？；：\n])({marker})", rf"，\1", text)
    return text


def add_chinese_clause_commas(text: str) -> str:
    temporal_suffixes = (
        "之后",
        "以后",
        "之前",
        "的时候",
        "过程中",
        "过程里",
    )
    suffix_group = "|".join(temporal_suffixes)
    text = re.sub(
        rf"(?<![，。！？；：\n])({suffix_group})(?=[\u4e00-\u9fff])",
        r"\1，",
        text,
    )

    # Speech transcripts often miss subject shifts, e.g. "没有标点用户看起来就很累".
    subject_transitions = (
        "用户",
        "体验",
        "效果",
        "精度",
        "速度",
        "成本",
    )
    subject_group = "|".join(subject_transitions)
    predicate_start = r"(?:会|就|是|要|可以|需要|应该|看起来)"
    text = re.sub(
        rf"([^，。！？；：\n]{{4,}})({subject_group})(?={predicate_start})",
        r"\1，\2",
        text,
    )
    text = re.sub(r"(?<!^)(?<![，。！？；：\n])现在(?=这(?:句|段|个|种|些))", "，现在", text)
    return text


def add_chinese_question_marks(text: str) -> str:
    question_words = (
        "怎么",
        "为什么",
        "为何",
        "什么",
        "是否",
        "能不能",
        "可不可以",
        "是不是",
        "多少",
        "哪里",
        "哪一个",
        "哪种",
        "吗",
    )
    question_group = "|".join(question_words)
    follow_up_markers = (
        "因为",
        "但是",
        "不过",
        "所以",
        "然后",
        "另外",
        "现在",
        "刚才",
        "这句话",
        "我想",
        "我需要",
        "我希望",
        "我觉得",
        "我认为",
        "下一步",
        "接下来",
    )
    follow_up_group = "|".join(follow_up_markers)
    text = re.sub(
        rf"([^。！？；：\n]{{0,50}}(?:{question_group})[^。！？；：\n]{{0,30}})，({follow_up_group})",
        r"\1？\2",
        text,
    )
    return text


def add_chinese_sentence_breaks(text: str) -> str:
    list_intro = r"((?:一|二|两|三|四|五|\d+)(?:个|件)?(?:问题|事情|事|部分|点|方向|任务|步骤|原因|目标))"
    text = re.sub(rf"{list_intro}，?(第一)", r"\1：\2", text)

    contrast_subjects = (
        "你却",
        "我却",
        "他却",
        "她却",
        "它却",
        "我们却",
        "他们却",
    )
    contrast_group = "|".join(contrast_subjects)
    text = re.sub(rf"(?<!^)(?<![。！？；：\n])，?({contrast_group})", rf"。\1", text)

    end_markers = ("下一步", "接下来", "最后")
    for marker in end_markers:
        text = re.sub(rf"(?<!^)(?<![。！？；：\n])，?({marker})", rf"。\1", text)
    return text


def clean_english_speech(text: str) -> str:
    text = re.sub(r"\b(um+|uh+|er+|ah+)\b[, ]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(you know|i mean|sort of|kind of)\b[, ]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text:
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".!?;:":
        text += "."
    return text


def split_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return []

    sentences: list[str] = []
    current: list[str] = []
    for char in cleaned:
        current.append(char)
        if char in ".!?;。！？；":
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []

    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences


def find_action_items(sentences: list[str]) -> list[str]:
    markers = (
        "need to",
        "should",
        "todo",
        "to do",
        "follow up",
        "next",
        "must",
        "remember to",
        "需要",
        "要做",
        "要完成",
        "应该",
        "待办",
        "下一步",
        "记得",
        "必须",
    )
    action_items = []
    for sentence in sentences:
        normalized = sentence.lower()
        if any(marker in normalized for marker in markers):
            action_items.append(sentence)
    return action_items[:8]


def format_markdown_section(title: str, items: list[str]) -> str:
    safe_items = [item.strip() for item in items if item.strip()]
    if not safe_items:
        safe_items = ["None"]
    bullets = "\n".join(f"- {item}" for item in safe_items)
    return f"## {title}\n{bullets}"


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
    parser.add_argument(
        "--format-text",
        help="Format provided text according to output_mode and print it without recording or pasting.",
    )
    parser.add_argument(
        "--output-mode",
        choices=sorted(VALID_OUTPUT_MODES),
        help="Override config output_mode for this run.",
    )
    parser.add_argument(
        "--structured-template",
        choices=sorted(STRUCTURED_PROMPTS),
        help="Override config structured_template for this run.",
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
    if args.output_mode:
        config["output_mode"] = args.output_mode
    if args.structured_template:
        config["structured_template"] = args.structured_template
    validate_config(config)

    if args.print_config:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    if args.check:
        return run_checks(config)

    if args.format_text is not None:
        print(VoxPasteApp(config).format_output(args.format_text))
        return 0

    VoxPasteApp(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
