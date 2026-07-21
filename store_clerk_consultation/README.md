# Store Clerk Consultation Module

This folder contains the VRChat/UdonSharp convenience-store clerk consultation module.

## Contents

```text
store_clerk_consultation/
  Assets/
    ConvenienceStoreDialog/
      Runtime/
      Editor/
      Fonts/
      README.md
```

## How To Use In A Unity VRChat Project

Copy this folder's `Assets/ConvenienceStoreDialog` directory into the target Unity project's `Assets/` directory.

The final Unity path should be:

```text
Assets/ConvenienceStoreDialog/
```

Then open Unity and run:

```text
Tools > Convenience Store Dialog > Install Or Refresh In Current Scene
```

This creates or refreshes:

```text
NPC_DialogTrigger_Demo
```

The interaction uses world-space reply buttons with `BoxCollider` and VRChat `Interact()`, not ordinary Unity UI buttons.

## Local Whisper Voice Choice

This module also includes an optional voice-control bridge:

```text
Assets/ConvenienceStoreDialog/Runtime/VoiceChoiceReceiver.cs
Assets/ConvenienceStoreDialog/ExternalVoiceService/voice_choice_server.py
```

The external service captures a Windows microphone with `soundcard`, segments speech by RMS/silence, transcribes Japanese locally with `faster-whisper`, matches the transcript to choice index `0`, `1`, or `2`, and exposes the latest result for VRChat polling:

```text
http://127.0.0.1:8765/session/default/latest
```

Install the local environment once, then start the service:

```powershell
& Assets/ConvenienceStoreDialog/ExternalVoiceService/setup_whisper.ps1
& Assets/ConvenienceStoreDialog/ExternalVoiceService/run_whisper.ps1
```

List microphone names when device selection needs adjustment:

```powershell
& Assets/ConvenienceStoreDialog/ExternalVoiceService/run_whisper.ps1 --list-devices
```

The included launcher defaults to `MIXLINE Record`, matching the validated `interaction` configuration on this machine. Override `STORE_CLERK_CAPTURE_MICROPHONE` with any unique part of another Windows device name when needed.

The page at `http://127.0.0.1:8765/` shows the latest Whisper result and retains manual transcript submission as a fallback. `VoiceChoiceReceiver` polls the result and triggers the same dialogue choice that a click would trigger.

## Requirements

- Unity 2022.3.x
- VRChat SDK Worlds
- UdonSharp
- TextMeshPro
- Python 3.11
- A Windows recording microphone
