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

## Voice Choice MVP

This module also includes an optional voice-control bridge:

```text
Assets/ConvenienceStoreDialog/Runtime/VoiceChoiceReceiver.cs
Assets/ConvenienceStoreDialog/ExternalVoiceService/voice_choice_server.py
```

The external service accepts recognized text, matches it to choice index `0`, `1`, or `2`, and exposes the latest result for VRChat polling:

```text
http://127.0.0.1:8765/session/default/latest
```

Start the test service from the Unity project root:

```powershell
python Assets/ConvenienceStoreDialog/ExternalVoiceService/voice_choice_server.py
```

Then open:

```text
http://127.0.0.1:8765/
```

Submit sample text such as `唐揚げ弁当を探しています`, `コーヒーはありますか`, or `ATMはどこですか`. `VoiceChoiceReceiver` polls the result and triggers the same dialogue choice that a click would trigger.

## Requirements

- Unity 2022.3.x
- VRChat SDK Worlds
- UdonSharp
- TextMeshPro
