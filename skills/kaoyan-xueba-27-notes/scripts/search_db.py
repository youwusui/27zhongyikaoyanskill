#!/usr/bin/env python3
"""Search the 27 Xueba notes SQLite database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"


def snippet(text: str, query: str, width: int = 90) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    pos = text.find(query)
    if pos < 0:
        return text[:width]
    start = max(0, pos - width // 2)
    end = min(len(text), pos + len(query) + width // 2)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def fts_query(query: str) -> str:
    # Trigram FTS supports ordinary CJK substrings. Quoting also keeps punctuation safe.
    return '"' + query.replace('"', '""') + '"'


def emit(text: str, escape_output: bool) -> None:
    if escape_output:
        print(text.encode("unicode_escape").decode("ascii"))
    else:
        print(text)


def search_pages(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    try:
        rows = conn.execute(
            """
            SELECT p.filename, p.page_num, p.global_page, p.text
            FROM page_fts f
            JOIN pages p ON p.filename=f.filename AND p.page_num=f.page_num
            WHERE page_fts MATCH ?
            LIMIT ?
            """,
            (fts_query(query), limit),
        ).fetchall()
        if rows:
            return rows
    except sqlite3.OperationalError:
        pass
    return conn.execute(
        """
        SELECT filename, page_num, global_page, text
        FROM pages
        WHERE text LIKE ?
        LIMIT ?
        """,
        (f"%{query}%", limit),
    ).fetchall()


def search_sections(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    try:
        rows = conn.execute(
            """
            SELECT filename, page_num, global_page, heading, excerpt
            FROM section_fts
            WHERE section_fts MATCH ?
            LIMIT ?
            """,
            (fts_query(query), limit),
        ).fetchall()
        if rows:
            return rows
    except sqlite3.OperationalError:
        pass
    return conn.execute(
        """
        SELECT filename, page_num, global_page, heading, excerpt
        FROM section_entries
        WHERE heading LIKE ? OR excerpt LIKE ?
        LIMIT ?
        """,
        (f"%{query}%", f"%{query}%", limit),
    ).fetchall()


def search_toc(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    try:
        rows = conn.execute(
            """
            SELECT kind, source_pdf, start_pdf_page, end_pdf_page, text
            FROM toc_fts
            WHERE toc_fts MATCH ?
            LIMIT ?
            """,
            (fts_query(query), limit),
        ).fetchall()
        if rows:
            return rows
    except sqlite3.OperationalError:
        pass
    return conn.execute(
        """
        SELECT kind, source_pdf, start_pdf_page, end_pdf_page,
               COALESCE(part || ' ', '') || COALESCE(chapter || ' ', '') || title AS text
        FROM toc_entries
        WHERE text LIKE ?
        LIMIT ?
        """,
        (f"%{query}%", limit),
    ).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    parser.add_argument(
        "--query-escape",
        help=r"ASCII-safe Python unicode escapes, e.g. \u9ebb\u9ec4 for 麻黄.",
    )
    parser.add_argument(
        "--unicode-escape-output",
        action="store_true",
        help="Print output as ASCII unicode escapes to avoid PowerShell mojibake.",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.query_escape:
        args.query = args.query_escape.encode("ascii").decode("unicode_escape")
    if not args.query:
        parser.error("query or --query-escape is required")

    with sqlite3.connect(args.db) as conn:
        conn.row_factory = sqlite3.Row

        pages = search_pages(conn, args.query, args.limit)
        sections = search_sections(conn, args.query, args.limit)
        toc = search_toc(conn, args.query, args.limit)

    emit(f"# Query: {args.query}", args.unicode_escape_output)

    emit("\n## Page hits", args.unicode_escape_output)
    if not pages:
        emit("(none)", args.unicode_escape_output)
    for row in pages:
        emit(
            f"- {row['filename']} p{row['page_num']}"
            f" global={row['global_page']}: {snippet(row['text'], args.query)}",
            args.unicode_escape_output,
        )

    emit("\n## Section hits", args.unicode_escape_output)
    if not sections:
        emit("(none)", args.unicode_escape_output)
    for row in sections:
        emit(
            f"- {row['filename']} p{row['page_num']}"
            f" global={row['global_page']} [{row['heading']}]: "
            f"{snippet(row['excerpt'], args.query)}",
            args.unicode_escape_output,
        )

    emit("\n## TOC routes", args.unicode_escape_output)
    if not toc:
        emit("(none)", args.unicode_escape_output)
    for row in toc:
        end_page = row["end_pdf_page"] or "?"
        emit(
            f"- {row['source_pdf']} p{row['start_pdf_page']}-{end_page}"
            f" ({row['kind']}): {row['text']}",
            args.unicode_escape_output,
        )


if __name__ == "__main__":
    main()
