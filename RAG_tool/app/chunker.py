"""Semantic chunker for 3GPP specifications with strict boundary detection."""
import re
from dataclasses import dataclass
from typing import List
from .parser import ParsedDocument
from .config import CHUNK_SIZE, CHUNK_OVERLAP

SECTION_RE = re.compile(r"^(\d+(?:\.\d+){0,4})\s+(.+)$")
ASN1_BLOCK_RE = re.compile(r"^--\s*(TAG[-_]?(?:START|STOP)|ASN1START|ASN1STOP|COMMENT)", re.IGNORECASE)
TABLE_MARKER_RE = re.compile(r"\[EXTRACTED TABLES\]", re.IGNORECASE)
FIGURE_RE = re.compile(r"^([Ff]ig(?:ure)?\.?\s*\d+|[Ff]igure\s+\d+)", re.IGNORECASE)
ANNEX_RE = re.compile(r"^(Annex|Appendix)\s+[A-Z]", re.IGNORECASE)
CHANGE_HISTORY_RE = re.compile(r"(Change\s+History|Revision\s+History|Changes\s+since)", re.IGNORECASE)
CR_HISTORY_RE = re.compile(r"(CR\s+\d+|Correction\s+Report)", re.IGNORECASE)
FORMULA_RE = re.compile(r"^\s*\w+\s*=\s*", re.IGNORECASE)
MIN_CHUNK_WORDS = 20
MAX_CHUNK_WORDS = 500
OVERLAP_WORDS = 15

ASN1_START_MARKER = "-- TAG"

@dataclass
class Chunk:
    chunk_id: str
    text: str
    ts_number: str
    release: str
    version: str
    section: str
    section_title: str = ""
    chunk_type: str = "section_content"
    page: int = 0
    token_count: int = 0

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def _count_words(text: str) -> int:
    return len(text.split())

def _detect_chunk_type(line: str, context: str) -> str:
    stripped = line.strip()
    if ASN1_BLOCK_RE.match(stripped):
        return "asn1"
    if TABLE_MARKER_RE.search(context):
        return "table"
    if FIGURE_RE.match(stripped):
        return "figure"
    if ANNEX_RE.match(stripped):
        return "annex"
    if CHANGE_HISTORY_RE.search(stripped):
        return "history"
    if CR_HISTORY_RE.search(stripped):
        return "history"
    if FORMULA_RE.match(stripped) and len(stripped) < 120:
        return "formula"
    if SECTION_RE.match(stripped):
        m = SECTION_RE.match(stripped)
        section_num = m.group(1)
        title = m.group(2).lower()
        event_keywords = ["event", "triggered", "condition", "measurement"]
        if any(kw in title for kw in event_keywords):
            return "event_definition"
        if len(section_num.split(".")) >= 4:
            return "event_definition"
    return "section_content"

def _is_boundary_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if ASN1_BLOCK_RE.match(stripped):
        return True
    if FIGURE_RE.match(stripped):
        return True
    if ANNEX_RE.match(stripped):
        return True
    if CHANGE_HISTORY_RE.search(stripped):
        return True
    if CR_HISTORY_RE.search(stripped):
        return True
    return False

