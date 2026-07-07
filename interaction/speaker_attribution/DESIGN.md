# Speaker Attribution Design

Goal: identify who is likely speaking in VRChat without using a general vision LLM.

## Current prototype

`prototype.py` combines two weak signals:

1. Stereo direction
   - Captures VRChat/Windows playback loopback in 2 channels.
   - Computes left/right RMS balance for each speech segment.
   - Emits `left`, `center`, `right`, or `unknown`.

2. OCR over recent screenshots
   - Keeps a screenshot buffer using `mss`.
   - Uses EasyOCR to read visible text.
   - Scores OCR candidates by matching their screen x-position to the audio direction.
   - Returns `identified`, `multiple`, or `unknown`.

This is intentionally conservative. If two candidates are close, it returns `multiple` rather than guessing.

## Why not a vision LLM first

A vision LLM is expensive and adds latency. It also tends to infer when it should abstain. For VRChat, the useful signal is mostly UI-level: nameplates and speaking rings. A small detector + OCR is a better fit.

## Recommended next step with YOLO

OCR over the whole screenshot is noisy. The practical upgrade is to train a tiny detector for:

- `nameplate`
- `speaking_ring_active`
- `speaking_ring_inactive`

Then run OCR only on `nameplate` crops linked to active rings. Use stereo direction as a tie-breaker when multiple active rings are visible.

Decision rules:

- one active ring + readable name: `identified`
- multiple active rings + one matches audio direction strongly: `identified`
- multiple active rings with similar score: `multiple`
- no active ring or unreadable OCR: `unknown`

## Data collection plan

Capture frames while testing in VRChat and label bounding boxes with Label Studio, CVAT, or Roboflow:

- 100-200 frames may be enough for a first same-UI prototype.
- Include different worlds, lighting, avatar sizes, and nameplate distances.
- Include both active and inactive speaking states.

After labeling, train a nano YOLO model and export it to ONNX for local inference.
