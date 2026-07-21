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

## Requirements

- Unity 2022.3.x
- VRChat SDK Worlds
- UdonSharp
- TextMeshPro
