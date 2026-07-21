from __future__ import annotations

import asyncio
import re
import traceback
import warnings
from collections import deque
from datetime import datetime
from difflib import SequenceMatcher

from .audio_io import AudioBridge
from .config import Settings
from .llm_client import LocalChatClient
from .schemas import ChatMessage
from .stt import WhisperTranscriber
from .text_output import TextSink, build_text_sink
from .tts import OpenAiTtsPlayer
from .vad import RmsSegmenter


async def run_voice_bridge(settings: Settings) -> None:
    try:
        from soundcard.mediafoundation import SoundcardRuntimeWarning

        warnings.filterwarnings("ignore", category=SoundcardRuntimeWarning)
    except Exception:
        warnings.filterwarnings("ignore", message=".*data discontinuity in recording.*")
    bridge = AudioBridge(settings)
    segmenter = RmsSegmenter(
        sample_rate=settings.sample_rate,
        threshold=settings.rms_threshold,
        min_segment_seconds=settings.min_segment_seconds,
        silence_seconds=settings.silence_seconds,
        max_segment_seconds=settings.max_segment_seconds,
    )
    transcriber = WhisperTranscriber(settings)
    chat_client = LocalChatClient(settings)
    text_sink = build_text_sink(settings)
    tts_player = OpenAiTtsPlayer(settings) if settings.tts_enabled else None
    history: deque[ChatMessage] = deque(maxlen=8)
    recent_tts_texts: deque[str] = deque(maxlen=3)

    print(f"Capture mode: {bridge.capture_source_label}", flush=True)
    print(f"Capture device: {bridge.capture_device.name}", flush=True)
    print(f"Text output: {settings.text_output}", flush=True)
    if tts_player:
        print(f"TTS output: {tts_player.output_device_name}", flush=True)
        print("TTS voice path: audio device output, not OSC microphone audio", flush=True)
    else:
        print("TTS output: disabled", flush=True)
    print(f"STT allowed languages: {', '.join(sorted(settings.transcribe_allowed_languages))}", flush=True)
    print(f"Transcript log: {settings.transcript_path}", flush=True)
    print("Listening. Press Ctrl+C to stop.", flush=True)
    _append_transcript(settings, "SYSTEM", "Listening started.")

    for chunk in bridge.capture_chunks():
        for segment in segmenter.push(chunk):
            await _handle_segment(
                segment,
                settings,
                transcriber,
                chat_client,
                text_sink,
                tts_player,
                segmenter,
                history,
                recent_tts_texts,
            )
        await asyncio.sleep(0)


async def _handle_segment(
    segment,
    settings: Settings,
    transcriber: WhisperTranscriber,
    chat_client: LocalChatClient,
    text_sink: TextSink,
    tts_player: OpenAiTtsPlayer | None,
    segmenter: RmsSegmenter,
    history: deque[ChatMessage],
    recent_tts_texts: deque[str],
) -> None:
    try:
        transcription = transcriber.transcribe(segment)
    except Exception as exc:
        _print_exception("STT transcription failed", exc)
        return

    if transcription.rejected_reason:
        probability = _format_probability(transcription.language_probability)
        print(
            f"[STT] ignored {transcription.rejected_reason}"
            f" probability={probability}",
            flush=True,
        )
        _append_transcript(
            settings,
            "SYSTEM",
            f"Ignored STT segment: {transcription.rejected_reason} probability={probability}",
        )
        return

    text = transcription.text
    if len(text) < 2:
        return

    if _is_probable_tts_echo(text, recent_tts_texts, settings.tts_echo_similarity):
        print(f"[STT] ignored probable TTS echo: {text}", flush=True)
        _append_transcript(settings, "SYSTEM", f"Ignored probable TTS echo: {text}")
        return

    probability = _format_probability(transcription.language_probability)
    language = transcription.language or "unknown"
    print(f"[STT] Other player ({language}, p={probability}): {text}", flush=True)
    _append_transcript(settings, "Other player", text)
    try:
        reply = await chat_client.ask(text, list(history))
    except Exception as exc:
        _print_exception("LLM request failed", exc)
        return

    if not reply.display_text:
        return

    try:
        text_sink.send(reply.display_text)
    except Exception as exc:
        _print_exception("Text output failed", exc)
        return

    history.append(ChatMessage(role="user", content=text))
    history.append(ChatMessage(role="assistant", content=reply.display_text))

    if tts_player:
        segmenter.reset()
        try:
            spoken_text = await tts_player.speak(reply.spoken_text)
        except Exception as exc:
            _print_exception("TTS failed", exc)
            return
        if spoken_text:
            recent_tts_texts.append(spoken_text)
        if settings.post_tts_cooldown_seconds > 0:
            print(f"[TTS] cooldown: {settings.post_tts_cooldown_seconds:.1f}s", flush=True)
            await asyncio.sleep(settings.post_tts_cooldown_seconds)
            segmenter.reset()


def _append_transcript(settings: Settings, speaker: str, text: str) -> None:
    settings.transcript_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with settings.transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {speaker}: {text}\n")
        handle.flush()


def _print_exception(label: str, exc: BaseException) -> None:
    print(f"[ERROR] {label}: {exc}", flush=True)
    traceback.print_exception(type(exc), exc, exc.__traceback__)


def _is_probable_tts_echo(text: str, recent_tts_texts: deque[str], threshold: float) -> bool:
    normalized_text = _normalize_for_echo(text)
    if len(normalized_text) < 6:
        return False

    for recent in recent_tts_texts:
        normalized_recent = _normalize_for_echo(recent)
        if len(normalized_recent) < 6:
            continue
        shorter, longer = sorted((normalized_text, normalized_recent), key=len)
        if len(shorter) >= 8 and shorter in longer:
            return True
        ratio = SequenceMatcher(None, normalized_text, normalized_recent).ratio()
        if ratio >= threshold:
            return True
    return False


def _normalize_for_echo(text: str) -> str:
    return re.sub(r"\W+", "", text.casefold())


def _format_probability(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
