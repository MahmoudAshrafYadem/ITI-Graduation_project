"""Parse 3GPP PDFs with PyMuPDF, extracting metadata, tables, and cleaned text."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import fitz  # PyMuPDF
import pandas as pd

TS_PATTERN = re.compile(r"3GPP\s+TS\s+(\d+\.\d+)\s+V(\d+\.\d+\.\d+)")
RELEASE_PATTERN = re.compile(r"Release\s+(\d+)", re.IGNORECASE)
PAGE_HEADER_PATTERN = re.compile(r"^3GPP\s+TS\s+\d+\.\d+\s+V\d+\.\d+\.\d+.*$")

@dataclass
class ParsedPage:
    page_number: int
    text: str

@dataclass
class ParsedDocument:
    ts_number: str
    release: str
    version: str
    pages: List[ParsedPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

def _extract_metadata(doc: fitz.Document) -> dict:
    head = "".join(doc[i].get_text() for i in range(min(3, len(doc))))
    ts_match = TS_PATTERN.search(head)
    rel_match = RELEASE_PATTERN.search(head)
    return {
        "ts_number": ts_match.group(1) if ts_match else "unknown",
        "version": ts_match.group(2) if ts_match else "unknown",
        "release": rel_match.group(1) if rel_match else "unknown",
    }

def _clean_page_text(text: str) -> str:
    cleaned_lines = []
    for line in text.split("\n"):
        if PAGE_HEADER_PATTERN.match(line.strip()):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

def _extract_tables_to_markdown(page: fitz.Page) -> str:
    tables = page.find_tables()
    if not tables.tables:
        return ""
    md_tables = []
    for tab in tables:
        try:
            df = tab.to_pandas()
            df = df.dropna(how='all').dropna(axis=1, how='all')
            if not df.empty:
                md_tables.append(df.to_markdown(index=False))
        except Exception:
            continue
    return "\n\n".join(md_tables)

def parse_pdf(pdf_path: str | Path) -> ParsedDocument:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    try:
        metadata = _extract_metadata(doc)
        pages = []
        for i, page in enumerate(doc):
            raw = page.get_text("text")
            cleaned = _clean_page_text(raw)
            tables_md = _extract_tables_to_markdown(page)
            if tables_md:
                cleaned += f"\n\n[EXTRACTED TABLES]\n{tables_md}\n"
            if cleaned:
                pages.append(ParsedPage(page_number=i + 1, text=cleaned))
        return ParsedDocument(
            ts_number=metadata["ts_number"],
            release=metadata["release"],
            version=metadata["version"],
            pages=pages,
        )
    finally:
        doc.close()