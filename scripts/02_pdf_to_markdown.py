"""
Paper B Task 2: Convert Tier-1 Paper A PDFs to page-anchored Markdown.

Outputs paper_b/data/clean_markdown/{Seplat,Oando,Aradel}.md
with delimiters --- Page N --- (or --- SR Page N --- / --- FS Page N --- for Oando).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PAPER_B = Path(__file__).resolve().parents[1]
ROOT = PAPER_B  # PDFs referenced in pdf_manifest.json must be supplied locally
MANIFEST = PAPER_B / "data" / "pdf_manifest.json"
OUT_DIR = PAPER_B / "data" / "clean_markdown"


def convert_with_pymupdf4llm(pdf_path: Path, anchor_prefix: str) -> str | None:
    """One-pass page_chunks conversion; returns None if unavailable/fails."""
    try:
        import pymupdf4llm
    except ImportError:
        return None

    print(f"    pymupdf4llm page_chunks: {pdf_path.name}")
    try:
        chunks = pymupdf4llm.to_markdown(
            str(pdf_path),
            page_chunks=True,
            show_progress=True,
        )
    except TypeError:
        # Older signatures may not accept show_progress
        chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

    if not isinstance(chunks, list):
        return None

    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        page_no = i + 1
        if isinstance(chunk, dict):
            meta = chunk.get("metadata") or {}
            page_no = int(meta.get("page") or meta.get("page_number") or page_no)
            text = chunk.get("text") or ""
        else:
            text = str(chunk)
        parts.append(f"\n\n--- {anchor_prefix} {page_no} ---\n\n")
        parts.append(str(text).strip())
    return "".join(parts).strip() + "\n"


def convert_with_fitz(pdf_path: Path, anchor_prefix: str) -> str:
    """Fast text extraction fallback with page anchors."""
    import pymupdf as fitz

    print(f"    fitz text fallback: {pdf_path.name}")
    doc = fitz.open(pdf_path)
    parts: list[str] = []
    for i, page in enumerate(doc):
        page_no = i + 1
        parts.append(f"\n\n--- {anchor_prefix} {page_no} ---\n\n")
        parts.append((page.get_text("text") or "").strip())
        if page_no % 50 == 0 or page_no == doc.page_count:
            print(f"      page {page_no}/{doc.page_count}")
    doc.close()
    return "".join(parts).strip() + "\n"


def convert_pdf(pdf_path: Path, anchor_prefix: str, prefer_layout: bool = False) -> str:
    # Default: fast extractable-text path. pymupdf4llm often triggers RapidOCR on
    # these filings and is too slow for Phase 1 verification; use --layout later.
    if prefer_layout:
        md = convert_with_pymupdf4llm(pdf_path, anchor_prefix)
        if md is not None and len(md) > 1000:
            return md
    return convert_with_fitz(pdf_path, anchor_prefix)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--layout",
        action="store_true",
        help="Use pymupdf4llm page_chunks (slower; may OCR). Default is fast fitz text.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    t0 = time.time()

    for entity_id, meta in manifest["entities"].items():
        chunks: list[str] = [f"# Entity: {entity_id}\n"]
        for src in meta["sources"]:
            pdf_path = ROOT / src["path"]
            if not pdf_path.exists():
                raise SystemExit(f"Missing PDF: {pdf_path}")
            prefix = src["anchor_prefix"]
            role = src["role"]
            print(f"Converting {entity_id} / {role}: {pdf_path.name}")
            chunks.append(f"\n# Document: {role} ({pdf_path.name})\n")
            chunks.append(convert_pdf(pdf_path, prefix, prefer_layout=args.layout))
        out_path = OUT_DIR / f"{entity_id}.md"
        text = "\n".join(chunks)
        out_path.write_text(text, encoding="utf-8")
        anchors = text.count(f"--- ")
        print(f"  Wrote {out_path.name}: {len(text):,} chars, ~{anchors} anchors")

    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
