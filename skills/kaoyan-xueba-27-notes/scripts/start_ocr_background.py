#!/usr/bin/env python3
"""Start the 27 Xueba OCR job as a detached background process on Windows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SKILL_ROOT.parents[1]
OCR_SCRIPT = SKILL_ROOT / "scripts" / "ocr_to_db.py"
LOG_DIR = WORKSPACE_ROOT / ".ocr-logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--scale", default="2.0")
    parser.add_argument("--log", default=str(LOG_DIR / "ocr-background.log"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = WORKSPACE_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stdout_path = log_path.parent / "ocr-background.stdout.log"
    stderr_path = log_path.parent / "ocr-background.stderr.log"

    command = [
        sys.executable,
        str(OCR_SCRIPT),
        "--engine",
        "rapidocr",
        "--scale",
        str(args.scale),
        "--quiet",
        "--log",
        str(log_path),
    ]
    if args.limit > 0:
        command.extend(["--limit", str(args.limit)])

    flags = 0
    for name in ("CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
        flags |= getattr(subprocess, name, 0)

    stdout_file = stdout_path.open("ab", buffering=0)
    stderr_file = stderr_path.open("ab", buffering=0)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(WORKSPACE_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            close_fds=False,
            creationflags=flags,
        )
    finally:
        stdout_file.close()
        stderr_file.close()

    print(f"Started OCR background process PID={process.pid}")
    print(f"Log={log_path}")
    print(f"Stdout={stdout_path}")
    print(f"Stderr={stderr_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
