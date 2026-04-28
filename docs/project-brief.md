# VoxPaste Local Project Brief

## One-Liner

VoxPaste Local is a local-first macOS voice input utility. Hold a keyboard trigger or mouse side button to record, release to transcribe with local Whisper, optionally polish with a local LLM, and paste the result into the active cursor.

## Target Users

This project is built for people who write frequently across chat apps, browsers, note-taking tools, and editors, especially users who want faster long-form input without sending raw audio to a cloud API.

## Core Workflow

```text
hold trigger key / mouse side button
  -> record microphone audio
  -> transcribe locally with MLX Whisper
  -> optionally polish with a local LM Studio model
  -> copy text to clipboard
  -> simulate Cmd+V into the active app
```

## Technical Stack

- Python
- `mlx-whisper`
- `sounddevice`
- `pynput`
- `pyperclip`
- LM Studio OpenAI-compatible API
- macOS AppleScript paste automation

## What I Built

- Designed a complete local voice-input loop from recording to transcription, optional polishing, clipboard update, and paste automation.
- Refactored a personal script into a public GitHub project with external configuration, a README, license, `.gitignore`, and environment checks.
- Implemented hold-to-record triggers for both keyboard keys and mouse buttons, including side-button aliases such as `side`, `mouse4`, and `mouse5`.
- Added optional output modes for raw transcripts, local rule-based speech cleanup, and structured Markdown.
- Added helper scripts to inspect keyboard and mouse trigger names recognized by the local `pynput` backend.
- Added lazy imports and a `--check` command that verifies core dependencies in child processes, reducing crash risk in unsupported MLX/Metal environments.

## Product Value

- Local-first: audio can stay on the user's machine.
- Low-friction: hold, speak, release, paste.
- Works across apps: the output lands in the current cursor instead of being locked inside one editor.
- Flexible output: users can choose raw transcription, local punctuation/filler cleanup, local LLM cleanup, or structured Markdown notes.
- Practical AI integration: the model is embedded into a real input workflow, not just called as a standalone demo.

## Resume Version

```text
VoxPaste Local | Local-first AI voice input utility for macOS
- Built a local macOS voice-input workflow: hold a keyboard key or mouse side button to record, release to transcribe with MLX Whisper, and automatically paste the result into the active cursor.
- Added optional output modes for raw transcripts, local rule-based speech cleanup, and structured Markdown notes, with optional local LLM support through LM Studio's OpenAI-compatible API.
- Refactored a personal automation script into a public GitHub project with external configuration, environment checks, helper scripts, README documentation, and a standard open-source license.
```