def _is_undesirable_standalone(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("ETSI") and "TS" in stripped[:25]:
        return True
    if stripped.startswith("RP-") or stripped.startswith("CR ") or stripped.startswith("FR "):
        return True
    if stripped.startswith("<!--") or stripped.startswith("-->"):
        return True
    if "CORRECTION" in stripped.upper() and "NR" not in stripped and len(stripped) < 200:
        return True
    return False

def _split_paragraphs(text: str) -> List[str]:
    paragraphs = []
    current = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs

def _create_chunk(chunk_id: str, text: str, ts_number: str, release: str,
                   version: str, section: str, section_title: str,
                   chunk_type: str, page: int) -> Chunk:
    text = text.strip()
    if not text:
        return None
    return Chunk(
        chunk_id=chunk_id, text=text, ts_number=ts_number,
        release=release, version=version, section=section,
        section_title=section_title, chunk_type=chunk_type,
        page=page, token_count=estimate_tokens(text),
    )

def _split_large_chunk(chunk_text: str, max_words: int, overlap_words: int,
                         chunk_id_base: str, ts_number: str, release: str,
                         version: str, section: str, section_title: str,
                         chunk_type: str, page: int) -> List[Chunk]:
    paragraphs = _split_paragraphs(chunk_text)
    if len(paragraphs) <= 1:
        return [_create_chunk(chunk_id_base, chunk_text, ts_number, release,
                               version, section, section_title, chunk_type, page)]

    sub_chunks = []
    current_paras = []
    current_words = 0
    sub_idx = 0

    for para in paragraphs:
        para_words = _count_words(para)
        if current_paras and current_words + para_words > max_words and current_words >= MIN_CHUNK_WORDS:
            text = "\n\n".join(current_paras)
            sub_chunks.append(_create_chunk(
                f"{chunk_id_base}-{sub_idx}" if sub_idx > 0 else chunk_id_base,
                text, ts_number, release, version, section, section_title,
                chunk_type, page,
            ))
            sub_idx += 1
            overlap_start = max(0, len(current_paras) - max(1, overlap_words // 10))
            current_paras = current_paras[overlap_start:]
            current_words = sum(_count_words(p) for p in current_paras)

        current_paras.append(para)
        current_words += para_words

    if current_paras:
        text = "\n\n".join(current_paras)
        sub_chunks.append(_create_chunk(
            f"{chunk_id_base}-{sub_idx}" if sub_idx > 0 else chunk_id_base,
            text, ts_number, release, version, section, section_title,
            chunk_type, page,
        ))

    return sub_chunks if sub_chunks else [_create_chunk(
        chunk_id_base, chunk_text, ts_number, release, version,
        section, section_title, chunk_type, page,
    )]

def _split_by_sections(doc: ParsedDocument) -> List[Chunk]:
    chunks: List[Chunk] = []
    current_section = "0"
    current_section_title = ""
    current_chunk_type = "section_content"
    current_lines: List[str] = []
    current_page = 1
    chunk_sequence = 0

    for page in doc.pages:
        for line in page.text.split("\n"):
            stripped = line.strip()

            if _is_boundary_line(stripped):
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text and not _is_undesirable_standalone(text):
                        chunk_id = f"{doc.ts_number}.{current_section}.{current_chunk_type}.{chunk_sequence:03d}"
                        sub_chunks = _split_large_chunk(
                            text, MAX_CHUNK_WORDS, OVERLAP_WORDS,
                            chunk_id, doc.ts_number, doc.release, doc.version,
                            current_section, current_section_title, current_chunk_type, current_page,
                        )
                        chunks.extend([c for c in sub_chunks if c is not None])
                        chunk_sequence += 1

                current_lines = []
                current_chunk_type = _detect_chunk_type(stripped, "")
                if SECTION_RE.match(stripped):
                    m = SECTION_RE.match(stripped)
                    current_section = m.group(1)
                    current_section_title = m.group(2).strip()
                    if current_chunk_type == "section_content":
                        current_chunk_type = "section_content"
                continue

            if _is_undesirable_standalone(stripped):
                continue

            if SECTION_RE.match(stripped):
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text and not _is_undesirable_standalone(text):
                        chunk_id = f"{doc.ts_number}.{current_section}.{current_chunk_type}.{chunk_sequence:03d}"
                        sub_chunks = _split_large_chunk(
                            text, MAX_CHUNK_WORDS, OVERLAP_WORDS,
                            chunk_id, doc.ts_number, doc.release, doc.version,
                            current_section, current_section_title, current_chunk_type, current_page,
                        )
                        chunks.extend([c for c in sub_chunks if c is not None])
                        chunk_sequence += 1

                m = SECTION_RE.match(stripped)
                current_section = m.group(1)
                current_section_title = m.group(2).strip()
                current_lines = [line]
                current_chunk_type = "event_definition" if "event" in current_section_title.lower() else "section_content"
                current_page = page.page_number
                continue

            if stripped.startswith("|"):
                if current_lines and current_chunk_type != "table":
                    text = "\n".join(current_lines).strip()
                    if text and not _is_undesirable_standalone(text):
                        chunk_id = f"{doc.ts_number}.{current_section}.{current_chunk_type}.{chunk_sequence:03d}"
                        sub_chunks = _split_large_chunk(
                            text, MAX_CHUNK_WORDS, OVERLAP_WORDS,
                            chunk_id, doc.ts_number, doc.release, doc.version,
                            current_section, current_section_title, current_chunk_type, current_page,
                        )
                        chunks.extend([c for c in sub_chunks if c is not None])
                        chunk_sequence += 1
                current_lines = [line]
                current_chunk_type = "table"
                current_page = page.page_number
                continue

            line_type = _detect_chunk_type(stripped, "\n".join(current_lines[-3:]) if current_lines else "")
            if line_type != current_chunk_type and current_lines:
                text = "\n".join(current_lines).strip()
                if text and not _is_undesirable_standalone(text) and _count_words(text) >= MIN_CHUNK_WORDS:
                    chunk_id = f"{doc.ts_number}.{current_section}.{current_chunk_type}.{chunk_sequence:03d}"
                    sub_chunks = _split_large_chunk(
                        text, MAX_CHUNK_WORDS, OVERLAP_WORDS,
                        chunk_id, doc.ts_number, doc.release, doc.version,
                        current_section, current_section_title, current_chunk_type, current_page,
                    )
                    chunks.extend([c for c in sub_chunks if c is not None])
                    chunk_sequence += 1
                current_lines = [line]
                current_chunk_type = line_type
            else:
                current_lines.append(line)
                if current_page != page.page_number:
                    current_page = page.page_number

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text and not _is_undesirable_standalone(text):
            chunk_id = f"{doc.ts_number}.{current_section}.{current_chunk_type}.{chunk_sequence:03d}"
            sub_chunks = _split_large_chunk(
                text, MAX_CHUNK_WORDS, OVERLAP_WORDS,
                chunk_id, doc.ts_number, doc.release, doc.version,
                current_section, current_section_title, current_chunk_type, current_page,
            )
            chunks.extend([c for c in sub_chunks if c is not None])

    return chunks

def _split_long_chunk(chunk: Chunk, max_tokens: int, overlap_tokens: int) -> List[Chunk]:
    if chunk.token_count <= max_tokens:
        return [chunk]
    max_words = int(max_tokens * 1.33)
    overlap_words = int(overlap_tokens * 1.33)
    paragraphs = _split_paragraphs(chunk.text)
    if len(paragraphs) <= 1:
        return [chunk]

    sub_chunks = []
    current_paras = []
    current_words = 0
    sub_idx = 0

    for para in paragraphs:
        para_words = _count_words(para)
        if current_paras and current_words + para_words > max_words and current_words >= MIN_CHUNK_WORDS:
            text = "\n\n".join(current_paras)
            sub_chunks.append(_create_chunk(
                f"{chunk.chunk_id}-{sub_idx}" if sub_idx > 0 else chunk.chunk_id,
                text, chunk.ts_number, chunk.release, chunk.version,
                chunk.section, chunk.section_title, chunk.chunk_type, chunk.page,
            ))
            sub_idx += 1
            overlap_start = max(0, len(current_paras) - max(1, overlap_words // 10))
            current_paras = current_paras[overlap_start:]
            current_words = sum(_count_words(p) for p in current_paras)

        current_paras.append(para)
        current_words += para_words

    if current_paras:
        text = "\n\n".join(current_paras)
        sub_chunks.append(_create_chunk(
            f"{chunk.chunk_id}-{sub_idx}" if sub_idx > 0 else chunk.chunk_id,
            text, chunk.ts_number, chunk.release, chunk.version,
            chunk.section, chunk.section_title, chunk.chunk_type, chunk.page,
        ))

    return sub_chunks if sub_chunks else [chunk]

def chunk_document(doc: ParsedDocument, max_tokens: int = CHUNK_SIZE, overlap_tokens: int = CHUNK_OVERLAP) -> List[Chunk]:
    section_chunks = _split_by_sections(doc)
    final = []
    for ch in section_chunks:
        final.extend(_split_long_chunk(ch, max_tokens, overlap_tokens))
    return [c for c in final if c is not None]