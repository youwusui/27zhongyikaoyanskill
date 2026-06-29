#!/usr/bin/env python3
"""Build OCR/text-search assets for local Chinese medicine exam papers."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


SKILL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SKILL_ROOT.parents[1]
DEFAULT_SOURCE_DIR = WORKSPACE_ROOT / "历年真题"
DEFAULT_OUT_DIR = SKILL_ROOT / "references" / "exam-papers"
DEFAULT_DB = DEFAULT_OUT_DIR / "exam-papers.sqlite"
DEFAULT_JSONL = DEFAULT_OUT_DIR / "exam-pages.jsonl"
DEFAULT_TEXT_DIR = DEFAULT_OUT_DIR / "text"
DEFAULT_WORK_DIR = DEFAULT_OUT_DIR / "ocr-work"


def configure_stdout() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def year_from_name(name: str) -> int | None:
    match = re.search(r"(19\d{2}|20\d{2})", name)
    return int(match.group(1)) if match else None


def year_range_from_name(name: str) -> str:
    match = re.search(r"(19\d{2})\D+(20\d{2})", name)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    year = year_from_name(name)
    return str(year) if year else "unknown"


def classify_doc(path: Path) -> str:
    name = path.name
    if "解析" in name or "答案" in name or "参考答案" in name:
        if "真题" in name:
            return "questions_answers"
        return "answers"
    return "questions"


def extract_pdf_text(pdf, page_index: int) -> str:
    try:
        return (pdf[page_index].get_textpage().get_text_range() or "").strip()
    except Exception:
        return ""


def render_pdf_page(pdf, page_index: int, image_path: Path, scale: float) -> None:
    page = pdf[page_index]
    bitmap = page.render(scale=scale)
    bitmap.to_pil().save(image_path)


def create_ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_image(ocr, image_path: Path) -> tuple[str, float | None]:
    result, _ = ocr(str(image_path))
    if not result:
        return "", None
    lines: list[str] = []
    scores: list[float] = []
    for item in result:
        if len(item) >= 3:
            lines.append(str(item[1]))
            scores.append(float(item[2]))
    confidence = sum(scores) / len(scores) if scores else None
    return "\n".join(lines), confidence


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    root = ET.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in para.findall(".//w:t", namespace)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def create_schema(conn: sqlite3.Connection) -> str:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;

        DROP TABLE IF EXISTS exam_page_fts;
        DROP TABLE IF EXISTS exam_pages;
        DROP TABLE IF EXISTS exam_documents;
        DROP TABLE IF EXISTS exam_metadata;

        CREATE TABLE exam_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE exam_documents (
          id INTEGER PRIMARY KEY,
          filename TEXT NOT NULL UNIQUE,
          file_type TEXT NOT NULL,
          doc_kind TEXT NOT NULL,
          year_range TEXT NOT NULL,
          pages INTEGER NOT NULL,
          source_path TEXT NOT NULL,
          built_at TEXT NOT NULL
        );

        CREATE TABLE exam_pages (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES exam_documents(id),
          filename TEXT NOT NULL,
          page_num INTEGER NOT NULL,
          year_range TEXT NOT NULL,
          doc_kind TEXT NOT NULL,
          text TEXT NOT NULL,
          extraction_method TEXT NOT NULL,
          ocr_confidence REAL,
          extracted_at TEXT NOT NULL,
          UNIQUE(document_id, page_num)
        );

        CREATE INDEX idx_exam_pages_filename_page
          ON exam_pages(filename, page_num);
        CREATE INDEX idx_exam_pages_year
          ON exam_pages(year_range);
        """
    )
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE exam_page_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, year_range UNINDEXED, "
            "doc_kind UNINDEXED, text, tokenize='trigram')"
        )
        return "trigram"
    except sqlite3.OperationalError:
        conn.execute(
            "CREATE VIRTUAL TABLE exam_page_fts USING fts5("
            "filename UNINDEXED, page_num UNINDEXED, year_range UNINDEXED, "
            "doc_kind UNINDEXED, text, tokenize='unicode61')"
        )
        return "unicode61"


