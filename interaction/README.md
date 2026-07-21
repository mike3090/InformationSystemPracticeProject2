# VRChat AI Voice Bridge

本目录是一个本机 VRChat AI 店员原型：监听用户语音，转成文字，交给 LLM 生成便利店 NPC 回复，再把回复显示为文字并可选地用 TTS 通过 VRChat 麦克风播给远端用户。

## 当前进度

- STT：使用 `faster-whisper`，当前配置为 `base`，并尝试使用 `cuda/float16`。
- LLM：使用 `gpt-4o-mini`，本地 FastAPI 服务封装 OpenAI 请求。
- LLM 输出：服务端强制要求 JSON，包含 `display_text` 和 `spoken_text`。
- 文字显示：`display_text` 输出到 PowerShell、`runtime/transcript.log`，并可通过 OSC Chatbox 发到 VRChat。
- TTS：使用 OpenAI `tts-1` + `alloy`，当前回退为完整 `wav` 播放，避免流式 PCM 的卡顿/电流声。
- TTS 播放：`spoken_text` 只包含日语，英文括号翻译不会进入 TTS。
- VRChat 麦克风控制：当前推荐 Push-to-talk；TTS 播放前发 `/input/Voice true`，播放后发 `/input/Voice false`。
- MIXLINE：推荐用 `MIXLINE Record` 给程序做 STT 输入，用 `MIXLINE Stream` 作为 VRChat 麦克风输出。
- 自动面向目标：`run_all.ps1 -SaveDebug` 会启动 OCR/自动转向；只测对话时推荐 `-NoFacing`。

## 当前推荐连接

MIXLINE 分工：

```text
MIXLINE Record = 程序的耳朵，给 STT 听
MIXLINE Stream = VRChat 的麦克风，给远端用户听
```

推荐连线：

```text
VRChat 远端用户声音 -> MIXLINE Record
Python / TTS 输出源 -> MIXLINE Stream
```

VRChat 设置：

```text
Microphone input = 麦克风 (MIXLINE Stream)
Microphone Behaviour = Push-to-talk / 按住说话
OSC = enabled
```

程序 STT 当前听：

```text
VRCHAT_AI_CAPTURE_MODE=microphone
VRCHAT_AI_CAPTURE_MICROPHONE=MIXLINE Record
```

不要连接：

```text
Python / TTS -> MIXLINE Record
MIXLINE Stream -> MIXLINE Record
VRChat -> MIXLINE Stream
```

否则 AI 可能听到自己刚说的话，或把 VRChat 输出重新送回 VRChat 麦克风。

## 启动方式

进入目录：

```powershell
cd C:\Users\ShengxinLi\Desktop\Codes\InformationSystemPracticeProject2\InformationSystemPracticeProject2\interaction
```

只测试 STT + LLM + TTS，不启动 OCR/自动转向：

```powershell
.\run_all.ps1 -NoFacing
```

启动完整脚本，包括截图/OCR/自动面向目标：

```powershell
.\run_all.ps1 -SaveDebug
```

如果自动转向方向反了：

```powershell
.\run_all.ps1 -SaveDebug -InvertLook
```

停止脚本：

```text
Ctrl+C
```

如果有后台残留，只停止当前目录相关 Python 进程：

```powershell
$root = (Resolve-Path .).Path
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*.exe' -and $_.CommandLine -like "*$root*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## 运行时看哪里

当前 PowerShell 会实时显示：

```text
[STT] Other player (ja, p=0.98): ...
[LLM] AI: ...
[TTS] synthesizing: ...
[TTS] VRChat mic hold: press
[TTS] playing on: ...
[TTS] playback finished
[TTS] VRChat mic hold: release
```

转写和回复日志：

```powershell
Get-Content .\runtime\transcript.log -Tail 40 -Wait
```

完整脚本输出：

```powershell
Get-Content .\runtime\run_all.out.log -Tail 80 -Wait
```

错误日志：

```powershell
Get-Content .\runtime\run_all.err.log -Tail 80 -Wait
```

## 关键配置

当前 `.env` 的核心配置应类似：

```text
OPENAI_MODEL=gpt-4o-mini

