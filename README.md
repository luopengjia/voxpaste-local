# VoxPaste Local

VoxPaste Local is a local-first macOS voice input layer for fast writing:

```text
hold a trigger key/button -> record speech -> Whisper transcription -> optional local LLM cleanup -> paste into the active cursor
```

It is designed for people who write across chat apps, notes, browsers, and editors, and want a more controllable alternative to built-in dictation.

The core idea is simple: voice input should behave like a universal text shortcut. Hold a key or mouse side button, speak, release, and the cleaned text appears exactly where the cursor is.

## Why Not Just Use macOS Dictation?

Built-in dictation is convenient, but it is optimized for general-purpose speech input. In real desktop writing, the friction often appears in different places:

- Mixed Chinese-English writing, especially product names, model names, commands, code terms, and abbreviations.
- Spoken drafts that contain filler words, repeated connectors, and unclear punctuation.
- Switching between WeChat, browsers, note apps, editors, and forms where the user wants the same input behavior everywhere.
- Lack of control over the transcription backend, post-processing rules, output style, and trigger behavior.
- Privacy-sensitive workflows where sending raw audio to a cloud service is undesirable.

VoxPaste treats dictation as a workflow problem, not only a speech recognition problem. The product value comes from combining local transcription, explicit hold-to-record interaction, deterministic text cleanup, optional local LLM polishing, and paste automation into one small loop.

| Need | Built-in dictation | VoxPaste Local |
| --- | --- | --- |
| Quick basic dictation | Strong | Supported |
| Mouse side-button hold-to-record | Not the core interaction | Built around it |
| Local Whisper backend | Not configurable | Uses `mlx-whisper` on Apple Silicon |
| Mixed Chinese-English tuning | Limited user control | Can use a Chinese language hint or auto-detect |
| Filler-word and punctuation cleanup | Opaque | Rule-based by default, local LLM optional |
| Output style control | Limited | `raw`, `polished`, or `structured` |
| Works across apps | Yes | Yes, by clipboard + paste automation |

This project does not claim to beat native dictation in every situation. It targets a narrower workflow: fast, repeatable, local voice-to-paste for users who care about control, mixed-language text, and post-processing.

## What It Does

- Records while you hold a keyboard key or mouse side button.
- Transcribes audio with `mlx-whisper` on Apple Silicon.
- Cleans spoken text with local rules for filler words, spacing, and punctuation.
- Optionally uses a local LM Studio model for higher-quality polishing or structuring.
- Can output raw transcripts, polished writing, or structured Markdown notes.
- Copies the final text to the clipboard and pastes it into the current cursor.
- Keeps configuration in `config.local.json`, so the script can stay clean.

## Product Principles

- Local first: audio can stay on the user's machine.
- Low friction: hold, speak, release, paste.
- Cross-app by default: the output goes into the active cursor, not a dedicated editor.
- Deterministic when possible: simple cleanup should not require a large language model.
- Optional intelligence: use a local LLM only when the user wants deeper rewriting or structured notes.

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
| `output_mode` | Output mode: `raw`, `polished`, or `structured` | `polished` |
| `structured_template` | Markdown template for structured output: `summary_action_items`, `meeting_notes`, or `jd_analysis` | `summary_action_items` |
| `language` | Whisper language hint. Use `zh` for mostly Chinese speech; use `null` to let Whisper auto-detect, which can be useful for mixed Chinese-English speech | `zh` |
| `use_local_llm` | Whether to call LM Studio for polished or structured output | `false` |
| `lm_studio_url` | LM Studio OpenAI-compatible endpoint | `http://localhost:1234/v1` |
| `llm_model` | Model name loaded in LM Studio | `local-model` |

## Output Modes

VoxPaste does not require an LLM for every mode:

| Mode | LLM needed? | Behavior |
| --- | --- | --- |
| `raw` | No | Paste the Whisper transcript as-is. |
| `polished` | Optional | If `use_local_llm=true`, clean the text with LM Studio. Otherwise use local rule-based cleanup for filler words, spacing, and punctuation. |
| `structured` | Optional | If `use_local_llm=true`, ask LM Studio to produce structured Markdown. Otherwise use a rule-based Markdown fallback. |

