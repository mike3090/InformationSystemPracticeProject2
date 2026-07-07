from __future__ import annotations

import asyncio
import warnings
from collections import deque
from datetime import datetime

from httpx import HTTPError

from .audio_io import AudioBridge
from .config import Settings
from .llm_client import LocalChatClient
from .schemas import ChatMessage
from .stt import WhisperTranscriber
from .text_output import TextSink, build_text_sink
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
    history: deque[ChatMessage] = deque(maxlen=8)

    print(f"Capture speaker: {bridge.capture_speaker.name}")
    print(f"Text output: {settings.text_output}")
    print(f"Transcript log: {settings.transcript_path}")
    print("Listening. Press Ctrl+C to stop.")
    _append_transcript(settings, "SYSTEM", "Listening started.")

    for chunk in bridge.capture_chunks():
        for segment in segmenter.push(chunk):
            await _handle_segment(segment, settings, transcriber, chat_client, text_sink, history)
        await asyncio.sleep(0)


async def _handle_segment(
    segment,
    settings: Settings,
    transcriber: WhisperTranscriber,
    chat_client: LocalChatClient,
    text_sink: TextSink,
    history: deque[ChatMessage],
) -> None:
    text = transcriber.transcribe(segment)
    if len(text) < 2:
        return

    print(f"Other player: {text}")
    _append_transcript(settings, "Other player", text)
    try:
        reply = await chat_client.ask(text, list(history))
    except HTTPError as exc:
        print(f"LLM request failed: {exc}")
        return

    if not reply:
        return

    text_sink.send(reply)
    history.append(ChatMessage(role="user", content=text))
    history.append(ChatMessage(role="assistant", content=reply))


def _append_transcript(settings: Settings, speaker: str, text: str) -> None:
    settings.transcript_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with settings.transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {speaker}: {text}\n")
        handle.flush()
