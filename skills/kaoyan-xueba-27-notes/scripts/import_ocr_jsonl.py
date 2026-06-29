#!/usr/bin/env python3
"""Import page-level OCR text into the local SQLite search database.

Expected JSONL fields per line:
  filename/source_pdf, page_num/pdf_page/page, text
Optional fields:
  global_page, ocr_engine/engine, confidence/ocr_confidence, ocr_at
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"


def pick(record: dict, *names: str, default=None):
    for name in names:
        if name in record and record[name] not in (None, ""):
            return record[name]
    return default


def import_jsonl(db_path: Path, jsonl_path: Path) -> None:
    imported = 0
    skipped = 0

    with sqlite3.connect(db_path) as conn, jsonl_path.open("r", encoding="utf-8-sig") as f:
        conn.execute("PRAGMA foreign_keys=ON")
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            filename = pick(record, "filename", "source_pdf")
            page_num = pick(record, "page_num", "pdf_page", "page")
            text = pick(record, "text", "ocr_text", default="")
            if not filename or not page_num or not text:
                skipped += 1
                print(f"skip line {line_no}: missing filename/page/text")
                continue

            row = conn.execute(
                "SELECT id, global_page FROM pages WHERE filename=? AND page_num=?",
                (filename, int(page_num)),
            ).fetchone()
            if not row:
                skipped += 1
                print(f"skip line {line_no}: unknown page {filename} p{page_num}")
                continue

            page_id, existing_global = row
            global_page = pick(record, "global_page", default=existing_global)
            engine = pick(record, "ocr_engine", "engine")
            confidence = pick(record, "confidence", "ocr_confidence")
            ocr_at = pick(record, "ocr_at")

            conn.execute(
                """
                UPDATE pages
                SET text=?, global_page=?, ocr_status='done',
                    ocr_engine=?, ocr_confidence=?, ocr_at=COALESCE(?, datetime('now'))
                WHERE id=?
                """,
                (text, global_page, engine, confidence, ocr_at, page_id),
            )
            conn.execute(
                "DELETE FROM page_fts WHERE filename=? AND page_num=?",
                (filename, int(page_num)),
            )
            conn.execute(
                """
                INSERT INTO page_fts (filename, page_num, global_page, text)
                VALUES (?, ?, ?, ?)
                """,
                (filename, int(page_num), global_page, text),
            )
            imported += 1

    print(f"Imported {imported} OCR page(s); skipped {skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    import_jsonl(args.db, args.jsonl)


if __name__ == "__main__":
    main()
