from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, unquote, urlparse
import argparse
import json
import os
import re
import sys
import time
import traceback


HOST = os.getenv("STORE_CLERK_VOICE_HOST", "127.0.0.1")
PORT = int(os.getenv("STORE_CLERK_VOICE_PORT", "8765"))

SESSION_LOCK = Lock()
SESSIONS = {
    "default": {
        "version": 0,
        "choice": -1,
        "transcript": "",
        "confidence": 0.0,
    }
}


CHOICE_RULES = [
    (
        0,
        [
            "唐揚げ",
            "からあげ",
            "弁当",
            "温めて",
            "温め",
            "袋はいりません",
            "いりません",
            "suica",
            "スイカ",
            "もう一度",
            "練習",
        ],
    ),
    (
        1,
        [
            "コーヒー",
            "珈琲",
            "現金",
            "袋をお願いします",
            "袋お願いします",
            "ありがとうございます",
            "他の商品",
            "そのまま",
            "大丈夫です",
        ],
    ),
    (
        2,
        [
            "atm",
            "エーティーエム",
            "袋も",
            "箸",
            "はし",
            "クレジット",
            "終了",
            "ありません",
            "最初に戻る",
            "最初に戻ります",
        ],
    ),
]


def env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


@dataclass(frozen=True)
class WhisperSettings:
    microphone: str | None
    model: str
    device: str
    compute_type: str
    language: str
    sample_rate: int
    chunk_seconds: float
    rms_threshold: float
    min_segment_seconds: float
    silence_seconds: float
    max_segment_seconds: float

    @classmethod
    def from_environment(cls) -> "WhisperSettings":
        microphone = os.getenv(
            "STORE_CLERK_CAPTURE_MICROPHONE",
            os.getenv("VRCHAT_AI_CAPTURE_MICROPHONE", ""),
        ).strip()
        return cls(
            microphone=microphone or None,
            model=os.getenv("STORE_CLERK_WHISPER_MODEL", "base").strip() or "base",
            device=os.getenv("STORE_CLERK_WHISPER_DEVICE", "cpu").strip() or "cpu",
            compute_type=os.getenv("STORE_CLERK_WHISPER_COMPUTE_TYPE", "int8").strip() or "int8",
            language=os.getenv("STORE_CLERK_WHISPER_LANGUAGE", "ja").strip() or "ja",
            sample_rate=env_int("STORE_CLERK_SAMPLE_RATE", 16000),
            chunk_seconds=env_float("STORE_CLERK_CHUNK_SECONDS", 0.25),
            rms_threshold=env_float("STORE_CLERK_RMS_THRESHOLD", 0.012),
            min_segment_seconds=env_float("STORE_CLERK_MIN_SEGMENT_SECONDS", 0.8),
            silence_seconds=env_float("STORE_CLERK_SILENCE_SECONDS", 0.9),
            max_segment_seconds=env_float("STORE_CLERK_MAX_SEGMENT_SECONDS", 12.0),
        )


def configure_huggingface_cache() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    cache_root = Path(
        os.getenv("HF_HOME", str(project_root / ".cache" / "huggingface"))
    ).expanduser().resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_root))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_root / "hub"))
    return cache_root


def import_audio_dependencies():
    try:
        import numpy as np
        import soundcard as sc
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Whisper dependencies are missing. Run setup_whisper.ps1 first."
        ) from exc
    return np, sc, WhisperModel


def normalize(text: str) -> str:
    text = text.strip().lower().replace("　", " ")
    return re.sub(r"[。．、，！？!?「」『』（）()［］\[\]\s]+", "", text)


def match_choice(transcript: str) -> tuple[int, float]:
    normalized = normalize(transcript)
    if not normalized:
        return -1, 0.0

    best_choice = -1
    best_score = 0
    for choice, keywords in CHOICE_RULES:
        score = sum(
            len(normalize(keyword))
            for keyword in keywords
            if normalize(keyword) in normalized
        )
        if score > best_score:
            best_choice = choice
            best_score = score

    if best_choice < 0:
        return -1, 0.0
    return best_choice, min(0.99, 0.55 + best_score / 20.0)


def update_session(
    session_id: str,
    transcript: str,
    forced_choice: int | None = None,
) -> dict:
    choice, confidence = (
        match_choice(transcript)
        if forced_choice is None
        else (forced_choice, 1.0)
    )
    with SESSION_LOCK:
        state = SESSIONS.setdefault(session_id, {})
        state.update(
            version=time.time_ns(),
            choice=choice,
            transcript=transcript,
            confidence=confidence,
        )
        return dict(state)


