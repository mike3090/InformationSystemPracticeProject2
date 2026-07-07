from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run VRChat AI chat and proximity auto-facing together.")
    parser.add_argument("--no-facing", action="store_true", help="Only run the AI chat bridge.")
    parser.add_argument("--facing-once", action="store_true", help="Run one targeting OCR pass, then continue chat.")
    parser.add_argument("--save-debug", action="store_true", help="Keep targeting crop images under the runtime crop directory.")
    parser.add_argument("--invert-look", action="store_true", help="Invert OSC LookHorizontal direction if turning is reversed.")
    parser.add_argument("--targeting-args", default="", help="Extra raw args for proximity_targeting/face_target.py.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    runtime_dir = root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "crops").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "easyocr").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "huggingface").mkdir(parents=True, exist_ok=True)

    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["EASYOCR_MODULE_PATH"] = str(runtime_dir / "easyocr")
    env["HF_HOME"] = str(root / ".cache" / "huggingface")
    env["HUGGINGFACE_HUB_CACHE"] = str(root / ".cache" / "huggingface" / "hub")
    env["VRCHAT_AI_TRANSCRIPT_PATH"] = str(runtime_dir / "transcript.log")

    children: list[subprocess.Popen] = []

    try:
        if not args.no_facing:
            targeting_cmd = [
                str(python),
                "proximity_targeting\\face_target.py",
                "--crop-dir",
                str(runtime_dir / "crops"),
            ]
            if args.facing_once:
                targeting_cmd.append("--once")
            if args.save_debug:
                targeting_cmd.append("--save-debug")
            if args.invert_look:
                targeting_cmd.append("--invert-look")
            targeting_cmd.extend(
                [
                    "--interval",
                    "0.8",
                    "--hue-min",
                    "0",
                    "--hue-max",
                    "180",
                    "--sat-min",
                    "0",
                    "--value-min",
                    "45",
                    "--min-component-area",
                    "30",
                    "--max-component-area",
                    "120000",
                    "--min-aspect",
                    "0.5",
                    "--max-aspect",
                    "40",
                ]
            )
            if args.targeting_args.strip():
                targeting_cmd.extend(shlex.split(args.targeting_args))
            print("[run_all] transcript:", runtime_dir / "transcript.log", flush=True)
            print("[run_all] crops:", runtime_dir / "crops", flush=True)
            print("[run_all] starting proximity targeting:", " ".join(targeting_cmd), flush=True)
            children.append(subprocess.Popen(targeting_cmd, cwd=root, env=env))
            time.sleep(2)

        chat_cmd = [str(python), "-u", "-m", "vrchat_ai_voice", "all"]
        print("[run_all] starting AI chat bridge:", " ".join(chat_cmd), flush=True)
        chat = subprocess.Popen(chat_cmd, cwd=root, env=env)
        children.append(chat)
        return chat.wait()
    except KeyboardInterrupt:
        print("\n[run_all] stopping...", flush=True)
        return 130
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.time() + 5
        for child in children:
            while child.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if child.poll() is None:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
