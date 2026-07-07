from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def _load_system_prompt(default_prompt: str) -> str:
    prompt_file = _optional(os.getenv("VRCHAT_AI_SYSTEM_PROMPT_FILE"))
    if prompt_file:
        path = Path(prompt_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"System prompt file was not found: {path}")
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"System prompt file is empty: {path}")
        return content
    return os.getenv("VRCHAT_AI_SYSTEM_PROMPT", default_prompt)


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    host: str
    port: int
    server_url: str
    capture_speaker: str | None
    transcribe_model: str
    transcribe_language: str | None
    sample_rate: int
    chunk_seconds: float
    rms_threshold: float
    min_segment_seconds: float
    silence_seconds: float
    max_segment_seconds: float
    text_output: str
    transcript_path: Path
    osc_host: str
    osc_port: int
    osc_send_immediately: bool
    system_prompt: str
    tmp_dir: Path


def load_settings() -> Settings:
    load_dotenv()
    default_system_prompt = (
        "You are a friendly AI companion in VRChat. "
        "Reply briefly and naturally for an in-world chatbox."
    )
    tmp_dir = Path(os.getenv("VRCHAT_AI_TMP_DIR", ".tmp")).resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    hf_home = Path(os.getenv("HF_HOME", ".cache/huggingface")).resolve()
    hf_home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        host=os.getenv("VRCHAT_AI_HOST", "127.0.0.1"),
        port=_get_int("VRCHAT_AI_PORT", 8765),
        server_url=os.getenv("VRCHAT_AI_SERVER_URL", "http://127.0.0.1:8765").rstrip("/"),
        capture_speaker=_optional(os.getenv("VRCHAT_AI_CAPTURE_SPEAKER")),
        transcribe_model=os.getenv("VRCHAT_AI_TRANSCRIBE_MODEL", "base"),
        transcribe_language=_optional(os.getenv("VRCHAT_AI_TRANSCRIBE_LANGUAGE")),
        sample_rate=_get_int("VRCHAT_AI_SAMPLE_RATE", 16000),
        chunk_seconds=_get_float("VRCHAT_AI_CHUNK_SECONDS", 0.25),
        rms_threshold=_get_float("VRCHAT_AI_RMS_THRESHOLD", 0.012),
        min_segment_seconds=_get_float("VRCHAT_AI_MIN_SEGMENT_SECONDS", 0.8),
        silence_seconds=_get_float("VRCHAT_AI_SILENCE_SECONDS", 0.9),
        max_segment_seconds=_get_float("VRCHAT_AI_MAX_SEGMENT_SECONDS", 12.0),
        text_output=os.getenv("VRCHAT_AI_TEXT_OUTPUT", "console,file"),
        transcript_path=Path(os.getenv("VRCHAT_AI_TRANSCRIPT_PATH", str(tmp_dir / "transcript.log"))).resolve(),
        osc_host=os.getenv("VRCHAT_AI_OSC_HOST", "127.0.0.1"),
        osc_port=_get_int("VRCHAT_AI_OSC_PORT", 9000),
        osc_send_immediately=_get_bool("VRCHAT_AI_OSC_SEND_IMMEDIATELY", True),
        system_prompt=_load_system_prompt(default_system_prompt),
        tmp_dir=tmp_dir,
    )
