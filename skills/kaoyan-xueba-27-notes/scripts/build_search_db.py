#!/usr/bin/env python3
"""Build the local SQLite search database for the 27 Xueba notes skill.

The database can be created before OCR exists. It stores document metadata,
the master TOC, page mappings, and empty page rows. OCR text can be imported
later with import_ocr_jsonl.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"
COLLECTION_JSON = SKILL_ROOT / "references" / "collection.json"
TOC_CSV = SKILL_ROOT / "references" / "toc-index.csv"
PAGE_MAP_JSON = SKILL_ROOT / "references" / "page-map.json"


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  subject TEXT NOT NULL,
  filename TEXT NOT NULL UNIQUE,
  absolute_path TEXT NOT NULL,
  pages INTEGER NOT NULL,
  size_mb REAL,
  text_layer_status TEXT,
  ocr_recommendation TEXT
);

CREATE TABLE IF NOT EXISTS toc_entries (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,
  part TEXT,
  chapter TEXT,
  title TEXT NOT NULL,
  start_global_page INTEGER NOT NULL,
  end_global_page INTEGER,
  source_pdf TEXT NOT NULL,
  start_pdf_page INTEGER NOT NULL,
  end_pdf_page INTEGER
);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  filename TEXT NOT NULL,
  page_num INTEGER NOT NULL,
  global_page INTEGER,
  text TEXT NOT NULL DEFAULT '',
  ocr_status TEXT NOT NULL DEFAULT 'pending',
  ocr_engine TEXT,
  ocr_confidence REAL,
  ocr_at TEXT,
  UNIQUE(document_id, page_num)
);

CREATE INDEX IF NOT EXISTS idx_pages_filename_page
  ON pages(filename, page_num);
CREATE INDEX IF NOT EXISTS idx_pages_global_page
  ON pages(global_page);
CREATE INDEX IF NOT EXISTS idx_toc_source_page
  ON toc_entries(source_pdf, start_pdf_page);

CREATE TABLE IF NOT EXISTS section_entries (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  page_num INTEGER NOT NULL,
  global_page INTEGER,
  heading TEXT NOT NULL,
  heading_level TEXT,
  excerpt TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_sections_filename_page
  ON section_entries(filename, page_num);
"""


def reset_tables(conn: sqlite3.Connection) -> None:
    for table in ("page_fts", "toc_fts", "section_fts"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    for table in ("section_entries", "pages", "toc_entries", "documents", "metadata"):
        conn.execute(f"DELETE FROM {table}")


def create_fts(conn: sqlite3.Connection) -> str:
    """Create FTS tables, preferring trigram for Chinese substring search."""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE page_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, global_page UNINDEXED, "
            "text, tokenize='trigram')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE toc_fts USING fts5("
            "kind UNINDEXED, source_pdf UNINDEXED, start_pdf_page UNINDEXED, "
            "end_pdf_page UNINDEXED, text, tokenize='trigram')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE section_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, global_page UNINDEXED, "
            "heading, excerpt, tokenize='trigram')"
        )
        return "trigram"
    except sqlite3.OperationalError:
        conn.execute("DROP TABLE IF EXISTS page_fts")
        conn.execute("DROP TABLE IF EXISTS toc_fts")
        conn.execute("DROP TABLE IF EXISTS section_fts")
        conn.execute(
            "CREATE VIRTUAL TABLE page_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, global_page UNINDEXED, "
            "text, tokenize='unicode61')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE toc_fts USING fts5("
            "kind UNINDEXED, source_pdf UNINDEXED, start_pdf_page UNINDEXED, "
            "end_pdf_page UNINDEXED, text, tokenize='unicode61')"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE section_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, global_page UNINDEXED, "
            "heading, excerpt, tokenize='unicode61')"
        )
        return "unicode61"


def load_page_map() -> list[dict]:
    data = json.loads(PAGE_MAP_JSON.read_text(encoding="utf-8"))
    return data["rules"]


