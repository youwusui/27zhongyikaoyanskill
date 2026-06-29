#!/usr/bin/env python3
"""Compact OCR JSONL and rebuild per-book TXT files.

When a page is re-OCRed with --force, ocr_to_db.py appends a newer JSONL
record. This script keeps the newest record per (filename, page_num), rewrites
the JSONL in page order, and rebuilds references/ocr-text/*.txt without
duplicates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = SKILL_ROOT / "references" / "ocr-pages.jsonl"
DEFAULT_TEXT_DIR = SKILL_ROOT / "references" / "ocr-text"


def load_latest(jsonl_path: Path) -> dict[tuple[str, int], dict]:
    latest: dict[tuple[str, int], dict] = {}
    if not jsonl_path.exists():
        return latest
    with jsonl_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            key = (record["filename"], int(record["page_num"]))
            latest[key] = record
    return latest


def sort_key(record: dict) -> tuple[str, int]:
    return (record["filename"], int(record["page_num"]))


def rewrite_jsonl(jsonl_path: Path, records: list[dict]) -> None:
    tmp_path = jsonl_path.with_suffix(jsonl_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp_path.replace(jsonl_path)


def rebuild_txt(text_dir: Path, records: list[dict]) -> None:
    text_dir.mkdir(parents=True, exist_ok=True)
    for path in text_dir.glob("*.txt"):
        path.unlink()

    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["filename"], []).append(record)

    for filename, items in grouped.items():
        out = text_dir / (Path(filename).stem + ".txt")
        with out.open("w", encoding="utf-8", newline="\n") as f:
            for record in sorted(items, key=lambda r: int(r["page_num"])):
                f.write(f"\n\n===== {filename} | PDF page {record['page_num']} =====\n")
                f.write(record.get("text", ""))
                f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--text-dir", type=Path, default=DEFAULT_TEXT_DIR)
    args = parser.parse_args()

    latest = load_latest(args.jsonl)
    records = sorted(latest.values(), key=sort_key)
    rewrite_jsonl(args.jsonl, records)
    rebuild_txt(args.text_dir, records)
    print(f"Compacted OCR records: {len(records)}")
    print(f"Rebuilt TXT directory: {args.text_dir}")


if __name__ == "__main__":
    main()
