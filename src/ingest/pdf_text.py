"""PDF text extraction helpers."""

from __future__ import annotations

from pathlib import Path

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract embedded text from a PDF.

    This intentionally does not OCR scanned pages yet. OCR can be added later as
    a fallback only when embedded text is empty or obviously incomplete.
    """

    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as error:
        raise RuntimeError("PDF text extraction requires pypdf. Run: pip install -r requirements.txt") from error

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"\n\n--- Seite {index} ---\n{text.strip()}")
    return "".join(pages).strip()
