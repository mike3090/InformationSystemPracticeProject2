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

The choice buttons are physical world-space objects with `BoxCollider` and Udon `Interact()`. They are not ordinary Unity UI buttons.