Structured output supports these templates:

- `summary_action_items`: `Summary`, `Key Points`, `Action Items`
- `meeting_notes`: `Summary`, `Discussion Notes`, `Decisions`, `Action Items`
- `jd_analysis`: `Role Summary`, `Requirements`, `Signals To Highlight`, `Questions To Clarify`

The rule-based fallback is intentionally conservative. It formats the transcript into sections and extracts likely action items, but it does not infer, summarize deeply, or invent missing details. For higher-quality structure, run LM Studio locally and set `use_local_llm` to `true`.

Older configs that still use `use_llm_polish` are supported as a backwards-compatible alias.

### Local Cleanup Example

You can test the local speech cleanup path without recording audio:

```bash
python voxpaste.py \
  --output-mode polished \
  --format-text "嗯那个就是我觉得这个软件有两个问题然后第一个是速度慢第二个是界面乱"
```

Example output:

```text
我觉得这个软件有两个问题：第一个是速度慢，第二个是界面乱。
```

You can test the local rule-based structured path without recording audio:

```bash
python voxpaste.py \
  --output-mode structured \
  --structured-template summary_action_items \
  --format-text "We need to review the JD. Next prepare a short demo video."
```

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

This checks the platform, imports core dependencies in child processes, and checks LM Studio only when local LLM output is enabled.

## Run

```bash
python voxpaste.py
```

Then:

1. Hold the trigger key or mouse side button.
2. Speak.
3. Release.
4. The transcript is pasted into the current cursor.

## Mixed Chinese-English Usage

For mostly Chinese speech, keep:

```json
"language": "zh"
```

For heavier mixed Chinese-English speech, such as product names, model names, commands, and code terms, try:

```json
"language": null
```

This removes the fixed language hint and lets Whisper detect the speech more freely. The best setting depends on the microphone, speaking style, model, and the ratio of Chinese to English terms.

Examples of the target use cases:

- "我想把 output mode 改成 polished，然后默认 trigger mouse button 用 side。"
- "这个 JD 里面提到 prompt engineering、SFT 和 RLHF，我想提炼成简历关键词。"
- "Next step 是录一个 demo video，然后把 GitHub README 优化一下。"

## Helper Scripts

Use these when choosing a trigger:

```bash
python scripts/detect_key.py
python scripts/detect_mouse.py
```

They print the `pynput` key/button names recognized by your machine. On macOS, some side buttons are reported as `unknown` or `middle`; the default `side` alias maps to the best available side-button representation for the current `pynput` backend.

## Why This Project Exists

Most voice input tools focus on recognition accuracy alone. VoxPaste explores a different question: what would voice input look like if it were designed as a desktop productivity layer?

The answer is a small but complete loop:

```text
capture intent quickly
  -> transcribe locally
  -> clean speech into usable writing
  -> paste into the current app
```

The project is intentionally small. Its value is not in building another full dictation app, but in proving a product hypothesis: for frequent desktop writing, the combination of local AI, hardware-triggered recording, and text post-processing can be more useful than raw transcription alone.

## Demo Story

A practical demo should compare the same workflow in two ways:

1. Use native dictation to input a mixed Chinese-English sentence with product names or code terms.
2. Use VoxPaste with a mouse side button to record the same sentence and paste cleaned text into the same app.

The point of the demo is not to claim universal accuracy superiority. The point is to show the product difference: VoxPaste is configurable, local-first, side-button driven, and has a post-processing layer that turns spoken drafts into cleaner written text.

## Limitations

- First Whisper run may download the model and take time.
- MLX/Metal can fail in unsupported or headless environments.
- Paste automation depends on macOS Accessibility permissions.
- LM Studio cleanup is optional and only works when LM Studio is running with a loaded model.
- Rule-based cleanup is conservative. It improves common filler words and punctuation, but it does not deeply rewrite or infer missing meaning.
- Rule-based structured output is basic; high-quality semantic structuring requires a local LLM.
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
├── docs/
│   └── project-brief.md     # portfolio summary
└── README.md
```

For a portfolio-ready project summary, see [docs/project-brief.md](docs/project-brief.md).

## License

MIT
