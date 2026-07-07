from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import Settings


class TextSink:
    def send(self, text: str) -> None:
        raise NotImplementedError


class ConsoleSink(TextSink):
    def send(self, text: str) -> None:
        print(f"AI: {text}")


@dataclass
class FileSink(TextSink):
    path: Path

    def send(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] AI: {text}\n")
            handle.flush()


@dataclass
class VrchatChatboxSink(TextSink):
    host: str
    port: int
    send_immediately: bool = True

    def send(self, text: str) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            for chunk in _split_chatbox_text(text):
                packet = _osc_packet("/chatbox/input", chunk, self.send_immediately, False)
                sock.sendto(packet, (self.host, self.port))


class MultiSink(TextSink):
    def __init__(self, sinks: list[TextSink]) -> None:
        self._sinks = sinks

    def send(self, text: str) -> None:
        for sink in self._sinks:
            sink.send(text)


def build_text_sink(settings: Settings) -> TextSink:
    names = {item.strip().casefold() for item in settings.text_output.split(",") if item.strip()}
    if not names:
        names = {"console"}

    sinks: list[TextSink] = []
    if "console" in names:
        sinks.append(ConsoleSink())
    if "file" in names:
        sinks.append(FileSink(settings.transcript_path))
    if "osc" in names or "chatbox" in names:
        sinks.append(VrchatChatboxSink(settings.osc_host, settings.osc_port, settings.osc_send_immediately))

    unknown = names - {"console", "file", "osc", "chatbox"}
    if unknown:
        raise RuntimeError(f"Unknown VRCHAT_AI_TEXT_OUTPUT value: {', '.join(sorted(unknown))}")
    if not sinks:
        raise RuntimeError("No text output target configured.")
    return MultiSink(sinks)


def _split_chatbox_text(text: str, limit: int = 130) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return chunks


def _osc_packet(address: str, text: str, send_immediately: bool, play_notification: bool) -> bytes:
    bool_tags = ("T" if send_immediately else "F") + ("T" if play_notification else "F")
    return (
        _osc_string(address)
        + _osc_string(f",s{bool_tags}")
        + _osc_string(text)
    )


def _osc_string(value: str) -> bytes:
    data = value.encode("utf-8") + b"\0"
    padding = (4 - (len(data) % 4)) % 4
    return data + (b"\0" * padding)
