"""Cross-encoder reranker"""
from typing import List
from sentence_transformers import CrossEncoder
from .config import TOP_K

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: List[dict], top_k: int = TOP_K) -> List[dict]:
        if not chunks:
            return []
        pairs = [[query, c["text"]] for c in chunks]
        scores = self.model.predict(pairs, show_progress_bar=False)
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]