# Exam Papers OCR Status

Built from the local `历年真题` directory on 2026-06-29.

## Coverage

- Documents: 26
- Page records: 847
- PDF text-layer pages: 772
- OCR fallback pages: 74
- DOCX XML records: 1
- Empty pages: 3 apparent blank/cover pages

## Outputs

- `exam-papers.sqlite` - SQLite + FTS search database for exam papers
- `exam-pages.jsonl` - page-level extracted text/OCR records
- `text/` - per-document TXT exports
- `legacy-1991-2006-questions.jsonl` - rough question-level split for the 1991-2006 papers, with answers intentionally left blank until evidence-backed derivation

## 1991-2006 Question Split

The 1991-2006 combined PDF has been split into question-level JSONL records for later answer-key work.

- Years: 16
- Question records: 2436
- Source answer key: not present in the local source PDF
- Answer status: `needs_xueba_evidence`
- Known limitation: OCR/printed layout causes a small number of missing or merged question numbers in most years; do not treat this JSONL as a verified answer key.

Question counts after OCR-aware splitting:

| Year | Records | Question range | Known missing numbers |
| --- | ---: | --- | --- |
| 1991 | 157 | 1-160 | 75, 77, 83, 103 |
| 1992 | 155 | 1-160 | 38, 73, 79, 83, 87 |
| 1993 | 157 | 1-160 | 51, 83, 95 |
| 1994 | 154 | 1-160 | 43, 73, 79, 107, 115, 128 |
| 1995 | 156 | 1-160 | 31, 75, 79, 87, 112 |
| 1996 | 155 | 1-160 | 69, 73, 105, 107, 125 |
| 1997 | 154 | 1-160 | 73, 75, 81, 83, 85, 102 |
| 1998 | 155 | 1-160 | 42, 75, 87, 97, 109 |
| 1999 | 147 | 1-160 | 73, 77, 81, 83, 85, 91, 93, 101, 105, 107, 109, 154, 157 |
| 2000 | 154 | 1-160 | 73, 79, 83, 85, 89, 109 |
| 2001 | 153 | 1-160 | 75, 77, 79, 81, 89, 115, 134 |
| 2002 | 152 | 1-160 | 73, 75, 77, 79, 81, 87, 101, 115 |
| 2003 | 147 | 1-150 | 80, 89, 97 |
| 2004 | 147 | 1-150 | 75, 95, 101 |
| 2005 | 146 | 1-150 | 78, 84, 88, 92 |
| 2006 | 147 | 1-150 | 76, 78, 86 |

## Empty Page Records

- `1991至2006年考研中医综合真题.pdf` page 248
- `2007年中医综合考研真题及答案.pdf` page 28
- `2014年考研中医综合真题完整版附答案.pdf` page 16

## Notes

- Most files contain a usable PDF text layer and were imported directly.
- `2020年中医综合考试答案详解.pdf`, `2023年中医综合考试真题及答案详解.pdf`, and most pages of `2024考研·中医综合真题及答案.pdf` required RapidOCR fallback.
- Spot checks confirmed readable text for 1991, 2020 answer explanations, 2023 answer explanations, 2024 answer pages, and the 2026 DOCX.
- 1991-2006 currently contains question text but no verified answer key in source. Deriving those answers from the Xueba notes should be treated as a separate evidence-backed answer-key build step.
- Spot checks confirmed the 2005 split recovered OCR variants such as `l．`, `31《...`, and `146 ...`; remaining missing numbers should be inspected against page text before answer derivation.

## Commands

Build or rebuild:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\build_exam_papers.py --scale 1.35
```

Search:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\search_exam_papers.py --query "阴中求阳" --limit 5
```

Rebuild the 1991-2006 question split:

```powershell
.\.venv-rapidocr\Scripts\python.exe skills\kaoyan-xueba-27-notes\scripts\extract_legacy_questions.py
```
