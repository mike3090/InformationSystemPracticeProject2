# Proximity Targeting Prototype

This prototype faces the local AI account toward the currently visible nearby player without using a vision LLM.

It uses:

- VRChat OSC `/input/LookHorizontal` to rotate the account.
- MSS screenshots from the running VRChat window/screen.
- HSV color thresholding to crop likely VRChat nameplate regions.
- EasyOCR only on those cropped regions.

VRChat notes:

- Enable OSC in VRChat before using auto-facing.
- `/input/LookHorizontal` is an axis. The script sends short pulses and resets it to `0` after each pulse.
- If turning direction is reversed, pass `--invert-look`.

Install optional dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r proximity_targeting\requirements.txt
```

Run one OCR pass and save crops:

```powershell
.\.venv\Scripts\python.exe proximity_targeting\face_target.py --once --save-debug
```

Run live auto-facing:

```powershell
.\.venv\Scripts\python.exe proximity_targeting\face_target.py --save-debug
```

Tuning:

- Start with `--once --save-debug`.
- Inspect `.tmp/proximity_targeting/crops`.
- Adjust `--hue-min`, `--hue-max`, `--sat-min`, and `--value-min` until crops mostly contain nameplates.
- If no crops appear, lower `--sat-min` or `--value-min`.
