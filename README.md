# VoxPaste Local

VoxPaste Local is a local-first macOS voice input utility:

```text
hold a trigger key/button -> record speech -> Whisper transcription -> optional local LLM cleanup -> paste into the active cursor
```

It is designed for people who write a lot in chat tools, notes, browsers, and editors, and want fast voice input without sending audio to a cloud API.

## What It Does

- Records while you hold a keyboard key or mouse side button.
- Transcribes audio with `mlx-whisper` on Apple Silicon.
- Optionally cleans spoken text with a local LM Studio model.
- Copies the final text to the clipboard and pastes it into the current cursor.
- Keeps configuration in `config.local.json`, so the script can stay clean.

## Platform

VoxPaste Local is intentionally narrow:

- macOS
- Apple Silicon
- Python 3.9+
- Microphone permission for your terminal app
- Accessibility permission for your terminal app

The Whisper backend uses MLX, so this is not a general Windows/Linux voice input tool.

## Install

```bash
cd voxpaste-local

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `sounddevice` cannot find PortAudio:

```bash
brew install portaudio
pip install -r requirements.txt
```

## Configure

Create a local config:

```bash
python voxpaste.py --init-config
```

This creates `config.local.json`, which is ignored by Git. You can also start from `config.example.json`.

Common options:

| Field | Meaning | Default |
| --- | --- | --- |
| `whisper_model` | MLX Whisper model or local path | `mlx-community/whisper-large-v3-turbo` |
| `trigger_key` | Keyboard trigger, such as `alt_r`, `f5`, or `f12` | `alt_r` |
| `trigger_mouse_button` | Mouse trigger. Supports `side`, `back`, `forward`, `mouse4`, `mouse5`, `middle`, `unknown`, `x1`, `x2` | `side` |
| `language` | Whisper language hint; use `null` for auto-detect | `zh` |
| `use_llm_polish` | Whether to call LM Studio for text cleanup | `false` |
| `lm_studio_url` | LM Studio OpenAI-compatible endpoint | `http://localhost:1234/v1` |
| `llm_model` | Model name loaded in LM Studio | `local-model` |

## Permissions

Open macOS System Settings and grant your terminal app:

- Privacy & Security -> Microphone
- Privacy & Security -> Accessibility

Accessibility is required because VoxPaste simulates `Cmd+V` after copying the transcript.

## Check Environment

Run:

```bash
python voxpaste.py --check
```

This checks the platform, imports core dependencies in child processes, and checks LM Studio only when `use_llm_polish` is enabled.

## Run

```bash
python voxpaste.py
```

Then:

1. Hold the trigger key or mouse side button.
2. Speak.
3. Release.
4. The transcript is pasted into the current cursor.

## Helper Scripts

Use these when choosing a trigger:

```bash
python scripts/detect_key.py
python scripts/detect_mouse.py
```

They print the `pynput` key/button names recognized by your machine. On macOS, some side buttons are reported as `unknown` or `middle`; the default `side` alias maps to the best available side-button representation for the current `pynput` backend.

## Why This Project Exists

Most voice input workflows either depend on cloud services or are too heavy for quick everyday writing. This project explores a smaller local workflow: local transcription, optional local text cleanup, and direct paste into any app.

The core product idea is not "another dictation app"; it is a low-friction input layer for people who already live inside editors, browsers, chat tools, and note apps.

## Limitations

- First Whisper run may download the model and take time.
- MLX/Metal can fail in unsupported or headless environments.
- Paste automation depends on macOS Accessibility permissions.
- LM Studio cleanup is optional and only works when LM Studio is running with a loaded model.
- The script is a local utility, not a signed macOS app.

## Project Structure

```text
.
├── voxpaste.py              # main utility
├── config.example.json      # public config template
├── requirements.txt         # runtime dependencies
├── scripts/
│   ├── detect_key.py        # inspect keyboard trigger names
│   └── detect_mouse.py      # inspect mouse trigger names
└── README.md
```

For a Chinese portfolio summary, see [docs/project-brief.zh-CN.md](docs/project-brief.zh-CN.md).

## License

MIT
