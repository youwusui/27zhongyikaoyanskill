#!/usr/bin/env python3
"""Probe whether the configured PDFs contain an extractable text layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sample_page_indexes(page_count: int) -> list[int]:
    if page_count <= 0:
        return []
    return sorted({0, page_count // 2, page_count - 1})


def compact_text(text: str) -> str:
    return " ".join(text.split())


def probe_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("pypdf is required: install pypdf or use the bundled Codex Python runtime.") from exc

    result: dict[str, Any] = {
        "filename": path.name,
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        result["error"] = "file_not_found"
        return result

    reader = PdfReader(str(path), strict=False)
    page_count = len(reader.pages)
    result["pages"] = page_count
    result["samples"] = []

    for index in sample_page_indexes(page_count):
        try:
            text = reader.pages[index].extract_text() or ""
            compact = compact_text(text)
            result["samples"].append(
                {
                    "page": index + 1,
                    "chars": len(compact),
                    "preview": compact[:120],
                }
            )
        except Exception as exc:  # Keep probing other pages/files.
            result["samples"].append(
                {
                    "page": index + 1,
                    "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                }
            )

    result["has_text_layer"] = any(sample.get("chars", 0) >= 20 for sample in result["samples"])
    return result


def print_table(results: list[dict[str, Any]]) -> None:
    for item in results:
        status = "text" if item.get("has_text_layer") else "no_text"
        pages = item.get("pages", "?")
        samples = item.get("samples", [])
        chars = ",".join(str(sample.get("chars", 0)) for sample in samples)
        print(f"{status}\tpages={pages}\tsample_chars={chars}\t{item.get('filename')}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    default_config = Path(__file__).resolve().parents[1] / "references" / "collection.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument("--json", action="store_true", help="Print full JSON probe results.")
    args = parser.parse_args()

    config = load_config(args.config)
    source_root = Path(config["source_root"])
    results = []

    for file_info in config.get("files", []):
        path = Path(file_info.get("absolute_path") or source_root / file_info["filename"])
        results.append(probe_pdf(path))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_table(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