def eval_pdf_formula(formula: str, global_page: int) -> int:
    left, op, right = formula.split()
    if left != "global_page":
        raise ValueError(f"Unsupported page-map formula: {formula}")
    offset = int(right)
    if op == "+":
        return global_page + offset
    if op == "-":
        return global_page - offset
    raise ValueError(f"Unsupported page-map formula: {formula}")


def global_page_for_pdf_page(filename: str, page_num: int, rules: list[dict]) -> int | None:
    for rule in rules:
        if rule["source_pdf"] != filename:
            continue
        start = int(rule["global_page_start"])
        end = int(rule["global_page_end"])
        for global_page in range(start, end + 1):
            pdf_page = eval_pdf_formula(rule["pdf_page_formula"], global_page)
            if pdf_page == page_num:
                return global_page
    return None


def import_documents(conn: sqlite3.Connection, collection: dict) -> None:
    for item in collection["files"]:
        conn.execute(
            """
            INSERT INTO documents (
              subject, filename, absolute_path, pages, size_mb,
              text_layer_status, ocr_recommendation
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["subject"],
                item["filename"],
                item["absolute_path"],
                int(item["pages"]),
                float(item.get("size_mb") or 0),
                item.get("text_layer_status"),
                item.get("ocr_recommendation"),
            ),
        )


def import_pages(conn: sqlite3.Connection, rules: list[dict]) -> None:
    rows = conn.execute("SELECT id, filename, pages FROM documents").fetchall()
    for doc_id, filename, page_count in rows:
        for page_num in range(1, int(page_count) + 1):
            global_page = global_page_for_pdf_page(filename, page_num, rules)
            conn.execute(
                """
                INSERT INTO pages (document_id, filename, page_num, global_page)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, filename, page_num, global_page),
            )


def import_toc(conn: sqlite3.Connection) -> None:
    rows: list[dict] = []
    with TOC_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row["start_global_page"] = int(row["start_global_page"])
            row["start_pdf_page"] = int(row["start_pdf_page"])
            rows.append(row)

    for i, row in enumerate(rows):
        next_row = rows[i + 1] if i + 1 < len(rows) else None
        end_global = None
        end_pdf = None
        if next_row and next_row["start_global_page"] > row["start_global_page"]:
            end_global = next_row["start_global_page"] - 1
            if next_row["source_pdf"] == row["source_pdf"]:
                end_pdf = next_row["start_pdf_page"] - 1

        conn.execute(
            """
            INSERT INTO toc_entries (
              kind, part, chapter, title, start_global_page, end_global_page,
              source_pdf, start_pdf_page, end_pdf_page
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["kind"],
                row.get("part") or None,
                row.get("chapter") or None,
                row["title"],
                row["start_global_page"],
                end_global,
                row["source_pdf"],
                row["start_pdf_page"],
                end_pdf,
            ),
        )

        search_text = " ".join(
            value for value in (row.get("part"), row.get("chapter"), row["title"]) if value
        )
        conn.execute(
            """
            INSERT INTO toc_fts (
              kind, source_pdf, start_pdf_page, end_pdf_page, text
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (row["kind"], row["source_pdf"], row["start_pdf_page"], end_pdf, search_text),
        )


def build(db_path: Path, overwrite: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and not overwrite:
        raise SystemExit(f"Database already exists: {db_path}. Use --overwrite to rebuild.")

    collection = json.loads(COLLECTION_JSON.read_text(encoding="utf-8"))
    rules = load_page_map()

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        reset_tables(conn)
        tokenizer = create_fts(conn)
        import_documents(conn, collection)
        import_pages(conn, rules)
        import_toc(conn)
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("collection_name", collection["name"]),
        )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("fts_tokenizer", tokenizer),
        )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, datetime('now'))",
            ("created_at",),
        )

    print(f"Built {db_path}")
    print(f"FTS tokenizer: {tokenizer}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    build(args.db, args.overwrite)


if __name__ == "__main__":
    main()