VRCHAT_AI_CAPTURE_MODE=microphone
VRCHAT_AI_CAPTURE_MICROPHONE=MIXLINE Record

VRCHAT_AI_TEXT_OUTPUT=console,file,osc

VRCHAT_AI_TRANSCRIBE_MODEL=base
VRCHAT_AI_TRANSCRIBE_DEVICE=cuda
VRCHAT_AI_TRANSCRIBE_COMPUTE_TYPE=float16
VRCHAT_AI_TRANSCRIBE_ALLOWED_LANGUAGES=ja,zh,en

VRCHAT_AI_CHUNK_SECONDS=0.12
VRCHAT_AI_MIN_SEGMENT_SECONDS=0.45
VRCHAT_AI_SILENCE_SECONDS=0.45

VRCHAT_AI_TTS_ENABLED=true
VRCHAT_AI_TTS_MODEL=tts-1
VRCHAT_AI_TTS_VOICE=alloy
VRCHAT_AI_TTS_RESPONSE_FORMAT=wav
VRCHAT_AI_TTS_STREAMING=false
VRCHAT_AI_TTS_VRCHAT_MIC_CONTROL=hold
VRCHAT_AI_POST_TTS_COOLDOWN_SECONDS=0.4
```

`VRCHAT_AI_TTS_OUTPUT_SPEAKER` 当前可以留空，让程序使用 Windows 默认输出；如果要固定到某个设备，可以填设备名片段，例如：

```text
VRCHAT_AI_TTS_OUTPUT_SPEAKER=MIXLINE
VRCHAT_AI_TTS_OUTPUT_SPEAKER=Steam Streaming Microphone
VRCHAT_AI_TTS_OUTPUT_SPEAKER=NVIDIA
```

列出当前 Windows 音频设备：

```powershell
.\.venv\Scripts\python.exe -m vrchat_ai_voice devices
```

## LLM 输出格式

服务端会要求模型返回 JSON：

```json
{
  "display_text": "こちらにタッチしてください。（Please tap your card here.）",
  "spoken_text": "こちらにタッチしてください。"
}
```

程序使用方式：

```text
display_text -> PowerShell / transcript.log / OSC Chatbox
spoken_text  -> TTS
```

这样 TTS 不再依赖括号切割或标题切割，英文翻译不会被读出来。

## OSC 边界

OSC 可以用于：

```text
Chatbox 文字
VRChat 输入控制，例如 /input/Voice
Avatar 参数
```

OSC 不能用于：

```text
把 TTS 音频直接作为 VRChat 麦克风音频流输入
```

要让远端玩家听到 TTS，必须走 Windows 音频设备或 MIXLINE 虚拟麦克风：

```text
Python TTS -> MIXLINE Stream -> VRChat microphone
```

## 安装

首次安装依赖：

```powershell
.\scripts\setup.ps1
```

如果没有 `.env`：

```powershell
Copy-Item .env.example .env
```

然后填写：

```text
OPENAI_API_KEY=你的 key
```

系统提示词在：

```text
prompts/system.md
```

## 已知问题和调试建议

- TTS 流式 PCM 曾出现卡顿/电流声，所以当前默认使用 `wav` 非流式播放。
- OCR/自动转向会使用 EasyOCR，目前 torch 是 CPU-only 时会刷 `pin_memory` warning，并可能拖慢整体体验；只测对话时用 `-NoFacing`。
- STT 当前尝试 `cuda/float16`，如果初始化失败，代码会自动回退到 `cpu/int8`。
- 如果 TTS 能在 PowerShell 显示播放但 VRChat 没听到，优先检查 MIXLINE 里 `Python/TTS` 是否连到 `MIXLINE Stream`，以及 VRChat 麦克风是否选择 `麦克风 (MIXLINE Stream)`。
