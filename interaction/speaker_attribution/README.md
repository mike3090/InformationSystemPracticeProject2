# Speaker Attribution Prototype

This folder is a standalone experiment for identifying the current VRChat speaker without a vision LLM.

Pipeline:

1. Capture loopback audio in stereo.
2. Segment speech using an RMS threshold.
3. Estimate direction from left/right channel energy.
4. Keep a short screenshot buffer.
5. OCR recent screenshots and score visible name text by x-position vs audio direction.

Install optional OCR/screenshot dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r speaker_attribution\requirements.txt
```

Run for 60 seconds:

```powershell
.\.venv\Scripts\python.exe speaker_attribution\prototype.py --duration 60
```

If EasyOCR is not installed, the script still prints audio direction only.
If MSS is not installed, screenshot/OCR attribution is disabled.

Recommended next step: collect screenshots where VRChat nameplates and speaking rings are visible, then train a small YOLO detector for `nameplate` and `speaking_ring_active`. OCR should then run only on detected nameplate crops.
