from __future__ import annotations

import argparse
import math
import os
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class DirectionEstimate:
    label: str
    balance: float
    confidence: float
    left_rms: float
    right_rms: float


@dataclass(frozen=True)
class Frame:
    timestamp: float
    path: Path


@dataclass(frozen=True)
class OcrCandidate:
    text: str
    confidence: float
    center_x: float
    center_y: float
    frame: Path


@dataclass(frozen=True)
class AttributionResult:
    status: str
    speaker_name: str | None
    confidence: float
    direction: DirectionEstimate
    candidates: list[tuple[str, float]]


class StereoRmsSegmenter:
    def __init__(self, sample_rate: int, threshold: float, silence_seconds: float, min_seconds: float, max_seconds: float) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.silence_samples = int(sample_rate * silence_seconds)
        self.min_samples = int(sample_rate * min_seconds)
        self.max_samples = int(sample_rate * max_seconds)
        self._buffer: list[np.ndarray] = []
        self._silence_seen = 0
        self._active = False

    def push(self, chunk: np.ndarray) -> list[np.ndarray]:
        chunk = np.asarray(chunk, dtype=np.float32)
        mono = to_mono(chunk)
        rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
        is_speech = rms >= self.threshold
        emitted: list[np.ndarray] = []

        if is_speech and not self._active:
            self._active = True
            self._silence_seen = 0

        if self._active:
            self._buffer.append(chunk)
            if is_speech:
                self._silence_seen = 0
            else:
                self._silence_seen += len(mono)

            total = sum(len(to_mono(part)) for part in self._buffer)
            if self._silence_seen >= self.silence_samples or total >= self.max_samples:
                segment = self._flush()
                if len(to_mono(segment)) >= self.min_samples:
                    emitted.append(segment)
        return emitted

    def _flush(self) -> np.ndarray:
        if not self._buffer:
            return np.empty((0, 2), dtype=np.float32)
        segment = np.concatenate(self._buffer, axis=0).astype(np.float32, copy=False)
        self._buffer.clear()
        self._silence_seen = 0
        self._active = False
        return segment


class ScreenshotBuffer:
    def __init__(self, output_dir: Path, interval_seconds: float, keep_seconds: float) -> None:
        self.output_dir = output_dir
        self.interval_seconds = interval_seconds
        self.keep_seconds = keep_seconds
        self.frames: deque[Frame] = deque()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.available = False

    def start(self) -> None:
        try:
            import mss  # noqa: F401
        except ImportError:
            print("[speaker-attribution] mss is not installed; screenshot/OCR attribution disabled.")
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.available = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2.0)

    def recent(self, count: int) -> list[Path]:
        with self.lock:
            return [frame.path for frame in list(self.frames)[-count:]]

    def _run(self) -> None:
        import mss
        import mss.tools

        with mss.mss() as screen:
            monitor = screen.monitors[1]
            while not self.stop_event.is_set():
                now = time.time()
                path = self.output_dir / f"frame-{int(now * 1000)}.png"
                image = screen.grab(monitor)
                mss.tools.to_png(image.rgb, image.size, output=str(path))
                with self.lock:
                    self.frames.append(Frame(now, path))
                    cutoff = now - self.keep_seconds
                    while self.frames and self.frames[0].timestamp < cutoff:
                        old = self.frames.popleft()
                        try:
                            old.path.unlink(missing_ok=True)
                        except OSError:
                            pass
                self.stop_event.wait(self.interval_seconds)


class EasyOcrNameReader:
    def __init__(self, languages: list[str]) -> None:
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("easyocr is not installed") from exc
        self.reader = easyocr.Reader(languages, gpu=False)

    def read(self, image_paths: Iterable[Path]) -> list[OcrCandidate]:
        candidates: list[OcrCandidate] = []
        for path in image_paths:
            results = self.reader.readtext(str(path), detail=1, paragraph=False)
            for bbox, text, confidence in results:
                cleaned = clean_name(text)
                if not cleaned:
                    continue
                xs = [float(point[0]) for point in bbox]
                ys = [float(point[1]) for point in bbox]
                width, height = image_size(path)
                candidates.append(
                    OcrCandidate(
                        text=cleaned,
                        confidence=float(confidence),
                        center_x=(sum(xs) / len(xs)) / max(width, 1),
                        center_y=(sum(ys) / len(ys)) / max(height, 1),
                        frame=path,
                    )
                )
        return candidates


def image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return (1920, 1080)


def to_mono(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1)


def estimate_direction(audio: np.ndarray) -> DirectionEstimate:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] < 2:
        mono_rms = rms(to_mono(audio))
        return DirectionEstimate("unknown", 0.0, 0.0, mono_rms, mono_rms)

    left = audio[:, 0]
    right = audio[:, 1]
    left_rms = rms(left)
    right_rms = rms(right)
    denom = max(left_rms + right_rms, 1e-6)
    balance = (right_rms - left_rms) / denom
    abs_balance = abs(balance)

    if abs_balance < 0.08:
        return DirectionEstimate("center", balance, max(0.0, 1.0 - abs_balance / 0.08), left_rms, right_rms)
    label = "right" if balance > 0 else "left"
    return DirectionEstimate(label, balance, min(1.0, abs_balance / 0.35), left_rms, right_rms)


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def clean_name(text: str) -> str | None:
    text = " ".join(text.replace("\n", " ").split()).strip(" :|[](){}")
    if len(text) < 2 or len(text) > 32:
        return None
    lowered = text.casefold()
    blocked = {"menu", "settings", "avatar", "world", "social", "launch pad", "mic", "voice", "debug"}
    if lowered in blocked:
        return None
    if sum(ch.isalnum() for ch in text) < 2:
        return None
    return text


