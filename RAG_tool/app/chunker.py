"""Section-aware chunker"""
import re
from dataclasses import dataclass
from typing import List
from .parser import ParsedDocument

SECTION_RE = re.compile(r"^(\d+(?:\.\d+){0,4})\s+[A-Z]")

@dataclass
class Chunk:
    chunk_id: str
    text: str
    ts_number: str
    release: str
    version: str
    section: str
    page: int
    token_count: int = 0

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def _split_by_sections(doc: ParsedDocument) -> List[Chunk]:
    chunks: List[Chunk] = []
    current_section = "0"
    current_lines: List[str] = []
    current_page = 1

    def flush():
        if not current_lines:
            return
        text = "\n".join(current_lines).strip()
        if not text:
            return
        chunks.append(Chunk(
            chunk_id=f"{doc.ts_number}-{current_section}-p{current_page}",
            text=text, ts_number=doc.ts_number, release=doc.release,
            version=doc.version, section=current_section, page=current_page,
            token_count=estimate_tokens(text),
        ))

    for page in doc.pages:
        for line in page.text.split("\n"):
            m = SECTION_RE.match(line.strip())
            if m:
                flush()
                current_section = m.group(1)
                current_lines = [line]
                current_page = page.page_number
            else:
                if not current_lines and not line.strip():
                    continue
                current_lines.append(line)
                if current_page != page.page_number:
                    current_page = page.page_number
    flush()
    return chunks

def _split_long_chunk(chunk: Chunk, max_tokens: int, overlap_tokens: int) -> List[Chunk]:
    if chunk.token_count <= max_tokens:
        return [chunk]
    words = chunk.text.split()
    max_words = int(max_tokens * 1.33)
    overlap_words = int(overlap_tokens * 1.33)
    sub_chunks: List[Chunk] = []
    i = 0
    idx = 0
    while i < len(words):
        window = words[i:i + max_words]
        text = " ".join(window)
        sub_chunks.append(Chunk(
            chunk_id=f"{chunk.chunk_id}-{idx}", text=text, ts_number=chunk.ts_number,
            release=chunk.release, version=chunk.version, section=chunk.section,
            page=chunk.page, token_count=estimate_tokens(text),
        ))
        i += max(1, max_words - overlap_words)
        idx += 1
    return sub_chunks

def chunk_document(doc: ParsedDocument, max_tokens: int = 800, overlap_tokens: int = 100) -> List[Chunk]:
    section_chunks = _split_by_sections(doc)
    final: List[Chunk] = []
    for ch in section_chunks:
        final.extend(_split_long_chunk(ch, max_tokens, overlap_tokens))
    return final