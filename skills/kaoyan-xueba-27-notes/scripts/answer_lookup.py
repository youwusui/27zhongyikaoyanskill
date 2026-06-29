#!/usr/bin/env python3
"""Unified lookup for the 27 Xueba notes skill."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"


def decode_query(query: str | None, escaped: str | None) -> str:
    if escaped:
        return escaped.encode("ascii").decode("unicode_escape")
    if query:
        return query
    raise ValueError("query or --query-escape is required")


def fts_query(query: str) -> str:
    return '"' + query.replace('"', '""') + '"'


def compact(text: str, width: int = 160) -> str:
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def snippet(text: str, query: str, width: int = 180) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    pos = text.find(query)
    if pos < 0:
        return compact(text, width)
    side = max(20, (width - len(query)) // 2)
    start = max(0, pos - side)
    end = min(len(text), pos + len(query) + side)
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


def subject_clause(subject: str | None) -> tuple[str, list[str]]:
    if not subject:
        return "", []
    return " AND d.subject LIKE ?", [f"%{subject}%"]


def search_pages(conn: sqlite3.Connection, query: str, limit: int, subject: str | None) -> list[dict]:
    clause, params = subject_clause(subject)
    try:
        rows = conn.execute(
            f"""
            SELECT d.subject, p.filename, p.page_num, p.global_page, p.text
            FROM page_fts f
            JOIN pages p ON p.filename=f.filename AND p.page_num=f.page_num
            JOIN documents d ON d.filename=p.filename
            WHERE page_fts MATCH ?{clause}
            LIMIT ?
            """,
            [fts_query(query), *params, limit],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = conn.execute(
            f"""
            SELECT d.subject, p.filename, p.page_num, p.global_page, p.text
            FROM pages p
            JOIN documents d ON d.filename=p.filename
            WHERE p.text LIKE ?{clause}
            LIMIT ?
            """,
            [f"%{query}%", *params, limit],
        ).fetchall()
    return [
        {
            "subject": row["subject"],
            "filename": row["filename"],
            "page_num": row["page_num"],
            "global_page": row["global_page"],
            "snippet": snippet(row["text"], query),
        }
        for row in rows
    ]


def search_sections(conn: sqlite3.Connection, query: str, limit: int, subject: str | None) -> list[dict]:
    clause, params = subject_clause(subject)
    try:
        rows = conn.execute(
            f"""
            SELECT d.subject, s.filename, s.page_num, s.global_page, s.heading, s.excerpt
            FROM section_fts f
            JOIN section_entries s
              ON s.filename=f.filename AND s.page_num=f.page_num AND s.heading=f.heading
            JOIN documents d ON d.filename=s.filename
            WHERE section_fts MATCH ?{clause}
            LIMIT ?
            """,
            [fts_query(query), *params, limit],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = conn.execute(
            f"""
            SELECT d.subject, s.filename, s.page_num, s.global_page, s.heading, s.excerpt
            FROM section_entries s
            JOIN documents d ON d.filename=s.filename
            WHERE (s.heading LIKE ? OR s.excerpt LIKE ?){clause}
            LIMIT ?
            """,
            [f"%{query}%", f"%{query}%", *params, limit],
        ).fetchall()
    return [
        {
            "subject": row["subject"],
            "filename": row["filename"],
            "page_num": row["page_num"],
            "global_page": row["global_page"],
            "heading": row["heading"],
            "snippet": snippet(row["excerpt"], query),
        }
        for row in rows
    ]


def search_toc(conn: sqlite3.Connection, query: str, limit: int, subject: str | None) -> list[dict]:
    clause = ""
    params: list[str] = []
    if subject:
        clause = " AND source_pdf LIKE ?"
        params.append(f"%{subject}%")
    try:
        rows = conn.execute(
            f"""
            SELECT kind, source_pdf, start_pdf_page, end_pdf_page, text
            FROM toc_fts
            WHERE toc_fts MATCH ?{clause}
            LIMIT ?
            """,
            [fts_query(query), *params, limit],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = conn.execute(
            f"""
            SELECT kind, source_pdf, start_pdf_page, end_pdf_page,
                   COALESCE(part || ' ', '') || COALESCE(chapter || ' ', '') || title AS text
            FROM toc_entries
            WHERE text LIKE ?{clause}
            LIMIT ?
            """,
            [f"%{query}%", *params, limit],
        ).fetchall()
    return [
        {
            "kind": row["kind"],
            "filename": row["source_pdf"],
            "start_pdf_page": row["start_pdf_page"],
            "end_pdf_page": row["end_pdf_page"],
            "text": compact(row["text"], 180),
        }
        for row in rows
    ]


def emit_markdown(result: dict, escape_output: bool) -> None:
    def out(line: str = "") -> None:
        if escape_output:
            print(line.encode("unicode_escape").decode("ascii"))
        else:
            print(line)

    out(f"# Query: {result['query']}")
    if result.get("subject"):
        out(f"Subject filter: {result['subject']}")

    out("\n## Best page evidence")
    if not result["pages"]:
        out("(none)")
    for item in result["pages"]:
        out(f"- {item['subject']} | {item['filename']} p{item['page_num']} global={item['global_page']}: {item['snippet']}")

    out("\n## Section evidence")
    if not result["sections"]:
        out("(none)")
    for item in result["sections"]:
        out(f"- {item['subject']} | {item['filename']} p{item['page_num']} [{item['heading']}]: {item['snippet']}")

    out("\n## TOC routes")
    if not result["toc"]:
        out("(none)")
    for item in result["toc"]:
        end_page = item["end_pdf_page"] or "?"
        out(f"- {item['filename']} p{item['start_pdf_page']}-{end_page} ({item['kind']}): {item['text']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query")
    parser.add_argument("--query-escape", help=r"ASCII-safe unicode escapes, e.g. \u820c\u8bca")
    parser.add_argument("--subject", help="Optional subject/book filter, e.g. 中医诊断学")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--unicode-escape-output", action="store_true")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    query = decode_query(args.query, args.query_escape)
    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row
        result = {
            "query": query,
            "subject": args.subject,
            "pages": search_pages(conn, query, args.limit, args.subject),
            "sections": search_sections(conn, query, args.limit, args.subject),
            "toc": search_toc(conn, query, args.limit, args.subject),
        }

    if args.format == "json":
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.unicode_escape_output:
            text = text.encode("unicode_escape").decode("ascii")
        print(text)
    else:
        emit_markdown(result, args.unicode_escape_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
