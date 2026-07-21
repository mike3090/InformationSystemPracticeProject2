from __future__ import annotations

import io
import re
import socket
import time
import wave
from queue import Queue

import httpx
import numpy as np

from .audio_devices import select_speaker
from .config import Settings


class OpenAiTtsPlayer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._speaker = select_speaker(settings.tts_output_speaker)

    @property
    def output_device_name(self) -> str:
        return self._speaker.name

    async def speak(self, text: str) -> str:
        spoken_text = extract_spoken_text(text)
        if not spoken_text:
            return ""

        print(f"[TTS] synthesizing: {spoken_text}", flush=True)
        if self._settings.tts_streaming and self._settings.tts_response_format == "pcm":
            await self._stream_pcm(spoken_text)
        else:
            audio_bytes = await self._synthesize_audio(spoken_text)
            await _run_blocking(lambda: self._play_with_mic_control(audio_bytes, self._settings.tts_response_format))
        return spoken_text

    async def _synthesize_audio(self, text: str) -> bytes:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is empty, so TTS cannot run.")

        payload = {
            "model": self._settings.tts_model,
            "voice": self._settings.tts_voice,
            "input": text,
            "response_format": self._settings.tts_response_format,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                    json=payload,
                )
            except httpx.RequestError as exc:
                raise RuntimeError(f"Could not reach OpenAI TTS endpoint: {exc!r}") from exc

        if response.is_error:
            raise RuntimeError(
                f"OpenAI TTS returned HTTP {response.status_code}.\n"
                f"Response body:\n{response.text}"
            )
        return response.content

    async def _stream_pcm(self, text: str) -> None:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is empty, so TTS cannot run.")

        payload = {
            "model": self._settings.tts_model,
            "voice": self._settings.tts_voice,
            "input": text,
            "response_format": "pcm",
        }
        chunks: Queue[bytes | None] = Queue(maxsize=16)
        play_task = _start_blocking(lambda: self._play_pcm_stream_from_queue(chunks))
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                try:
                    async with client.stream(
                        "POST",
                        "https://api.openai.com/v1/audio/speech",
                        headers={"Authorization": f"Bearer {self._settings.openai_api_key}"},
                        json=payload,
                    ) as response:
                        if response.is_error:
                            body = await response.aread()
                            raise RuntimeError(
                                f"OpenAI TTS returned HTTP {response.status_code}.\n"
                                f"Response body:\n{body.decode('utf-8', errors='replace')}"
                            )
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                await _run_blocking(lambda chunk=chunk: chunks.put(chunk))
                except httpx.RequestError as exc:
                    raise RuntimeError(f"Could not reach OpenAI TTS endpoint: {exc!r}") from exc
        finally:
            await _run_blocking(lambda: chunks.put(None))
            await play_task

    def _play_wav(self, audio_bytes: bytes) -> None:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            raw = wav.readframes(wav.getnframes())

        audio = _decode_pcm(raw, sample_width)
        if channels > 1:
            audio = audio.reshape(-1, channels)
        self._speaker.play(audio, samplerate=sample_rate)

    def _play_with_mic_control(self, audio_bytes: bytes, response_format: str) -> None:
        mic_control = VrcVoiceInput(self._settings)
        mic_opened = False
        try:
            mic_opened = mic_control.open_for_tts()
            print(f"[TTS] playing on: {self.output_device_name}", flush=True)
            if response_format == "wav":
                self._play_wav(audio_bytes)
            elif response_format == "pcm":
                self._play_pcm(audio_bytes)
            else:
                raise RuntimeError(f"Unsupported non-streaming TTS response format: {response_format}")
            print("[TTS] playback finished", flush=True)
        finally:
            if mic_opened:
                mic_control.close_after_tts()

    def _play_pcm(self, audio_bytes: bytes) -> None:
        audio = _decode_pcm(audio_bytes[: len(audio_bytes) - (len(audio_bytes) % 2)], 2)
        self._speaker.play(audio, samplerate=24000)

    def _play_pcm_stream_from_queue(self, chunks: Queue[bytes | None]) -> None:
        mic_control = VrcVoiceInput(self._settings)
        mic_opened = False
        started = False
        leftover = b""
        try:
            with self._speaker.player(samplerate=24000, channels=1, blocksize=2048) as player:
                while True:
                    chunk = chunks.get()
                    if chunk is None:
                        break
                    if not chunk:
                        continue
                    if not started:
                        mic_opened = mic_control.open_for_tts()
                        print(f"[TTS] streaming on: {self.output_device_name}", flush=True)
                        started = True
                    data = leftover + chunk
                    usable_len = len(data) - (len(data) % 2)
                    leftover = data[usable_len:]
                    if usable_len:
                        player.play(_decode_pcm(data[:usable_len], 2))
            if started:
                print("[TTS] streaming playback finished", flush=True)
        finally:
            if mic_opened:
                mic_control.close_after_tts()


