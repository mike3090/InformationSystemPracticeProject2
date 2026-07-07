from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time

from .audio_devices import print_devices
from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vrchat-ai-voice")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("devices", help="List Windows audio playback and recording devices.")
    subparsers.add_parser("server", help="Start the local OpenAI chat server.")
    subparsers.add_parser("run", help="Run the VRChat STT -> LLM -> text bridge.")
    subparsers.add_parser("all", help="Start the local OpenAI server and the text bridge in one process.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    settings = load_settings()

    if args.command == "devices":
        print_devices()
        return 0

    if args.command == "server":
        from .openai_server import main as server_main

        server_main()
        return 0

    if args.command == "run":
        from .pipeline import run_voice_bridge

        asyncio.run(run_voice_bridge(settings))
        return 0

    if args.command == "all":
        _start_server_thread(settings.host, settings.port)
        from .pipeline import run_voice_bridge

        asyncio.run(run_voice_bridge(settings))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


def _start_server_thread(host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config("vrchat_ai_voice.openai_server:app", host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