def insert_document(conn: sqlite3.Connection, path: Path, pages: int) -> int:
    cursor = conn.execute(
        """
        INSERT INTO exam_documents (
          filename, file_type, doc_kind, year_range, pages, source_path, built_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            path.name,
            path.suffix.lower().lstrip("."),
            classify_doc(path),
            year_range_from_name(path.name),
            pages,
            str(path.resolve()),
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    return int(cursor.lastrowid)


def write_page(conn: sqlite3.Connection, jsonl_file, text_dir: Path, record: dict) -> None:
    jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    jsonl_file.flush()

    out = text_dir / f"{Path(record['filename']).stem}.txt"
    with out.open("a", encoding="utf-8") as f:
        f.write(f"\n\n===== {record['filename']} | page {record['page_num']} =====\n")
        f.write(record["text"])
        f.write("\n")

    conn.execute(
        """
        INSERT INTO exam_pages (
          document_id, filename, page_num, year_range, doc_kind, text,
          extraction_method, ocr_confidence, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["document_id"],
            record["filename"],
            record["page_num"],
            record["year_range"],
            record["doc_kind"],
            record["text"],
            record["extraction_method"],
            record.get("ocr_confidence"),
            record["extracted_at"],
        ),
    )
    conn.execute(
        """
        INSERT INTO exam_page_fts (filename, page_num, year_range, doc_kind, text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record["filename"],
            record["page_num"],
            record["year_range"],
            record["doc_kind"],
            record["text"],
        ),
    )


def process_pdf(path: Path, conn: sqlite3.Connection, jsonl_file, text_dir: Path, args, ocr) -> tuple[int, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    page_count = len(pdf)
    doc_id = insert_document(conn, path, page_count)
    ocr_pages = 0
    for page_index in range(page_count):
        page_num = page_index + 1
        text = extract_pdf_text(pdf, page_index)
        confidence = None
        method = "pdf_text"
        if len(text) < args.ocr_threshold:
            if ocr is None:
                ocr = create_ocr()
            image_path = Path(args.work_dir) / f"{path.stem}-p{page_num:04d}.png"
            render_pdf_page(pdf, page_index, image_path, args.scale)
            text, confidence = ocr_image(ocr, image_path)
            method = "rapidocr"
            ocr_pages += 1
            try:
                image_path.unlink()
            except OSError:
                pass
        record = {
            "document_id": doc_id,
            "filename": path.name,
            "page_num": page_num,
            "year_range": year_range_from_name(path.name),
            "doc_kind": classify_doc(path),
            "text": text,
            "extraction_method": method,
            "ocr_confidence": confidence,
            "extracted_at": datetime.now().isoformat(timespec="seconds"),
        }
        write_page(conn, jsonl_file, text_dir, record)
        print(f"{path.name} p{page_num}/{page_count} {method} chars={len(text)}", flush=True)
    pdf.close()
    return page_count, ocr_pages


def process_docx(path: Path, conn: sqlite3.Connection, jsonl_file, text_dir: Path) -> tuple[int, int]:
    text = extract_docx_text(path)
    doc_id = insert_document(conn, path, 1)
    record = {
        "document_id": doc_id,
        "filename": path.name,
        "page_num": 1,
        "year_range": year_range_from_name(path.name),
        "doc_kind": classify_doc(path),
        "text": text,
        "extraction_method": "docx_xml",
        "ocr_confidence": None,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_page(conn, jsonl_file, text_dir, record)
    print(f"{path.name} docx_xml chars={len(text)}", flush=True)
    return 1, 0


def build(args: argparse.Namespace) -> None:
    source_dir = Path(args.source_dir)
    out_dir = Path(args.out_dir)
    text_dir = Path(args.text_dir)
    work_dir = Path(args.work_dir)
    db_path = Path(args.db)
    jsonl_path = Path(args.jsonl)

    out_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    for stale in text_dir.glob("*.txt"):
        stale.unlink()
    if jsonl_path.exists():
        jsonl_path.unlink()
    if db_path.exists():
        db_path.unlink()

    files = sorted([*source_dir.glob("*.pdf"), *source_dir.glob("*.docx")])
    if not files:
        raise SystemExit(f"No exam files found under {source_dir}")

    total_pages = 0
    total_ocr_pages = 0
    ocr = None
    with sqlite3.connect(db_path) as conn, jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        tokenizer = create_schema(conn)
        for path in files:
            if path.suffix.lower() == ".pdf":
                pages, ocr_pages = process_pdf(path, conn, jsonl_file, text_dir, args, ocr)
            elif path.suffix.lower() == ".docx":
                pages, ocr_pages = process_docx(path, conn, jsonl_file, text_dir)
            else:
                continue
            total_pages += pages
            total_ocr_pages += ocr_pages
        conn.execute("INSERT INTO exam_metadata (key, value) VALUES (?, ?)", ("fts_tokenizer", tokenizer))
        conn.execute("INSERT INTO exam_metadata (key, value) VALUES (?, ?)", ("built_at", datetime.now().isoformat(timespec="seconds")))
        conn.execute("INSERT INTO exam_metadata (key, value) VALUES (?, ?)", ("source_dir", str(source_dir.resolve())))
        conn.execute("INSERT INTO exam_metadata (key, value) VALUES (?, ?)", ("total_pages", str(total_pages)))
        conn.execute("INSERT INTO exam_metadata (key, value) VALUES (?, ?)", ("ocr_pages", str(total_ocr_pages)))

    print(f"Built {db_path}")
    print(f"Documents: {len(files)}")
    print(f"Pages: {total_pages}")
    print(f"OCR fallback pages: {total_ocr_pages}")


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--text-dir", type=Path, default=DEFAULT_TEXT_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--ocr-threshold", type=int, default=40)
    parser.add_argument("--scale", type=float, default=2.0)
    args = parser.parse_args()
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
