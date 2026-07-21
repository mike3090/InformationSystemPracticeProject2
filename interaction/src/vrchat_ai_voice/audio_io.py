from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from .audio_devices import select_microphone, select_speaker
from .config import Settings


class AudioBridge:
    def __init__(self, settings: Settings) -> None:
        try:
            import soundcard as sc
        except ImportError as exc:
            raise RuntimeError("soundcard is not installed. Run scripts/setup.ps1 first.") from exc

        self._sc = sc
        self._settings = settings
        self.capture_mode = settings.capture_mode
        if self.capture_mode == "speaker":
            self.capture_device = select_speaker(settings.capture_speaker)
            self.capture_source_label = "speaker loopback"
        elif self.capture_mode == "microphone":
            self.capture_device = select_microphone(settings.capture_microphone)
            self.capture_source_label = "microphone"
        else:
            raise ValueError(f"Unknown capture mode: {self.capture_mode}")
        self._frames_per_chunk = max(1, int(settings.sample_rate * settings.chunk_seconds))

    def capture_chunks(self) -> Iterator[np.ndarray]:
        if self.capture_mode == "speaker":
            capture_source = self._sc.get_microphone(self.capture_device.name, include_loopback=True)
        else:
            capture_source = self.capture_device
        with capture_source.recorder(samplerate=self._settings.sample_rate, channels=1) as recorder:
            while True:
                data = recorder.record(numframes=self._frames_per_chunk)
                yield _mono_float32(data)


def _mono_float32(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data, dtype=np.float32)
    if array.ndim == 2:
        array = array.mean(axis=1)
    return np.ascontiguousarray(array, dtype=np.float32)
