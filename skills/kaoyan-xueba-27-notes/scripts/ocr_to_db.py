#!/usr/bin/env python3
"""OCR the scanned 27 Xueba PDFs into JSONL, TXT, and SQLite.

Default engine is RapidOCR ONNXRuntime because it avoids PaddleOCR/PaddleX
oneDNN issues on Windows CPU.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = SKILL_ROOT.parents[1] / "27学霸笔记"
COLLECTION_JSON = SKILL_ROOT / "references" / "collection.json"
DEFAULT_DB = SKILL_ROOT / "references" / "xueba-notes.sqlite"
DEFAULT_JSONL = SKILL_ROOT / "references" / "ocr-pages.jsonl"
DEFAULT_TEXT_DIR = SKILL_ROOT / "references" / "ocr-text"
DEFAULT_CACHE = r"C:\tmp\xueba-paddlex-ms"
DEFAULT_WORK = SKILL_ROOT / "references" / "ocr-work"


def configure_env(cache_dir: str) -> None:
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", cache_dir)
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "modelscope")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
    os.environ.setdefault("FLAGS_use_mkldnn", "false")
    os.environ.setdefault("FLAGS_use_onednn", "false")


def load_collection() -> list[dict]:
    data = json.loads(COLLECTION_JSON.read_text(encoding="utf-8"))
    return data["files"]


def select_files(files: list[dict], names: list[str]) -> list[dict]:
    if not names:
        return files
    selected = []
    for item in files:
        if any(name in item["filename"] or name == item["subject"] for name in names):
            selected.append(item)
    if not selected:
        raise SystemExit(f"No matching PDF for: {', '.join(names)}")
    return selected


def done_pages(jsonl_path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if not jsonl_path.exists():
        return done
    with jsonl_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("text"):
                done.add((record["filename"], int(record["page_num"])))
    return done


def render_page(pdf_path: Path, page_num: int, image_path: Path, scale: float) -> None:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[page_num - 1]
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    pil_image.save(image_path)
    page.close()
    pdf.close()


def create_paddle_ocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="ch",
        ocr_version="PP-OCRv5",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def create_rapid_ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def create_ocr(engine: str):
    if engine == "rapidocr":
        return create_rapid_ocr()
    if engine == "paddleocr":
        return create_paddle_ocr()
    raise ValueError(f"Unsupported OCR engine: {engine}")


def run_ocr(engine_name: str, engine, image_path: Path) -> tuple[str, float | None]:
    if engine_name == "rapidocr":
        result, _ = engine(str(image_path))
        if not result:
            return "", None
        texts = []
        scores = []
        for item in result:
            if len(item) >= 3:
                texts.append(str(item[1]))
                scores.append(float(item[2]))
        confidence = sum(scores) / len(scores) if scores else None
        return "\n".join(texts), confidence

    result = engine.predict(str(image_path))
    return extract_paddle_text(result)


def extract_paddle_text(result) -> tuple[str, float | None]:
    if not result:
        return "", None
    item = result[0] if isinstance(result, list) else result
    texts = item.get("rec_texts", []) if isinstance(item, dict) else []
    scores = item.get("rec_scores", []) if isinstance(item, dict) else []
    text = "\n".join(str(t) for t in texts if str(t).strip())
    confidence = None
    if scores:
        confidence = float(sum(float(s) for s in scores) / len(scores))
    return text, confidence


def upsert_page(db_path: Path, record: dict) -> None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, global_page FROM pages WHERE filename=? AND page_num=?",
            (record["filename"], int(record["page_num"])),
        ).fetchone()
        if not row:
            return
        page_id, existing_global = row
        global_page = record.get("global_page", existing_global)
        conn.execute(
            """
            UPDATE pages
            SET text=?, global_page=?, ocr_status='done', ocr_engine=?,
                ocr_confidence=?, ocr_at=?
            WHERE id=?
            """,
            (
                record["text"],
                global_page,
                record["ocr_engine"],
                record.get("ocr_confidence"),
                record["ocr_at"],
                page_id,
            ),
        )
        conn.execute(
            "DELETE FROM page_fts WHERE filename=? AND page_num=?",
            (record["filename"], int(record["page_num"])),
        )
        conn.execute(
            """
            INSERT INTO page_fts (filename, page_num, global_page, text)
            VALUES (?, ?, ?, ?)
            """,
            (record["filename"], int(record["page_num"]), global_page, record["text"]),
        )


def append_txt(text_dir: Path, filename: str, page_num: int, text: str) -> None:
    text_dir.mkdir(parents=True, exist_ok=True)
    out = text_dir / (Path(filename).stem + ".txt")
    with out.open("a", encoding="utf-8") as f:
        f.write(f"\n\n===== {filename} | PDF page {page_num} =====\n")
        f.write(text)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="append", default=[], help="Filename substring or subject")
    parser.add_argument("--start-page", type=int)
    parser.add_argument("--end-page", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="PDF render scale. 2.0 is the quality-first default for these dense scans.",
    )
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--text-dir", type=Path, default=DEFAULT_TEXT_DIR)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE)
    parser.add_argument("--work-dir", default=DEFAULT_WORK)
    parser.add_argument("--engine", choices=["rapidocr", "paddleocr"], default="rapidocr")
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-OCR pages already in JSONL.")
    parser.add_argument("--log", type=Path, help="Append progress messages to this UTF-8 log file.")
    parser.add_argument("--quiet", action="store_true", help="Do not print progress to stdout.")
    args = parser.parse_args()

    log_context = args.log.open("a", encoding="utf-8") if args.log else contextlib.nullcontext()
    with log_context as log_file:
        run(args, log_file)


def run(args: argparse.Namespace, log_file) -> None:
    def log(message: str) -> None:
        if not args.quiet:
            print(message, flush=True)
        if log_file:
            log_file.write(message + "\n")
            log_file.flush()

    if args.engine == "paddleocr":
        configure_env(args.cache_dir)
    Path(args.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(args.work_dir).mkdir(parents=True, exist_ok=True)
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)

    files = select_files(load_collection(), args.pdf)
    already_done = done_pages(args.jsonl)
    ocr = create_ocr(args.engine)
    processed = 0
    started_at = time.perf_counter()

    with args.jsonl.open("a", encoding="utf-8") as jf:
        for item in files:
            filename = item["filename"]
            pdf_path = Path(item["absolute_path"])
            if not pdf_path.exists():
                pdf_path = SOURCE_ROOT / filename
            page_start = args.start_page or 1
            page_end = args.end_page or int(item["pages"])
            page_end = min(page_end, int(item["pages"]))

            for page_num in range(page_start, page_end + 1):
                if args.limit and processed >= args.limit:
                    log(f"Reached limit: {args.limit}")
                    return
                if not args.force and (filename, page_num) in already_done:
                    continue

                image_path = Path(args.work_dir) / f"{Path(filename).stem}-p{page_num:04d}.png"
                page_started_at = time.perf_counter()
                log(
                    f"OCR start: {filename} p{page_num} scale={args.scale}",
                )
                render_page(pdf_path, page_num, image_path, args.scale)
                render_seconds = time.perf_counter() - page_started_at
                ocr_started_at = time.perf_counter()
                text, confidence = run_ocr(args.engine, ocr, image_path)
                ocr_seconds = time.perf_counter() - ocr_started_at
                record = {
                    "filename": filename,
                    "page_num": page_num,
                    "text": text,
                    "ocr_engine": args.engine,
                    "ocr_confidence": confidence,
                    "ocr_at": datetime.now().isoformat(timespec="seconds"),
                }
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                jf.flush()
                append_txt(args.text_dir, filename, page_num, text)
                if not args.no_db:
                    upsert_page(args.db, record)
                processed += 1
                log(
                    "OCR done: "
                    f"{filename} p{page_num} chars={len(text)} "
                    f"render={render_seconds:.1f}s ocr={ocr_seconds:.1f}s "
                    f"elapsed={(time.perf_counter() - started_at):.1f}s",
                )

                try:
                    image_path.unlink()
                except OSError:
                    pass

    log(f"OCR completed pages: {processed}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
