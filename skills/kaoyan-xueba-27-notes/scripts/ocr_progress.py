#!/usr/bin/env python3
"""Report OCR progress for the 27 Xueba notes skill."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
COLLECTION_JSON = SKILL_ROOT / "references" / "collection.json"
DEFAULT_JSONL = SKILL_ROOT / "references" / "ocr-pages.jsonl"


def main() -> None:
    collection = json.loads(COLLECTION_JSON.read_text(encoding="utf-8"))
    totals = {item["filename"]: int(item["pages"]) for item in collection["files"]}
    total_pages = sum(totals.values())

    done_pages: set[tuple[str, int]] = set()
    latest = None
    if DEFAULT_JSONL.exists():
        with DEFAULT_JSONL.open("r", encoding="utf-8-sig") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("text"):
                    key = (record["filename"], int(record["page_num"]))
                    done_pages.add(key)
                    latest = record

    by_file = Counter(filename for filename, _ in done_pages)
    done = len(done_pages)
    remaining = total_pages - done
    percent = (done / total_pages * 100) if total_pages else 0

    print(f"done_pages={done}")
    print(f"total_pages={total_pages}")
    print(f"remaining_pages={remaining}")
    print(f"percent={percent:.2f}")
    if latest:
        print(
            "latest="
            f"{latest['filename']} p{latest['page_num']} "
            f"chars={len(latest.get('text', ''))}"
        )
    print("by_file:")
    for filename, total in totals.items():
        count = by_file.get(filename, 0)
        print(f"  {filename}: {count}/{total}")


if __name__ == "__main__":
    main()
