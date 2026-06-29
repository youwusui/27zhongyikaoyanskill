#!/usr/bin/env python3
"""Build a heading/section index from imported OCR text."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"
DEFAULT_CSV = SKILL_ROOT / "references" / "section-index.csv"

HEADING_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("chapter", re.compile(r"^第[一二三四五六七八九十百0-9]+[章节篇].{0,28}$")),
    ("numbered", re.compile(r"^[一二三四五六七八九十]+[、.．].{1,32}$")),
    ("paren", re.compile(r"^[（(][一二三四五六七八九十0-9]+[）)].{1,32}$")),
    ("marker", re.compile(r"^【[^】]{1,18}】.{0,28}$")),
    ("short", re.compile(r"^[\u4e00-\u9fffA-Za-z0-9·《》]{2,16}$")),
]


def classify(line: str) -> str | None:
    if not line or len(line) > 36:
        return None
    if re.search(r"[。；，,：:]{2,}", line):
        return None
    for level, pattern in HEADING_PATTERNS:
        if pattern.match(line):
            return level
    return None


def normalize_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", "", raw.strip())
        if line:
            lines.append(line)
    return lines


def build(db_path: Path, csv_path: Path) -> int:
    rows_out: list[tuple[str, int, int | None, str, str, str]] = []
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM section_entries")
        conn.execute("DELETE FROM section_fts")
        pages = conn.execute(
            """
            SELECT filename, page_num, global_page, text
            FROM pages
            WHERE ocr_status='done' AND length(text) > 0
            ORDER BY filename, page_num
            """
        ).fetchall()

        for filename, page_num, global_page, text in pages:
            lines = normalize_lines(text)
            for i, line in enumerate(lines):
                level = classify(line)
                if not level:
                    continue
                excerpt = "\n".join(lines[i : i + 8])
                rows_out.append((filename, page_num, global_page, line, level, excerpt))
                conn.execute(
                    """
                    INSERT INTO section_entries
                    (filename, page_num, global_page, heading, heading_level, excerpt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (filename, page_num, global_page, line, level, excerpt),
                )
                conn.execute(
                    """
                    INSERT INTO section_fts
                    (filename, page_num, global_page, heading, excerpt)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (filename, page_num, global_page, line, excerpt),
                )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("filename,page_num,global_page,heading,heading_level,excerpt\n")
        for filename, page_num, global_page, heading, level, excerpt in rows_out:
            safe_excerpt = excerpt.replace('"', '""').replace("\n", "\\n")
            safe_heading = heading.replace('"', '""')
            f.write(
                f'"{filename}",{page_num},{global_page or ""},'
                f'"{safe_heading}","{level}","{safe_excerpt}"\n'
            )
    return len(rows_out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    count = build(args.db, args.csv)
    print(f"Built {count} section index entries: {args.csv}")


if __name__ == "__main__":
    main()
