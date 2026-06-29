#!/usr/bin/env python3
"""Search local exam-paper OCR/text assets."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "exam-papers" / "exam-papers.sqlite"


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def decode_query(query: str | None, escaped: str | None) -> str:
    if escaped:
        return escaped.encode("ascii").decode("unicode_escape")
    if query:
        return query
    raise ValueError("query or --query-escape is required")


def fts_query(query: str) -> str:
    return '"' + query.replace('"', '""') + '"'


def compact(text: str, width: int = 220) -> str:
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "..."


def snippet(text: str, query: str, width: int = 260) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    pos = text.find(query)
    if pos < 0:
        return compact(text, width)
    side = max(30, (width - len(query)) // 2)
    start = max(0, pos - side)
    end = min(len(text), pos + len(query) + side)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def search(conn: sqlite3.Connection, query: str, limit: int, year: str | None, kind: str | None) -> list[dict]:
    clauses: list[str] = []
    params: list[str] = []
    if year:
        clauses.append("year_range LIKE ?")
        params.append(f"%{year}%")
    if kind:
        clauses.append("doc_kind = ?")
        params.append(kind)
    suffix = ""
    if clauses:
        suffix = " AND " + " AND ".join(clauses)
    try:
        rows = conn.execute(
            f"""
            SELECT filename, page_num, year_range, doc_kind, extraction_method, text
            FROM exam_page_fts
            JOIN exam_pages USING (filename, page_num, year_range, doc_kind)
            WHERE exam_page_fts MATCH ?{suffix}
            LIMIT ?
            """,
            [fts_query(query), *params, limit],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = conn.execute(
            f"""
            SELECT filename, page_num, year_range, doc_kind, extraction_method, text
            FROM exam_pages
            WHERE text LIKE ?{suffix}
            LIMIT ?
            """,
            [f"%{query}%", *params, limit],
        ).fetchall()
    return [
        {
            "filename": row["filename"],
            "page_num": row["page_num"],
            "year_range": row["year_range"],
            "doc_kind": row["doc_kind"],
            "extraction_method": row["extraction_method"],
            "snippet": snippet(row["text"], query),
        }
        for row in rows
    ]


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query")
    parser.add_argument("--query-escape")
    parser.add_argument("--year", help="Optional year or range fragment, e.g. 2024 or 1991-2006")
    parser.add_argument("--kind", choices=("questions", "answers", "questions_answers"))
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    query = decode_query(args.query, args.query_escape)
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        results = search(conn, query, args.limit, args.year, args.kind)

    if args.format == "json":
        print(json.dumps({"query": query, "results": results}, ensure_ascii=False, indent=2))
        return 0

    print(f"# Exam query: {query}")
    if args.year:
        print(f"Year filter: {args.year}")
    if args.kind:
        print(f"Kind filter: {args.kind}")
    if not results:
        print("(none)")
    for item in results:
        print(
            f"- {item['year_range']} | {item['filename']} p{item['page_num']} "
            f"[{item['doc_kind']}/{item['extraction_method']}]: {item['snippet']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
