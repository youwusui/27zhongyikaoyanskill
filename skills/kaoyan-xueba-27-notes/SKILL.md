---
name: kaoyan-xueba-27-notes
description: 27中医307考研学霸笔记知识点简介。Private local retrieval skill for the user's 2027 "27学霸笔记" Chinese medicine postgraduate exam notes, built from OCR outputs and GitHub-project-style skill packaging. Use only when the user explicitly mentions "27学霸笔记", "$kaoyan-xueba-27-notes", "这个学霸笔记 skill", or asks to search this exact local notes database; supports OCR-backed lookup, page citation, TOC routing, section lookup, exam-style question generation without immediate answers, answer grading with full source-grounded explanations, and OCR maintenance for 方剂学、针灸与人文、中药学、中医基础理论、中医内科学、中医诊断学. Works for all agents that can read Codex-style skills and bundled local references/scripts.
---

# 27中医307考研学霸笔记知识点简介

This is an all-agent-compatible Codex-style skill for the local `27学霸笔记` OCR knowledge base. It turns six scanned 307 中医考研 note books into a searchable, page-cited, exam-training retrieval system.

The source material was processed through OCR and packaged with a GitHub-project-inspired skill structure: durable scripts, SQLite full-text search, JSONL page records, per-book TXT exports, TOC routing, and a section index. Use it to rapidly locate knowledge points, trace topics back to source pages, generate postgraduate-entrance-level questions, grade answers with complete explanations, and build high-density review workflows from the actual notes instead of loose memory.

Useful capabilities include:

-速查知识点：search exact terms, related concepts, TOC routes, and OCR page evidence across all six books.
-出题并批改：generate challenging single-choice and multiple-choice questions, wait for the learner's answers, then grade with full source-grounded解析.
-定位原文：cite book name, PDF page number, global page, and relevant OCR text for every serious claim.
-复习规划：turn a chapter, concept range, or weak topic list into focused drills and review checkpoints.
-跨科串联：connect 中基、中诊、中药、方剂、中内、针灸、人文知识点 through searchable evidence.
-维护扩展：continue OCR maintenance, rebuild indexes, compact OCR outputs, and keep the database useful as the notes evolve.

## Boundaries

- Use this skill only after the user explicitly names `27学霸笔记`, `$kaoyan-xueba-27-notes`, or this exact local notes database.
- Treat all files under this collection as private local study material.
- Answer from retrieved evidence. If retrieval is weak, say what was searched and what did not appear.
- Do not use this skill for general TCM, 考研, medicine, or textbook questions unless this database is explicitly invoked.

## Sources

The collection contains six OCRed scanned PDF books:

- `方剂学` - 160 pages
- `针灸与人文` - 135 pages
- `中药学` - 89 pages
- `中医基础理论` - 112 pages, PDF page 2 is blank
- `中医内科学` - 162 pages
- `中医诊断学` - 110 pages

Core files:

- `references/xueba-notes.sqlite` - primary SQLite + FTS database
- `references/ocr-pages.jsonl` - page-level OCR records
- `references/ocr-text/` - per-book TXT exports
- `references/toc-index.csv` - master table-of-contents routing
- `references/page-map.json` - global page to split-PDF page mapping
- `references/section-index.csv` - OCR-derived headings and excerpts
- `references/ocr-status.md` - coverage, engine, and maintenance notes

Current OCR state: all 768 PDF pages have records; 767 contain text; the only empty-text page is blank `中医基础理论` PDF page 2.

## Retrieval Workflow

1. Prefer the unified lookup script for content questions:

   ```powershell
   .\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\answer_lookup.py --query "舌诊" --limit 6
   ```

2. Use `--query-escape` when the shell mangles Chinese:

   ```powershell
   .\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\answer_lookup.py --query-escape "\u820c\u8bca" --limit 6
   ```

3. For broad topic routing, inspect TOC hits before synthesizing. TOC routes give the source PDF and PDF page span.
4. For exact terms, trust page hits first, then section hits. Quote or paraphrase with `filename pN` citations.
5. If a term has no hits, try synonyms, abbreviated forms, and related chapter names before making an absence claim.
6. For file inventory or OCR coverage questions, read `references/ocr-status.md`, `references/collection.json`, and `references/file-inventory.csv`.
7. If PowerShell displays mojibake, rerun lookup with `--unicode-escape-output`; the stored data is UTF-8.

## Quiz Workflow

- When the user asks to generate exam-style questions, do not include answers, answer keys, or explanations in the initial question set unless the user explicitly asks to see them immediately.
- After generating questions, ask the user to reply with their selected answers.
- When the user submits answers, grade them against the notes and provide complete explanations.
- For every graded item, cite where the evidence appears, using the book name, PDF page number, and relevant OCR text or a faithful paraphrase of that text.
- If a question depends on a range such as "某概念及其以前的内容", first locate the topic boundary with TOC/page hits, then build questions only from that bounded source range.
- Keep answer choices challenging at postgraduate entrance exam difficulty: test concept boundaries, source wording, contrasts, and application, not only isolated memorization.

## Direct Tools

- Search pages, sections, and TOC:

  ```powershell
  .\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\search_db.py --query-escape "\u533b\u7597\u4e8b\u6545" --limit 5
  ```

- Search only the table of contents:

  ```powershell
  .\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\search_toc.py "温病"
  ```

- Check OCR progress:

  ```powershell
  .\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\ocr_progress.py
  ```

## Maintenance

- OCR is complete. Do not restart OCR unless the user asks to re-OCR pages or improve quality.
- After forced re-OCR, run `scripts/compact_ocr_outputs.py`, then `scripts/build_section_index.py`.
- Keep `references/ocr-status.md` current after material OCR/index changes.
- Keep this skill lean: put durable procedures in `scripts/`, status in `references/ocr-status.md`, and avoid adding unrelated README-style files.