def attribute_speaker(direction: DirectionEstimate, candidates: list[OcrCandidate], threshold: float, multiple_ratio: float) -> AttributionResult:
    if not candidates:
        return AttributionResult("unknown", None, 0.0, direction, [])

    target_x = {"left": 0.25, "center": 0.5, "right": 0.75}.get(direction.label, 0.5)
    scores: Counter[str] = Counter()
    for candidate in candidates:
        if candidate.center_y < 0.05 or candidate.center_y > 0.85:
            continue
        x_score = max(0.0, 1.0 - abs(candidate.center_x - target_x) / 0.4)
        direction_weight = 0.55 + 0.45 * direction.confidence
        score = candidate.confidence * (0.35 + 0.65 * x_score) * direction_weight
        scores[candidate.text] += score

    ranked = scores.most_common(5)
    if not ranked:
        return AttributionResult("unknown", None, 0.0, direction, [])

    top_name, top_score = ranked[0]
    if top_score < threshold:
        return AttributionResult("unknown", None, float(top_score), direction, ranked)
    if len(ranked) > 1 and ranked[1][1] >= top_score * multiple_ratio:
        return AttributionResult("multiple", None, float(top_score), direction, ranked)
    return AttributionResult("identified", top_name, float(top_score), direction, ranked)


def select_speaker(name_fragment: str | None):
    import soundcard as sc

    if not name_fragment:
        return sc.default_speaker()
    fragment = name_fragment.casefold()
    matches = [speaker for speaker in sc.all_speakers() if fragment in speaker.name.casefold()]
    if not matches:
        available = "\n".join(f"- {speaker.name}" for speaker in sc.all_speakers())
        raise RuntimeError(f"Speaker matching {name_fragment!r} was not found.\n{available}")
    return matches[0]


def load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype VRChat speaker attribution with stereo direction + OCR.")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--speaker", default=os.getenv("VRCHAT_AI_CAPTURE_SPEAKER", ""))
    parser.add_argument("--sample-rate", type=int, default=int(os.getenv("VRCHAT_AI_SAMPLE_RATE", "16000")))
    parser.add_argument("--threshold", type=float, default=float(os.getenv("VRCHAT_AI_RMS_THRESHOLD", "0.012")))
    parser.add_argument("--ocr-langs", default=os.getenv("VRCHAT_AI_OCR_LANGS", "en,ja,ch_sim,ch_tra"))
    parser.add_argument("--screenshot-dir", default=os.getenv("VRCHAT_AI_SCREENSHOT_DIR", ".tmp/speaker_attribution"))
    parser.add_argument("--frame-count", type=int, default=int(os.getenv("VRCHAT_AI_SPEAKER_ATTRIBUTION_FRAME_COUNT", "5")))
    parser.add_argument("--confidence-threshold", type=float, default=float(os.getenv("VRCHAT_AI_SPEAKER_CONFIDENCE_THRESHOLD", "0.55")))
    parser.add_argument("--multiple-ratio", type=float, default=float(os.getenv("VRCHAT_AI_SPEAKER_MULTIPLE_RATIO", "0.75")))
    args = parser.parse_args()

    load_dotenv_if_present()

    screenshot_buffer = ScreenshotBuffer(Path(args.screenshot_dir), interval_seconds=0.5, keep_seconds=8.0)
    screenshot_buffer.start()

    ocr_reader = None
    if screenshot_buffer.available:
        try:
            ocr_reader = EasyOcrNameReader([lang.strip() for lang in args.ocr_langs.split(",") if lang.strip()])
        except RuntimeError as exc:
            print(f"[speaker-attribution] {exc}; OCR disabled, direction only.")

    import soundcard as sc

    speaker = select_speaker(args.speaker or None)
    print(f"Capture speaker: {speaker.name}")
    print("Listening for attribution segments. Press Ctrl+C to stop.")

    segmenter = StereoRmsSegmenter(args.sample_rate, args.threshold, silence_seconds=0.8, min_seconds=0.6, max_seconds=8.0)
    chunk_frames = max(1, int(args.sample_rate * 0.25))
    deadline = time.time() + args.duration if args.duration > 0 else math.inf

    try:
        with sc.get_microphone(speaker.name, include_loopback=True).recorder(samplerate=args.sample_rate, channels=2) as recorder:
            while time.time() < deadline:
                chunk = recorder.record(numframes=chunk_frames)
                for segment in segmenter.push(chunk):
                    direction = estimate_direction(segment)
                    candidates = ocr_reader.read(screenshot_buffer.recent(args.frame_count)) if ocr_reader else []
                    attribution = attribute_speaker(direction, candidates, args.confidence_threshold, args.multiple_ratio)
                    print_result(attribution)
    finally:
        screenshot_buffer.stop()
    return 0


def print_result(result: AttributionResult) -> None:
    print(
        "speaker_attribution "
        f"status={result.status} "
        f"speaker={result.speaker_name or '-'} "
        f"direction={result.direction.label} "
        f"balance={result.direction.balance:.3f} "
        f"direction_conf={result.direction.confidence:.2f} "
        f"confidence={result.confidence:.2f}"
    )
    if result.candidates:
        candidate_text = ", ".join(f"{name}:{score:.2f}" for name, score in result.candidates[:5])
        print(f"  candidates: {candidate_text}")


if __name__ == "__main__":
    raise SystemExit(main())