class VrcVoiceInput:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mode = settings.tts_vrchat_mic_control

    def open_for_tts(self) -> bool:
        if self._mode == "off":
            return False
        if self._mode == "toggle":
            print("[TTS] VRChat mic toggle: open", flush=True)
            self._tap_voice_button()
            self._sleep(self._settings.tts_mic_pre_delay_seconds)
            return True
        if self._mode == "hold":
            print("[TTS] VRChat mic hold: press", flush=True)
            self._send_voice(True)
            self._sleep(self._settings.tts_mic_pre_delay_seconds)
            return True
        raise RuntimeError(f"Unknown VRChat mic control mode: {self._mode}")

    def close_after_tts(self) -> None:
        self._sleep(self._settings.tts_mic_post_delay_seconds)
        if self._mode == "toggle":
            print("[TTS] VRChat mic toggle: close", flush=True)
            self._tap_voice_button()
        elif self._mode == "hold":
            print("[TTS] VRChat mic hold: release", flush=True)
            self._send_voice(False)

    def _tap_voice_button(self) -> None:
        self._send_voice(True)
        self._sleep(0.05)
        self._send_voice(False)

    def _send_voice(self, pressed: bool) -> None:
        packet = _osc_string("/input/Voice") + (b",T\0\0" if pressed else b",F\0\0")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, (self._settings.osc_host, self._settings.osc_port))

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


def extract_spoken_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    japanese_section = _extract_labeled_section(normalized, ("日本語", "Japanese"))
    if japanese_section:
        return _clean_spoken_lines(japanese_section)

    for marker in ("中文翻译", "中国語訳", "Chinese translation", "Translation"):
        index = normalized.casefold().find(marker.casefold())
        if index > 0:
            normalized = normalized[:index].strip()
            break

    return _clean_spoken_lines(normalized)


def _extract_labeled_section(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    next_label_pattern = "|".join(
        re.escape(label)
        for label in (
            "中文翻译",
            "中国語訳",
            "Chinese translation",
            "Translation",
            "English",
            "英語",
            "中国語",
            "中文",
        )
    )
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:{label_pattern})\s*[:：]\s*(.*?)(?=\n\s*(?:{next_label_pattern})\s*[:：]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _clean_spoken_lines(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.rstrip(":：").casefold() in {"日本語", "japanese"}:
            continue
        line = re.sub(r"^(日本語|japanese)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
        line = _strip_parenthetical_translations(line)
        lines.append(line.strip("「」\"' "))
    return " ".join(lines).strip()


def _strip_parenthetical_translations(text: str) -> str:
    text = re.sub(r"\s*[（(]([^（）()]*)[）)]", _drop_english_parentheses, text)
    return " ".join(text.split()).strip()


def _drop_english_parentheses(match: re.Match[str]) -> str:
    content = match.group(1)
    ascii_letters = sum(char.isascii() and char.isalpha() for char in content)
    japanese_chars = sum(_is_japanese_char(char) for char in content)
    if ascii_letters > 0 and ascii_letters >= japanese_chars:
        return ""
    return match.group(0)


def _is_japanese_char(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x3040 <= codepoint <= 0x30FF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
    )


def _decode_pcm(raw: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        return (data - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    raise RuntimeError(f"Unsupported TTS wav sample width: {sample_width}")


def _osc_string(value: str) -> bytes:
    data = value.encode("utf-8") + b"\0"
    padding = (4 - (len(data) % 4)) % 4
    return data + (b"\0" * padding)


async def _run_blocking(func) -> None:
    import asyncio

    await asyncio.to_thread(func)


def _start_blocking(func):
    import asyncio

    return asyncio.create_task(asyncio.to_thread(func))
