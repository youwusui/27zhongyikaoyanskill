#!/usr/bin/env python3
"""Search the master table-of-contents index for the 27学霸笔记 collection."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_source_max_pages(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8") as fh:
        page_map = json.load(fh)
    return {rule["source_pdf"]: int(rule["global_page_end"]) for rule in page_map["rules"]}


def row_text(row: dict[str, str]) -> str:
    return " ".join(row.get(key, "") for key in ("kind", "part", "chapter", "title", "source_pdf"))


def start_global(row: dict[str, str]) -> int:
    return int(row["start_global_page"])


def infer_end_global(row: dict[str, str], all_rows: list[dict[str, str]], source_max_pages: dict[str, int]) -> int:
    start = start_global(row)
    source_max = source_max_pages.get(row["source_pdf"], start)

    if row["kind"] == "part":
        candidates = [
            start_global(other)
            for other in all_rows
            if other["kind"] == "part" and start_global(other) > start
        ]
    else:
        candidates = [start_global(other) for other in all_rows if start_global(other) > start]

    if candidates:
        return min(min(candidates) - 1, source_max)
    return source_max


def pdf_page_for_global(row: dict[str, str], global_page: int) -> int:
    offset = int(row["start_pdf_page"]) - int(row["start_global_page"])
    return global_page + offset


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    default_index = Path(__file__).resolve().parents[1] / "references" / "toc-index.csv"
    default_page_map = Path(__file__).resolve().parents[1] / "references" / "page-map.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*", help="Keyword(s), for example: 方剂 清热剂")
    parser.add_argument("--index", type=Path, default=default_index)
    parser.add_argument("--page-map", type=Path, default=default_page_map)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    all_rows = load_rows(args.index)
    source_max_pages = load_source_max_pages(args.page_map)
    rows = all_rows
    query = " ".join(args.query).strip()
    if query:
        terms = [term.casefold() for term in query.split()]
        rows = [row for row in rows if all(term in row_text(row).casefold() for term in terms)]

    for row in rows[: args.limit]:
        end_global = infer_end_global(row, all_rows, source_max_pages)
        start_pdf_page = int(row["start_pdf_page"])
        end_pdf_page = pdf_page_for_global(row, end_global)
        print(
            "\t".join(
                [
                    row["kind"],
                    row["part"],
                    row["chapter"],
                    row["title"],
                    f"global={row['start_global_page']}-{end_global}",
                    f"pdf_page={start_pdf_page}-{end_pdf_page}",
                    row["source_pdf"],
                ]
            )
        )

    if not rows:
        print("No matching TOC entries.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
