from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import Settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None
    language_probability: float | None
    rejected_reason: str | None = None


class WhisperTranscriber:
    def __init__(self, settings: Settings) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed. Run scripts/setup.ps1 first.") from exc

        self._settings = settings
        try:
            self._model = WhisperModel(
                settings.transcribe_model,
                device=settings.transcribe_device,
                compute_type=settings.transcribe_compute_type,
            )
            print(
                f"STT model: {settings.transcribe_model} "
                f"device={settings.transcribe_device} compute_type={settings.transcribe_compute_type}",
                flush=True,
            )
        except Exception as exc:
            if settings.transcribe_device == "cpu":
                raise
            print(
                f"[WARN] STT failed to initialize on {settings.transcribe_device}/"
                f"{settings.transcribe_compute_type}: {exc}. Falling back to cpu/int8.",
                flush=True,
            )
            self._model = WhisperModel(settings.transcribe_model, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
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
        language = _normalize_language(getattr(_info, "language", None) or self._settings.transcribe_language)
        language_probability = getattr(_info, "language_probability", None)
        allowed_languages = self._settings.transcribe_allowed_languages
        if allowed_languages and language and language not in allowed_languages:
            return TranscriptionResult(
                text="",
                language=language,
                language_probability=language_probability,
                rejected_reason=f"language '{language}' is not allowed",
            )

        text = "".join(segment.text for segment in segments).strip()
        return TranscriptionResult(text=text, language=language, language_probability=language_probability)


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None
    language = language.strip().casefold()
    aliases = {
        "jp": "ja",
        "jpn": "ja",
        "japanese": "ja",
        "cn": "zh",
        "chi": "zh",
        "chinese": "zh",
        "mandarin": "zh",
        "eng": "en",
        "english": "en",
    }
    return aliases.get(language, language)
