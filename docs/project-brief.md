# VoxPaste Local Project Brief

## One-Liner

VoxPaste Local is a local-first macOS voice input layer that turns spoken drafts into paste-ready text. Hold a keyboard trigger or mouse side button to record, release to transcribe with local Whisper, clean the transcript, and paste it into the active cursor.

## Product Story

Native dictation is useful, but it mainly solves "speech to text." In daily desktop writing, the harder workflow is often "spoken draft to usable text": mixed Chinese-English terms, missing punctuation, filler words, app switching, and limited control over output style.

VoxPaste reframes voice input as a desktop productivity workflow:

```text
fast trigger
  -> local transcription
  -> audio pause segmentation + deterministic cleanup or optional local LLM polishing
  -> paste into the current app
```

The product bet is that frequent writers do not always need a full dictation app. They need a small, reliable input layer that works wherever the cursor is.

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
- Improved local Chinese speech cleanup for filler words, audio pause-aware punctuation, clause boundaries, questions, contrast, and common spoken connectors.
- Added formatting regression fixtures for real Chinese spoken-text failure cases.
- Added helper scripts to inspect keyboard and mouse trigger names recognized by the local `pynput` backend.
- Added lazy imports and a `--check` command that verifies core dependencies in child processes, reducing crash risk in unsupported MLX/Metal environments.

## Product Value

- Local-first: audio can stay on the user's machine.
- Low-friction: hold, speak, release, paste.
- Works across apps: the output lands in the current cursor instead of being locked inside one editor.
- Flexible output: users can choose raw transcription, local punctuation/filler cleanup, local LLM cleanup, or structured Markdown notes.
- Practical AI integration: the model is embedded into a real input workflow, not just called as a standalone demo.

## Key Product Decisions

- Focused on macOS Apple Silicon first instead of building a shallow cross-platform version.
- Used mouse side-button push-to-talk as a core interaction, not just a keyboard shortcut.
- Made local rule-based cleanup the default because simple punctuation and filler cleanup should be fast, predictable, and usable without an LLM.
- Added audio-level pause segmentation before full transcription, with Whisper word timestamps as a fallback punctuation signal.
- Added golden tests for spoken-text cleanup because punctuation quality is easy to regress.
- Kept local LLM support optional for semantic rewriting and higher-quality structure.
- Designed the tool to paste into existing apps instead of forcing users into a dedicated editor.

## Interview Narrative

```text
I did not want to build another generic dictation demo. I noticed that native dictation is good at basic speech-to-text, but the real pain in my writing workflow was mixed Chinese-English input, missing punctuation, filler words, and moving text across apps. So I built VoxPaste as a local voice-to-paste layer: hold a mouse side button, speak, release, transcribe locally with Whisper, clean the spoken draft, and paste it directly into the active cursor.

The most important product decision was not to use an LLM for everything. For everyday punctuation and filler-word cleanup, I use audio pause segmentation, Whisper timestamps, deterministic local rules, and regression tests first because they are faster, more predictable, and do not require LM Studio to be running. The LLM layer remains optional for deeper rewriting or structured notes.
```

## Resume Version

```text
VoxPaste Local | Local-first AI voice input utility for macOS
- Built a local macOS voice-input workflow: hold a keyboard key or mouse side button to record, release to transcribe with MLX Whisper, and automatically paste the result into the active cursor.
- Added output modes for raw transcripts, local rule-based speech cleanup, and structured Markdown notes, with optional local LLM support through LM Studio's OpenAI-compatible API.
- Improved Chinese speech cleanup with audio pause segmentation, Whisper word timestamps, deterministic post-processing rules, and regression fixtures for real spoken-text failure cases.
- Refactored a personal automation script into a public GitHub project with external configuration, environment checks, helper scripts, README documentation, and a standard open-source license.
```
