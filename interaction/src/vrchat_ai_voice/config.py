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


def _get_capture_mode() -> str:
    mode = os.getenv("VRCHAT_AI_CAPTURE_MODE", "speaker").strip().casefold()
    if mode not in {"speaker", "microphone"}:
        raise ValueError("VRCHAT_AI_CAPTURE_MODE must be either 'speaker' or 'microphone'.")
    return mode


def _get_csv_set(name: str, default: str) -> set[str]:
    raw = os.getenv(name, default)
    return {item.strip().casefold() for item in raw.split(",") if item.strip()}


def _get_tts_mic_control_mode() -> str:
    mode = os.getenv("VRCHAT_AI_TTS_VRCHAT_MIC_CONTROL", "off").strip().casefold()
    if mode not in {"off", "toggle", "hold"}:
        raise ValueError("VRCHAT_AI_TTS_VRCHAT_MIC_CONTROL must be 'off', 'toggle', or 'hold'.")
    return mode


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
    capture_mode: str
    capture_speaker: str | None
    capture_microphone: str | None
    transcribe_model: str
    transcribe_device: str
    transcribe_compute_type: str
    transcribe_language: str | None
    transcribe_allowed_languages: set[str]
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
    tts_enabled: bool
    tts_model: str
    tts_voice: str
    tts_output_speaker: str | None
    tts_response_format: str
    tts_streaming: bool
    tts_vrchat_mic_control: str
    tts_mic_pre_delay_seconds: float
    tts_mic_post_delay_seconds: float
    post_tts_cooldown_seconds: float
    tts_echo_similarity: float
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
        capture_mode=_get_capture_mode(),
        capture_speaker=_optional(os.getenv("VRCHAT_AI_CAPTURE_SPEAKER")),
        capture_microphone=_optional(os.getenv("VRCHAT_AI_CAPTURE_MICROPHONE")),
        transcribe_model=os.getenv("VRCHAT_AI_TRANSCRIBE_MODEL", "base"),
        transcribe_device=os.getenv("VRCHAT_AI_TRANSCRIBE_DEVICE", "cpu"),
        transcribe_compute_type=os.getenv("VRCHAT_AI_TRANSCRIBE_COMPUTE_TYPE", "int8"),
        transcribe_language=_optional(os.getenv("VRCHAT_AI_TRANSCRIBE_LANGUAGE")),
        transcribe_allowed_languages=_get_csv_set("VRCHAT_AI_TRANSCRIBE_ALLOWED_LANGUAGES", "ja,zh,en"),
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
        tts_enabled=_get_bool("VRCHAT_AI_TTS_ENABLED", False),
        tts_model=os.getenv("VRCHAT_AI_TTS_MODEL", "tts-1"),
        tts_voice=os.getenv("VRCHAT_AI_TTS_VOICE", "alloy"),
        tts_output_speaker=_optional(os.getenv("VRCHAT_AI_TTS_OUTPUT_SPEAKER")),
        tts_response_format=os.getenv("VRCHAT_AI_TTS_RESPONSE_FORMAT", "pcm").strip().casefold(),
        tts_streaming=_get_bool("VRCHAT_AI_TTS_STREAMING", True),
        tts_vrchat_mic_control=_get_tts_mic_control_mode(),
        tts_mic_pre_delay_seconds=_get_float("VRCHAT_AI_TTS_MIC_PRE_DELAY_SECONDS", 0.15),
        tts_mic_post_delay_seconds=_get_float("VRCHAT_AI_TTS_MIC_POST_DELAY_SECONDS", 0.25),
        post_tts_cooldown_seconds=_get_float("VRCHAT_AI_POST_TTS_COOLDOWN_SECONDS", 1.0),
        tts_echo_similarity=_get_float("VRCHAT_AI_TTS_ECHO_SIMILARITY", 0.82),
        system_prompt=_load_system_prompt(default_system_prompt),
        tmp_dir=tmp_dir,
    )
