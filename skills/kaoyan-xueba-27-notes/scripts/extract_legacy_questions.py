#!/usr/bin/env python3
"""Extract rough 1991-2006 question chunks from the exam-paper database."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = SKILL_ROOT / "references" / "exam-papers" / "exam-papers.sqlite"
DEFAULT_OUT = SKILL_ROOT / "references" / "exam-papers" / "legacy-1991-2006-questions.jsonl"
LEGACY_FILE = "1991至2006年考研中医综合真题.pdf"


YEAR_RE = re.compile(r"(19\d{2}|200[0-6])\s*年[^\n]{0,30}中医综合")
QUESTION_RE = re.compile(r"(?:(?<=\n)|^)\s*([1-9]\d{0,2}|[lI])(?:[.．、]|\s+(?=\S)|(?=[《“\u4e00-\u9fff]))\s*")


def normalize(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pages(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT page_num, text
            FROM exam_pages
            WHERE filename=? AND length(text)>0
            ORDER BY page_num
            """,
            (LEGACY_FILE,),
        ).fetchall()
    return [dict(row) for row in rows]


def split_year_sections(pages: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for page in pages:
        text = normalize(page["text"])
        matches = list(YEAR_RE.finditer(text))
        cursor = 0
        for match in matches:
            before = normalize(text[cursor : match.start()])
            if before and current:
                current["end_page"] = page["page_num"]
                current["parts"].append(before)
            if current:
                sections.append(current)
            current = {
                "year": int(match.group(1)),
                "start_page": page["page_num"],
                "end_page": page["page_num"],
                "parts": [],
            }
            cursor = match.start()
        remainder = normalize(text[cursor:])
        if remainder and current:
            current["end_page"] = page["page_num"]
            current["parts"].append(remainder)
    if current:
        sections.append(current)
    return sections


def question_type_before(section_text: str, offset: int) -> str | None:
    prefix = section_text[:offset]
    markers = [
        ("A", "A 型题"),
        ("B", "B 型题"),
        ("X", "X 型题"),
    ]
    found: tuple[int, str] | None = None
    for value, marker in markers:
        pos = max(prefix.rfind(marker), prefix.rfind(marker.replace(" ", "")))
        if pos >= 0 and (found is None or pos > found[0]):
            found = (pos, value)
    return found[1] if found else None


def split_questions(section: dict) -> list[dict]:
    text = "\n".join(section["parts"])
    matches = list(QUESTION_RE.finditer(text))
    questions: list[dict] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = normalize(text[start:end])
        if len(body) < 12:
            continue
        number_text = match.group(1)
        number = 1 if number_text in {"l", "I"} else int(number_text)
        questions.append(
            {
                "year": section["year"],
                "question_no": number,
                "question_type": question_type_before(text, start),
                "source_pdf": LEGACY_FILE,
                "pdf_page_start": section["start_page"],
                "pdf_page_end": section["end_page"],
                "answer": None,
                "answer_status": "needs_xueba_evidence",
                "text": body,
            }
        )
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    pages = load_pages(args.db)
    sections = split_year_sections(pages)
    questions: list[dict] = []
    for section in sections:
        questions.extend(split_questions(section))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for question in questions:
            f.write(json.dumps(question, ensure_ascii=False) + "\n")

    by_year: dict[int, int] = {}
    for question in questions:
        by_year[question["year"]] = by_year.get(question["year"], 0) + 1
    print(f"Wrote {args.out}")
    print(f"Years: {len(by_year)}")
    print(f"Questions: {len(questions)}")
    print(json.dumps(dict(sorted(by_year.items())), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
