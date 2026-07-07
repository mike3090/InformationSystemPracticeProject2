# VRChat AI Text Bridge

本仓库提供一个本机原型：监听 VRChat 的输出音频，将其他玩家说话转成文本，交给 `gpt-4o-mini` 生成回复，并把回复显示为文字。语音合成和推送到 VRChat 麦克风的部分先暂停，后续再接。

## 当前实现

- OpenAI 服务端：`gpt-4o-mini` 聊天接口，API key 留给你在 `.env` 中填写。
- 本机音频监听：使用 Windows WASAPI 回环录制指定播放设备。Windows 上更稳定的做法是按“设备”监听；如果需要只听 VRChat，不听其它软件声音，请把 VRChat 输出路由到单独的虚拟播放设备。
- 语音转文本：使用 `faster-whisper` 本地模型，首次运行会下载模型。
- 文字输出：默认显示在终端；也可以通过 VRChat OSC 发到 Chatbox。

## 安装

1. 安装 Python 依赖和下载 STT 模型

   ```powershell
   .\scripts\setup.ps1
   ```

2. 填写配置

   ```powershell
   Copy-Item .env.example .env
   ```

   然后编辑 `.env`，填入：

   ```text
   OPENAI_API_KEY=你的 key
   ```

   多行系统提示词放在 `prompts/system.md`。`.env` 中默认使用：

   ```text
   VRCHAT_AI_SYSTEM_PROMPT_FILE=prompts/system.md
   ```

   如果你想临时用单行提示词，可以清空 `VRCHAT_AI_SYSTEM_PROMPT_FILE`，再设置 `VRCHAT_AI_SYSTEM_PROMPT=...`。

3. 可选：打开 VRChat OSC

   如果只想在终端看文字，不需要做这步。

   如果想让回复出现在 VRChat Chatbox：

   - 在 VRChat Action Menu 中开启 OSC。
   - 在 `.env` 中设置 `VRCHAT_AI_TEXT_OUTPUT=console,osc`。
   - OSC 默认发送到 `127.0.0.1:9000`。

## 运行

先查看设备名：

```powershell
.\.venv\Scripts\python.exe -m vrchat_ai_voice devices
```

在 `.env` 中按设备名片段填写：

```text
VRCHAT_AI_CAPTURE_SPEAKER=
VRCHAT_AI_TEXT_OUTPUT=console
```

启动 OpenAI 服务端：

```powershell
.\.venv\Scripts\python.exe -m vrchat_ai_voice server
```

另开一个终端启动语音桥接：

```powershell
.\.venv\Scripts\python.exe -m vrchat_ai_voice run
```

## 后续改进点

- 多人同时说话时，在 `RmsSegmenter` 前替换为更强的 VAD 和说话人分离。
- 如果要避免监听到游戏音效，可以将 VRChat 输出路由到专用播放设备，再只监听该设备。
- 后续再接 TTS 和麦克风推送；到那一步再考虑 VB-CABLE、Voicemeeter、已有 Stereo Mix 或其它音频路由方案。

## 组件选择

- STT：`faster-whisper`，默认模型为 `base`，可在 `.env` 的 `VRCHAT_AI_TRANSCRIBE_MODEL` 中改成 `small`、`medium` 或本地模型路径。
- LLM：OpenAI `gpt-4o-mini`。
- VRChat 文字显示：OSC Chatbox。
