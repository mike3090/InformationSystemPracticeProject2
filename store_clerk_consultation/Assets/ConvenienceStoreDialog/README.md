# Convenience Store Dialog Module

VRChat/UdonSharp convenience-store dialogue prototype.

## What It Contains

- `Runtime/ProximityDialogTrigger.cs`
  - Shows the world-space dialogue panel when the local player is near.
  - Manages the convenience-store dialogue state.
  - Updates the question text and three reply choices.
- `Runtime/ProximityDialogChoiceButton.cs`
  - Handles VRChat `Interact()` on each reply choice.
  - Sends the selected choice back to `ProximityDialogTrigger`.
- `Runtime/*.asset`
  - UdonSharp program assets for the two runtime scripts.
- `Editor/AddProximityDialogToScene.cs`
  - Installs or refreshes `NPC_DialogTrigger_Demo` in the active scene.
  - Builds the NPC marker, dialogue canvas, text fields, and three interactable choice buttons.
- `Runtime/VoiceChoiceReceiver.cs`
  - Polls an external voice-choice service.
  - Converts service results into the same `SelectChoice0/1/2` calls used by clickable buttons.
- `ExternalVoiceService/voice_choice_server.py`
  - Minimal local HTTP service for the MVP.
  - Serves a browser microphone page using Web Speech API for Japanese ASR.
  - Also accepts manual recognized text and matches it to choice index `0`, `1`, or `2`.
- `Fonts/`
  - Noto Sans CJK JP TMP font assets used for Japanese text display.

## Install Or Refresh In A Scene

In Unity:

1. Open the target scene.
2. Run `Tools > Convenience Store Dialog > Install Or Refresh In Current Scene`.
3. Enter Play mode or use VRChat Build & Test.
4. Walk near `NPC_DialogTrigger_Demo`.
5. Aim at a reply button and click/interact to progress the dialogue.

The installer is idempotent: running it again updates the existing object instead of creating a second one.

## Voice Choice MVP

The generated NPC also includes `VoiceChoiceReceiver`.

Default polling URL:

```text
http://127.0.0.1:8765/session/default/latest
```

Start the local test service:

```powershell
py -3 Assets/ConvenienceStoreDialog/ExternalVoiceService/voice_choice_server.py
```

If `py` is unavailable, try:

```powershell
python Assets/ConvenienceStoreDialog/ExternalVoiceService/voice_choice_server.py
```

Open the voice page in Chrome or Edge:

```text
http://127.0.0.1:8765/
```

Click:

```text
Start Japanese voice recognition
```

Then speak one of the current reply phrases, for example:

```text
唐揚げ弁当を探しています
コーヒーはありますか
ATMはどこですか
```

The page submits final Japanese transcripts to the local service automatically.

Manual text submission is still available on the same page as a fallback.

The service returns:

```text
version|choiceIndex|transcript|confidence
```

Example:

```text
1721540000000|0|唐揚げ弁当を探しています|0.95
```

`VoiceChoiceReceiver` polls this result. When it sees a new `version`, it triggers the matching choice in the active dialogue.

For VRChat Build & Test, external URLs may require enabling untrusted URLs in VRChat settings when using a localhost endpoint.

## Sync To Another Project

Recommended minimal sync unit:

```text
Assets/ConvenienceStoreDialog/
```

After copying this folder into another VRChat Unity project:

1. Let Unity import the assets.
2. Run `Tools > Convenience Store Dialog > Install Or Refresh In Current Scene`.
3. Save the scene.

The target project must already have VRChat SDK, UdonSharp, TextMeshPro, and Unity 2022.3.x compatible with the current project.

## Scene Object

The generated scene root is:

```text
NPC_DialogTrigger_Demo
```

It contains:

- `Visible_NPC_Marker`
- `Dialog_Canvas`
- `Dialog_Text`
- `Status_Text`
- `Choice_0_Button`
- `Choice_1_Button`
- `Choice_2_Button`
- `VoiceChoiceReceiver` component on the root object

The choice buttons are physical world-space objects with `BoxCollider` and Udon `Interact()`. They are not ordinary Unity UI buttons.
