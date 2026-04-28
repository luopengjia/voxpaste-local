# VoxPaste Local 作品说明

## 一句话

VoxPaste Local 是一个本地优先的 macOS 语音输入工具：按住快捷键录音，松开后使用本地 Whisper 转写，可选本地 LLM 润色，并自动粘贴到当前光标。

## 目标用户

高频写作者、学生、产品经理、研究人员，以及经常在微信、浏览器、笔记软件、代码编辑器里输入长文本的人。

## 核心流程

```text
按住快捷键/鼠标键
  -> 录制麦克风音频
  -> MLX Whisper 本地转写
  -> 可选 LM Studio 本地模型润色
  -> 写入剪贴板
  -> 模拟 Cmd+V 粘贴到当前光标
```

## 技术栈

- Python
- mlx-whisper
- sounddevice
- pynput
- pyperclip
- LM Studio OpenAI-compatible API
- macOS AppleScript paste automation

## 我负责的部分

- 设计本地语音输入的最小闭环，从录音、转写、润色到粘贴。
- 将个人脚本整理成可公开发布的小项目，补齐配置文件、README、许可证、`.gitignore` 和环境自检。
- 处理 macOS 权限、快捷键监听、鼠标按住触发、Whisper 模型加载、可选 LLM 润色等细节。
- 将依赖延迟导入，并用 `--check` 在子进程里检测 MLX，避免环境异常时直接让主进程崩溃。

## 项目亮点

- 本地优先：音频不需要上传云端，适合隐私敏感输入场景。
- 使用体验清楚：按住说话、松开粘贴，不打断用户原来的写作环境。
- AI 工具落地：不是只调用模型，而是把模型嵌进一个真实输入工作流。
- 工程化整理：从单机脚本整理为 GitHub 可读、可运行、可复用的小项目。

## 简历写法

```text
VoxPaste Local | 本地 AI 语音输入工具
- 独立实现 macOS 本地语音输入工作流：按住快捷键录音，松开后通过 MLX Whisper 转写，并自动粘贴到当前光标。
- 接入 LM Studio OpenAI-compatible API，支持可选本地 LLM 润色，将口语转为更适合聊天、笔记和文档的书面表达。
- 将个人脚本整理为可公开发布项目，补齐配置外置、环境自检、README、许可证与 GitHub 仓库结构。
```
