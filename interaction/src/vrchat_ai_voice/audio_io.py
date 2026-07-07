from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from .audio_devices import select_speaker
from .config import Settings


class AudioBridge:
    def __init__(self, settings: Settings) -> None:
        try:
            import soundcard as sc
        except ImportError as exc:
            raise RuntimeError("soundcard is not installed. Run scripts/setup.ps1 first.") from exc

        self._sc = sc
        self._settings = settings
        self.capture_speaker = select_speaker(settings.capture_speaker)
        self._frames_per_chunk = max(1, int(settings.sample_rate * settings.chunk_seconds))

    def capture_chunks(self) -> Iterator[np.ndarray]:
        loopback_mic = self._sc.get_microphone(self.capture_speaker.name, include_loopback=True)
        with loopback_mic.recorder(samplerate=self._settings.sample_rate, channels=1) as recorder:
            while True:
                data = recorder.record(numframes=self._frames_per_chunk)
                yield _mono_float32(data)


def _mono_float32(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data, dtype=np.float32)
    if array.ndim == 2:
        array = array.mean(axis=1)
    return np.ascontiguousarray(array, dtype=np.float32)
