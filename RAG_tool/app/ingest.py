"""CLI to ingest PDFs"""
import argparse
import sys
from pathlib import Path
from .config import DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from .parser import parse_pdf
from .chunker import chunk_document
from .embeddings import Embedder
from .retriever import VectorStore

def ingest_pdf(pdf_path: str, embedder: Embedder, store: VectorStore) -> int:
    path = Path(pdf_path)
    doc = parse_pdf(pdf_path)
    print("--------------------------------")
    print(f"Processing:\n\n{path.name}\n\nTS Number : {doc.ts_number}\n\nRelease   : {doc.release}\n\nPages      : {len(doc.pages)}\n")
    print("--------------------------------")

    print("   Chunking (section-aware) ...")
    chunks = chunk_document(doc, max_tokens=CHUNK_SIZE, overlap_tokens=CHUNK_OVERLAP)
    print(f"    {len(chunks)} chunks")

    print("   Embedding ...")
    texts = [c.text for c in chunks]
    embeddings = embedder.encode(texts)

    print("   Upserting to local Qdrant ...")
    store.upsert_chunks(chunks, embeddings)
    print(f"    ✓ Stored {len(chunks)} chunks")
    return len(chunks)

def main():
    p = argparse.ArgumentParser(description="Ingest 3GPP PDFs into local Qdrant")
    p.add_argument("--pdf", type=str, help="Path to a single PDF")
    p.add_argument("--all", action="store_true", help="Ingest every PDF in data/")
    p.add_argument("--no-recreate", action="store_true", help="Don't drop existing collection")
    args = p.parse_args()

    if not args.pdf and not args.all:
        p.print_help()
        sys.exit(1)

    embedder = Embedder()
    store = VectorStore()
    store.create_collection(recreate=not args.no_recreate)

    if args.pdf:
        ingest_pdf(args.pdf, embedder, store)
    else:
        pdfs = sorted(DATA_DIR.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs found in {DATA_DIR}")
            sys.exit(1)
        print(f"Found {len(pdfs)} PDFs in {DATA_DIR}")
        total = 0
        for path in pdfs:
            total += ingest_pdf(str(path), embedder, store)
        print(f"\n✓ Ingestion complete. Total chunks: {total}")

if __name__ == "__main__":
    main()