def get_session(session_id: str) -> dict:
    with SESSION_LOCK:
        state = SESSIONS.setdefault(
            session_id,
            {"version": 0, "choice": -1, "transcript": "", "confidence": 0.0},
        )
        return dict(state)


def payload_for(state: dict) -> str:
    transcript = str(state["transcript"]).replace("|", " ").replace("\r", " ").replace("\n", " ")
    return f'{state["version"]}|{state["choice"]}|{transcript}|{state["confidence"]:.2f}'


def select_microphone(sc, name_fragment: str | None):
    if not name_fragment:
        microphone = sc.default_microphone()
        if microphone is None:
            raise RuntimeError("Windows has no default recording microphone.")
        return microphone

    microphones = sc.all_microphones(include_loopback=False)
    fragment = name_fragment.casefold()
    matches = [mic for mic in microphones if fragment in mic.name.casefold()]
    if not matches:
        available = "\n".join(f"- {mic.name}" for mic in microphones)
        raise RuntimeError(
            f"Microphone matching '{name_fragment}' was not found.\n"
            f"Available microphones:\n{available}"
        )
    return matches[0]


def print_devices() -> None:
    _np, sc, _model = import_audio_dependencies()
    default = sc.default_microphone()
    for microphone in sc.all_microphones(include_loopback=False):
        marker = " default" if default and microphone.name == default.name else ""
        print(f"[microphone{marker}] {microphone.name}")


class RmsSegmenter:
    def __init__(self, settings: WhisperSettings) -> None:
        self._np, _sc, _model = import_audio_dependencies()
        self.threshold = settings.rms_threshold
        self.min_samples = int(settings.sample_rate * settings.min_segment_seconds)
        self.silence_samples = int(settings.sample_rate * settings.silence_seconds)
        self.max_samples = int(settings.sample_rate * settings.max_segment_seconds)
        self.buffer = []
        self.silence_seen = 0
        self.active = False

    def push(self, chunk):
        chunk = self._np.asarray(chunk, dtype=self._np.float32).reshape(-1)
        rms = float(self._np.sqrt(self._np.mean(self._np.square(chunk)))) if chunk.size else 0.0
        is_speech = rms >= self.threshold
        if is_speech and not self.active:
            self.active = True
            self.silence_seen = 0
        if not self.active:
            return []

        self.buffer.append(chunk)
        self.silence_seen = 0 if is_speech else self.silence_seen + len(chunk)
        total = sum(len(part) for part in self.buffer)
        if self.silence_seen < self.silence_samples and total < self.max_samples:
            return []

        segment = self._np.concatenate(self.buffer).astype(self._np.float32, copy=False)
        self.buffer.clear()
        self.silence_seen = 0
        self.active = False
        return [segment] if len(segment) >= self.min_samples else []


