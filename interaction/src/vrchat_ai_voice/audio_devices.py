from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceSummary:
    kind: str
    name: str
    id: str
    is_default: bool


def _soundcard():
    try:
        import soundcard as sc
    except ImportError as exc:
        raise RuntimeError("soundcard is not installed. Run scripts/setup.ps1 first.") from exc
    return sc


def list_devices() -> list[DeviceSummary]:
    sc = _soundcard()
    default_speaker = sc.default_speaker()
    default_microphone = sc.default_microphone()

    devices: list[DeviceSummary] = []
    for speaker in sc.all_speakers():
        devices.append(
            DeviceSummary(
                kind="speaker",
                name=speaker.name,
                id=str(speaker.id),
                is_default=speaker.name == default_speaker.name,
            )
        )
    for microphone in sc.all_microphones(include_loopback=True):
        devices.append(
            DeviceSummary(
                kind="microphone",
                name=microphone.name,
                id=str(microphone.id),
                is_default=microphone.name == default_microphone.name,
            )
        )
    return devices


def select_speaker(name_fragment: str | None):
    sc = _soundcard()
    if not name_fragment:
        return sc.default_speaker()

    fragment = name_fragment.casefold()
    speakers = sc.all_speakers()
    matches = [speaker for speaker in speakers if fragment in speaker.name.casefold()]
    if not matches:
        available = "\n".join(f"- {speaker.name}" for speaker in speakers)
        raise RuntimeError(f"Speaker matching '{name_fragment}' was not found.\nAvailable speakers:\n{available}")
    return matches[0]


def select_microphone(name_fragment: str | None):
    sc = _soundcard()
    if not name_fragment:
        return sc.default_microphone()

    fragment = name_fragment.casefold()
    microphones = sc.all_microphones(include_loopback=False)
    matches = [microphone for microphone in microphones if fragment in microphone.name.casefold()]
    if not matches:
        available = "\n".join(f"- {microphone.name}" for microphone in microphones)
        raise RuntimeError(f"Microphone matching '{name_fragment}' was not found.\nAvailable microphones:\n{available}")
    return matches[0]


def print_devices() -> None:
    for device in list_devices():
        default_marker = " default" if device.is_default else ""
        print(f"[{device.kind}{default_marker}] {device.name}")
