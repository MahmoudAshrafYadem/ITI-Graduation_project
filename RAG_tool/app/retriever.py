"""Local Qdrant vector store (No Docker needed)"""
import uuid
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
)
from .config import QDRANT_PATH, QDRANT_COLLECTION, EMBEDDING_DIM
from .chunker import Chunk

class VectorStore:
    def __init__(self):
        # Run Qdrant locally in embedded mode (saves to disk)
        self.client = QdrantClient(path=str(QDRANT_PATH))
        print("Qdrant path:", QDRANT_PATH)

        collections = self.client.get_collections().collections
        print("Collections:", [c.name for c in collections])

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
        for start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[start:start + batch_size]
            batch_vecs = embeddings[start:start + batch_size]
            points = [
                PointStruct(
                    id=str(uuid.uuid4()), vector=vec.tolist(),
                    payload={
                        "text": c.text, "ts_number": c.ts_number, "release": c.release,
                        "version": c.version, "section": c.section, "page": c.page, "chunk_id": c.chunk_id,
                    },
                ) for c, vec in zip(batch_chunks, batch_vecs)
            ]
            self.client.upsert(collection_name=collection, points=points)

    def search(self, query_vector, top_k: int = 5, collection: str = QDRANT_COLLECTION, ts_filter: Optional[str] = None, release_filter: Optional[str] = None):
        must = []
        if ts_filter:
            must.append(FieldCondition(key="ts_number", match=MatchValue(value=ts_filter)))
        if release_filter:
            must.append(FieldCondition(key="release", match=MatchValue(value=release_filter)))
        query_filter = Filter(must=must) if must else None
        return self.client.search(
            collection_name=collection, query_vector=query_vector.tolist(),
            limit=top_k, query_filter=query_filter, with_payload=True,
        )