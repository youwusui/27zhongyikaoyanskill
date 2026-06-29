# OCR Status

Last updated: 2026-06-27

## Current State

- Source PDFs are scanned/image-based PDFs. A `pypdf` text-layer probe on the first, middle, and last page of each PDF returned no extractable body text.
- OCR is required for reliable full-text search, within-chapter lookup, quotation, and content-grounded answers.
- RapidOCR ONNXRuntime is the current working OCR engine. PaddleOCR/PaddleX attempts were unstable on this Windows CPU environment because of oneDNN runtime errors.
- OCR is incremental and resumable. Completed pages are stored in `references/ocr-pages.jsonl`, per-book text files under `references/ocr-text/`, and `references/xueba-notes.sqlite`.
- Last observed OCR coverage: 768 / 768 unique page records at 2026-06-27. 767 pages contain OCR text; the only empty-text page is `27学霸笔记—中医基础理论.pdf` PDF page 2, visually confirmed as blank.
- Full high-quality OCR completed on 2026-06-27 with RapidOCR scale 2.0; progress log: `.ocr-logs\continue-20260627.log`.
- Current section index coverage: 7839 entries from completed OCR pages in `references/section-index.csv` and the SQLite `section_entries` / `section_fts` tables.
- High-quality OCR uses `--scale 2.0`. This is slower than `--scale 0.75`, but it correctly recognized dense table terms such as `麻黄*` on `中药学` PDF page 28; lower scale missed or corrupted that key term.
- Current tested speed for high-quality OCR is roughly 39-72 seconds per dense page on this CPU. Full OCR is therefore an overnight-scale local job, not a one-hour job.

## Outputs

- SQLite database: `references/xueba-notes.sqlite`
- OCR JSONL: `references/ocr-pages.jsonl`
- Per-book TXT: `references/ocr-text/`
- Master TOC index: `references/toc-index.csv`
- Page map: `references/page-map.json`

## Commands

Continue high-quality OCR from the checkpoint:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\ocr_to_db.py --engine rapidocr --scale 2.0
```

Continue a daily short batch of 10 pages:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\ocr_to_db.py --engine rapidocr --scale 2.0 --log .ocr-logs\daily-ocr.log --limit 10
```

Check progress:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\ocr_progress.py
```

Search completed OCR pages:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\search_db.py --query-escape \u9ebb\u9ec4 --limit 5
```

After forced re-OCR of existing pages, compact JSONL and rebuild TXT files:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\compact_ocr_outputs.py
```

After all pages are OCRed, build the section index:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\build_section_index.py
```

## Notes

- Use the TOC index for routing even before full OCR is complete.
- Do not claim a topic is absent from the notes unless the relevant pages have been OCRed or visually inspected.
- PowerShell may display Chinese filenames or snippets as mojibake in command output; the stored JSON/TXT/SQLite data is UTF-8.