class WhisperListener:
    def __init__(self, settings: WhisperSettings) -> None:
        self.settings = settings
        self.np, self.sc, whisper_model = import_audio_dependencies()
        self.microphone = select_microphone(self.sc, settings.microphone)
        try:
            self.model = whisper_model(
                settings.model,
                device=settings.device,
                compute_type=settings.compute_type,
            )
            model_label = f"{settings.device}/{settings.compute_type}"
        except Exception as exc:
            if settings.device == "cpu":
                raise
            print(
                f"[WARN] Whisper failed on {settings.device}/{settings.compute_type}: {exc}",
                flush=True,
            )
            print("[WARN] Falling back to cpu/int8", flush=True)
            self.model = whisper_model(settings.model, device="cpu", compute_type="int8")
            model_label = "cpu/int8 fallback"
        self.segmenter = RmsSegmenter(settings)
        self.frames_per_chunk = max(1, int(settings.sample_rate * settings.chunk_seconds))
        print(f"[AUDIO] microphone: {self.microphone.name}", flush=True)
        print(f"[STT] model: {settings.model} ({model_label}), language={settings.language}", flush=True)

    def run_forever(self) -> None:
        try:
            with self.microphone.recorder(
                samplerate=self.settings.sample_rate,
                channels=1,
            ) as recorder:
                print("[AUDIO] listening", flush=True)
                while True:
                    data = recorder.record(numframes=self.frames_per_chunk)
                    audio = self.np.asarray(data, dtype=self.np.float32)
                    if audio.ndim == 2:
                        audio = audio.mean(axis=1)
                    for segment in self.segmenter.push(audio):
                        self.transcribe(segment)
        except Exception:
            print("[ERROR] microphone capture stopped:", flush=True)
            traceback.print_exc()

    def transcribe(self, audio) -> None:
        try:
            segments, info = self.model.transcribe(
                audio,
                language=self.settings.language,
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments).strip()
            if not text:
                print("[STT] empty transcription", flush=True)
                return
            choice, _confidence = match_choice(text)
            language = getattr(info, "language", self.settings.language)
            print(f"[STT] ({language}) {text}", flush=True)
            print(f"[MATCH] choice={choice}", flush=True)
            update_session("default", text)
        except Exception:
            print("[ERROR] transcription failed:", flush=True)
            traceback.print_exc()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path == "/":
            self.send_html()
            return

        if len(parts) >= 3 and parts[0] == "session":
            session_id, action = parts[1], parts[2]
            query = parse_qs(parsed.query)
            if action == "latest":
                self.send_text(payload_for(get_session(session_id)))
                return
            if action == "simulate":
                transcript = unquote(query.get("text", [""])[0])
                self.send_text(payload_for(update_session(session_id, transcript)))
                return
            if action == "choice":
                transcript = unquote(query.get("text", ["manual choice"])[0])
                try:
                    choice = int(query.get("choice", ["-1"])[0])
                except ValueError:
                    choice = -1
                self.send_text(payload_for(update_session(session_id, transcript, choice)))
                return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 3 or parts[0] != "session":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        transcript = ""
        forced_choice = None
        if "application/json" in self.headers.get("Content-Type", "") and raw:
            body = json.loads(raw)
            transcript = str(body.get("text", ""))
            forced_choice = int(body["choice"]) if "choice" in body else None
        elif raw:
            fields = parse_qs(raw)
            transcript = fields.get("text", [raw])[0]
            forced_choice = int(fields["choice"][0]) if "choice" in fields else None

        session_id, action = parts[1], parts[2]
        if action == "transcript":
            self.send_text(payload_for(update_session(session_id, transcript)))
            return
        if action == "choice":
            choice = forced_choice if forced_choice is not None else -1
            self.send_text(payload_for(update_session(session_id, transcript, choice)))
            return
        self.send_response(404)
        self.end_headers()

    def send_text(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def send_html(self) -> None:
        body = """<!doctype html>
<meta charset="utf-8">
<title>Store Clerk Whisper Service</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 760px; margin: 32px auto; line-height: 1.5; }
input { padding: 8px; width: 420px; } button { padding: 8px 12px; }
code, pre { background: #f3f3f3; padding: 3px 5px; }
</style>
<h1>Store Clerk Whisper Service</h1>
<p>Local faster-whisper microphone recognition is running in the Python process.</p>
<p>Unity polls <code>/session/default/latest</code>.</p>
<p>Latest payload:</p><pre id="payload">loading...</pre>
<h2>Manual fallback</h2>
<form action="/session/default/simulate" method="get">
  <input name="text" value="唐揚げ弁当を探しています">
  <button type="submit">Submit transcript</button>
</form>
<script>
async function refresh() {
  const response = await fetch('/session/default/latest');
  document.getElementById('payload').textContent = await response.text();
}
refresh(); setInterval(refresh, 1000);
</script>"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        print(f"[HTTP] {self.address_string()} {format % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local faster-whisper service for the store clerk dialogue")
    parser.add_argument("--list-devices", action="store_true", help="list physical microphones and exit")
    parser.add_argument("--no-microphone", action="store_true", help="run HTTP/manual test mode only")
    args = parser.parse_args()

    configure_huggingface_cache()
    if args.list_devices:
        print_devices()
        return

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    if not args.no_microphone:
        listener = WhisperListener(WhisperSettings.from_environment())
        Thread(target=listener.run_forever, name="whisper-listener", daemon=True).start()

    print(f"[HTTP] voice choice server: http://{HOST}:{PORT}", flush=True)
    print(f"[HTTP] Unity endpoint: http://{HOST}:{PORT}/session/default/latest", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] voice choice server stopped", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[FATAL] voice service failed to start:", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise
