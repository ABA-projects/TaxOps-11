"""services/renta/ocr_agent.py — OCR extraction for renta documents.

Strategy (all free, no API calls):
  1. PDF with digital text → pdfplumber (instant, perfect quality)
  2. PDF scanned / image   → pytesseract (local, free)
  3. Word (.docx)          → python-docx
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path


def extract_text(file_bytes: bytes, filename: str, mime_type: str = "") -> str:
    """Extract plain text from a document. Returns empty string on failure."""
    fname = filename.lower()

    if fname.endswith(".pdf") or "pdf" in mime_type:
        return _extract_pdf(file_bytes)
    if fname.endswith((".docx",)) or "word" in mime_type:
        return _extract_docx(file_bytes)
    if fname.endswith((".doc",)):
        return ""  # .doc not supported without antiword
    if fname.endswith((".xlsx", ".xls")):
        return _extract_excel(file_bytes, fname)
    if fname.endswith((".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".webp")):
        return _ocr_image(file_bytes)
    return ""


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = pdf.pages[:10]
            text = "\n".join(p.extract_text() or "" for p in pages).strip()
        if len(text) > 100:
            return text
        # Very little digital text → try OCR
        return _ocr_pdf(file_bytes)
    except Exception:
        return _ocr_pdf(file_bytes)


def _ocr_pdf(file_bytes: bytes) -> str:
    """Rasterize PDF pages and run pytesseract."""
    try:
        import pdfplumber
        import pytesseract
        from PIL import Image

        parts: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:3]:
                try:
                    img = page.to_image(resolution=200).original
                    t = pytesseract.image_to_string(img, lang="spa", timeout=60)
                    if t.strip():
                        parts.append(t)
                except Exception:
                    continue
        return "\n".join(parts).strip()
    except Exception:
        return ""


def _ocr_image(file_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(img, lang="spa", timeout=60).strip()
    except Exception:
        return ""


def _extract_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    except Exception:
        return ""


def _extract_excel(file_bytes: bytes, filename: str) -> str:
    try:
        import pandas as pd
        if filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None)
        else:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, header=None, engine="xlrd")
        parts = []
        for sheet_name, sheet_df in df.items():
            parts.append(f"--- {sheet_name} ---")
            parts.append(sheet_df.fillna("").to_string(index=False, header=False))
        return "\n".join(parts).strip()
    except Exception:
        return ""
