# VRChat AI Interaction Quick Start

这个文件用于以后新开 Codex/PowerShell 窗口时快速接上当前原型。

## 1. 进入目录

```powershell
cd C:\Users\ShengxinLi\Desktop\Codes\InformationSystemPracticeProject2\InformationSystemPracticeProject2\interaction
```

## 2. 启动完整脚本

推荐启动方式：

```powershell
.\run_all.ps1 -SaveDebug
```

它会同时启动：

- 本地 OpenAI 服务端：`http://127.0.0.1:8765`
- VRChat 输出音频监听和语音转文字
- LLM 回复生成
- 文本输出到控制台、`runtime/transcript.log`，以及按 `.env` 配置发送 OSC
- 截图、名牌颜色区域裁剪、OCR、自动面朝目标玩家

如果只想测试语音转文字和 AI 回复，不想自动转向：

```powershell
.\run_all.ps1 -NoFacing
```

如果转向方向反了：

```powershell
.\run_all.ps1 -SaveDebug -InvertLook
```

## 3. 测试时看哪里

当前 PowerShell 窗口会实时显示：

```text
[STT] Other player: 对方被识别出来的话
[LLM] AI: LLM 生成的回复
[TTS] playing on: TTS 播放到的输出设备
```

主要看转写和 AI 回复：

```powershell
Get-Content .\runtime\transcript.log -Tail 40 -Wait
```

看完整脚本输出：

```powershell
Get-Content .\runtime\run_all.out.log -Tail 80 -Wait
```

看错误日志：

```powershell
Get-Content .\runtime\run_all.err.log -Tail 80 -Wait
```

看截图裁剪结果：

```powershell
explorer .\runtime\crops
```

`runtime/` 是本地运行产物，已经在 `.gitignore` 里，不需要 push。

## 4. 停止后台

如果是在当前 PowerShell 前台运行，按 `Ctrl+C`。

如果是后台残留，用这个只停止当前 interaction 目录相关的 Python 进程：

```powershell
$root = (Resolve-Path .).Path
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -like "*$root*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

检查是否还有后台：

```powershell
$root = (Resolve-Path .).Path
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -like "*$root*" } |
  Select-Object ProcessId,CommandLine
```

没有输出就表示已经停干净。

## 5. 重要配置

`.env` 里至少需要：

```text
OPENAI_API_KEY=你的 key
OPENAI_MODEL=gpt-4o-mini
VRCHAT_AI_CAPTURE_SPEAKER=
VRCHAT_AI_TEXT_OUTPUT=console,file
VRCHAT_AI_TRANSCRIBE_ALLOWED_LANGUAGES=ja,zh,en
VRCHAT_AI_SYSTEM_PROMPT_FILE=prompts/system.md
```

多行 prompt 写在：

```text
prompts/system.md
```

如果 VRChat 没有被识别到声音，先列设备：

```powershell
.\.venv\Scripts\python.exe -m vrchat_ai_voice devices
```

真实 VRChat 测试时，监听播放设备回环，也就是 VRChat 里其他玩家声音输出到哪里就监听哪里：

```text
VRCHAT_AI_CAPTURE_MODE=speaker
VRCHAT_AI_CAPTURE_SPEAKER=Steam Streaming Speakers
```

如果只是你自己对着麦克风跟它测试，把 `.env` 改成麦克风模式：

```text
VRCHAT_AI_CAPTURE_MODE=microphone
VRCHAT_AI_CAPTURE_MICROPHONE=
```

`VRCHAT_AI_CAPTURE_MICROPHONE` 留空时使用 Windows 默认麦克风；也可以填设备名的一部分。

如果要打开 TTS，让 AI 回复通过 MIXLINE 播出去：

```text
VRCHAT_AI_TTS_ENABLED=true
VRCHAT_AI_TTS_OUTPUT_SPEAKER=MIXLINE
VRCHAT_AI_TTS_VRCHAT_MIC_CONTROL=hold
VRCHAT_AI_POST_TTS_COOLDOWN_SECONDS=1.0
```

推荐 MIXLINE 路由：

```text
用户声音来源 -> MIXLINE Record -> 程序 STT 输入
程序 TTS 输出到 扬声器 (MIXLINE) -> MIXLINE Stream -> VRChat 麦克风
```

OSC 只能继续用于 Chatbox 文本、输入控制和头像参数；不能把 TTS 音频通过 OSC 作为 VRChat 麦克风输入。玩家麦克风语音必须走 Windows 音频设备，例如 `麦克风 (MIXLINE Stream)`。

如果 VRChat 设置为 Push-to-talk / 按住说话，`VRCHAT_AI_TTS_VRCHAT_MIC_CONTROL=hold` 会在 TTS 播放前发送 `/input/Voice true` 打开麦克风，播放后发送 `/input/Voice false` 关闭麦克风。

不要把 `MIXLINE Stream` 或 TTS 输出再接回 `MIXLINE Record`。程序也会在 TTS 播放期间暂停处理输入，并忽略和上一句 AI 语音很像的回声。

## 6. 当前已知状态

- 语音转文字和 LLM 回复链路已经跑通过。
- OCR/自动面朝目标还在原型阶段，可能误读 VRChat UI 或其它屏幕文字。
- 当前默认 OCR 语言是英文和日文：`en,ja`。
- TTS 已有基础输出，默认关闭；打开后会播放到 `.env` 里配置的输出设备。
