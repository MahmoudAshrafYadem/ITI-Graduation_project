"""Local Qdrant vector store (No Docker needed)"""
import time
import uuid
import hashlib
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)
from .config import QDRANT_PATH, QDRANT_COLLECTION, EMBEDDING_DIM, TOP_K
from .chunker import Chunk
from . import profiler

SECTION_TITLE_BOOST_WORDS = [
    "event", "triggered", "condition", "threshold", "offset",
    "measurement", "reporting", "timer", "procedure", "reconfiguration",
    "handover", "connection", "setup", "release", "establishment",
    "mobility", "drx", "power", "control", "scheduling",
]

class VectorStore:
    def __init__(self):
        profiler.stage_start("Init Qdrant")
        self.client = QdrantClient(path=str(QDRANT_PATH))
        profiler.stage_end("Init Qdrant", {"path": str(QDRANT_PATH)})

        collections = self.client.get_collections().collections
        print("Qdrant collections:", [c.name for c in collections])

        try:
            info = self.client.get_collection(QDRANT_COLLECTION)
            print("Points count:", info.points_count)
        except Exception as e:
            print(e)

    def create_collection(self, collection: str = QDRANT_COLLECTION, dim: int = EMBEDDING_DIM, recreate: bool = True) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if collection in existing:
            if recreate:
                self.client.delete_collection(collection)
            else:
                return
        self.client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def upsert_chunks(self, chunks: List[Chunk], embeddings, collection: str = QDRANT_COLLECTION, batch_size: int = 100) -> None:
        profiler.stage_start("Upsert Chunks")
        total = 0
        for start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[start:start + batch_size]
            batch_vecs = embeddings[start:start + batch_size]
            points = [
                PointStruct(
                    id=str(uuid.uuid4()), vector=vec.tolist(),
                    payload={
                        "text": c.text, "ts_number": c.ts_number, "release": c.release,
                        "version": c.version, "section": c.section,
                        "section_title": c.section_title,
                        "page": c.page, "chunk_id": c.chunk_id,
                        "chunk_hash": self._chunk_hash(c.text),
                    },
                ) for c, vec in zip(batch_chunks, batch_vecs)
            ]
            self.client.upsert(collection_name=collection, points=points)
            total += len(batch_chunks)
        profiler.stage_end("Upsert Chunks", {"total": total})

    def search(self, query_vector, top_k: int = TOP_K, collection: str = QDRANT_COLLECTION,
               ts_filter: Optional[str] = None, release_filter: Optional[str] = None,
               query_text: str = "") -> List:
        profiler.stage_start("Qdrant Search")
        must = []
        if ts_filter:
            must.append(FieldCondition(key="ts_number", match=MatchValue(value=ts_filter)))
        if release_filter:
            must.append(FieldCondition(key="release", match=MatchValue(value=release_filter)))
        query_filter = Filter(must=must) if must else None
        results = self.client.search(
            collection_name=collection, query_vector=query_vector.tolist(),
            limit=top_k * 2, query_filter=query_filter, with_payload=True,
        )
        profiler.stage_end("Qdrant Search", {"fetched": len(results), "top_k": top_k})
        return results

    def remove_duplicates(self, chunks: List, max_page_duplicates: int = 2) -> List:
        profiler.stage_start("Remove Duplicates")
        seen_hashes = {}
        seen_pages = {}
        deduped = []
        removed = 0
        for result in chunks:
            payload = result.payload
            chunk_hash = payload.get("chunk_hash", "")
            page = payload.get("page", 0)
            section = payload.get("section", "")

            dup_key = (chunk_hash, page)
            if dup_key in seen_hashes:
                removed += 1
                continue

            page_key = (page, section)
            if page_key in seen_pages:
                seen_pages[page_key] += 1
                if seen_pages[page_key] > max_page_duplicates:
                    removed += 1
                    continue
            else:
                seen_pages[page_key] = 1

            seen_hashes[dup_key] = True
            deduped.append(result)

        profiler.stage_end("Remove Duplicates", {"input": len(chunks), "output": len(deduped), "removed": removed})
        return deduped

    def boost_by_section_title(self, results: List, query_text: str) -> List:
        if not query_text:
            return results
        query_lower = query_text.lower()
        boosted = []
        for result in results:
            score = result.score
            section_title = result.payload.get("section_title", "").lower()
            ts_number = result.payload.get("ts_number", "")
            for boost_word in SECTION_TITLE_BOOST_WORDS:
                if boost_word in query_lower and boost_word in section_title:
                    score = min(score * 1.2, 1.0)
                    break
            if "lte" in query_lower or "36.331" in query_lower or "ts 36" in query_lower:
                if ts_number == "36.331":
                    score = min(score * 1.3, 1.0)
                elif ts_number in ("38.331", "38.211", "38.401"):
                    score = max(score * 0.7, 0.0)
            if "nr" in query_lower or "38.331" in query_lower or "5g" in query_lower or "new radio" in query_lower:
                if ts_number in ("38.331", "38.211", "38.401"):
                    score = min(score * 1.3, 1.0)
                elif ts_number == "36.331":
                    score = max(score * 0.7, 0.0)
            boosted.append((result, score))
        boosted.sort(key=lambda x: x[1], reverse=True)
        profiler.stage_end("Metadata Boost", {"query_terms_matched": sum(1 for w in SECTION_TITLE_BOOST_WORDS if w in query_lower)})
        return [r for r, _ in boosted]

    @staticmethod
    def _chunk_hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:16]