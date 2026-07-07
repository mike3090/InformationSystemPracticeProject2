from __future__ import annotations

import numpy as np


class RmsSegmenter:
    def __init__(
        self,
        sample_rate: int,
        threshold: float,
        min_segment_seconds: float,
        silence_seconds: float,
        max_segment_seconds: float,
    ) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_segment_samples = int(sample_rate * min_segment_seconds)
        self.silence_samples = int(sample_rate * silence_seconds)
        self.max_segment_samples = int(sample_rate * max_segment_seconds)
        self._buffer: list[np.ndarray] = []
        self._silence_seen = 0
        self._active = False

    def push(self, chunk: np.ndarray) -> list[np.ndarray]:
        chunk = np.asarray(chunk, dtype=np.float32)
        rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size else 0.0
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
                self._silence_seen += len(chunk)

            total_samples = sum(len(part) for part in self._buffer)
            should_close = self._silence_seen >= self.silence_samples or total_samples >= self.max_segment_samples
            if should_close:
                segment = self._flush()
                if len(segment) >= self.min_segment_samples:
                    emitted.append(segment)
        return emitted

    def _flush(self) -> np.ndarray:
        if not self._buffer:
            return np.empty(0, dtype=np.float32)
        segment = np.concatenate(self._buffer).astype(np.float32, copy=False)
        self._buffer.clear()
        self._silence_seen = 0
        self._active = False
        return segment
