"""Orchestrates the RAG pipeline"""
from typing import Optional
from .embeddings import Embedder
from .retriever import VectorStore
from .llm import OllamaLLM
from .reranker import Reranker
from .config import TOP_K

class TelecomRAG:
    def __init__(self):
        self.embedder = Embedder()
        self.store = VectorStore()
        self.llm = OllamaLLM()
        self.reranker = Reranker()

    def ask(self, question: str, top_k: int = TOP_K, ts_filter: Optional[str] = None, release_filter: Optional[str] = None) -> dict:
        query_vec = self.embedder.encode_query(question)
        fetch_k = top_k * 4
        hits = self.store.search(
            query_vector=query_vec, top_k=fetch_k,
            ts_filter=ts_filter, release_filter=release_filter,
        )

        if not hits:
            return {
                "answer": "I cannot find this in the supplied specifications.",
                "references": [], "chunks": [],
            }

        retrieved_chunks = [h.payload for h in hits]
        reranked_chunks = self.reranker.rerank(question, retrieved_chunks, top_k=top_k)

        references = []
        for c in reranked_chunks:
            references.append({
                "ts": c["ts_number"], "release": c["release"], "section": c["section"],
                "page": c["page"], "score": c.get("rerank_score", 0.0),
            })

        answer = self.llm.generate(question, reranked_chunks)

        return {
            "answer": answer, "references": references,
            "chunks": [
                {
                    "chunk_id": c["chunk_id"], "section": c["section"],
                    "preview": c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
                } for c in reranked_chunks
            ],
        }