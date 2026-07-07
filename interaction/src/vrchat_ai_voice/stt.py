from __future__ import annotations

import numpy as np

from .config import Settings


class WhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed. Run scripts/setup.ps1 first.") from exc

        self._settings = settings
        self._model = WhisperModel(settings.transcribe_model, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1:
            audio = audio.reshape(-1)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 1.0:
            audio = audio / peak

        segments, _info = self._model.transcribe(
            audio,
            language=self._settings.transcribe_language,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip()
