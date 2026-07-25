"""Cross-encoder reranker with batch inference and device auto-selection"""
import time
import os
from typing import List
from sentence_transformers import CrossEncoder
from .config import TOP_K
from . import profiler

BATCH_SIZE = 32

def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "CUDA"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "MPS"
    except ImportError:
        pass
    return "CPU"

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        profiler.stage_start("Load Reranker Model")
        self.model_name = model_name
        self.device = _detect_device()
        self.model = CrossEncoder(model_name, device=self.device if self.device != "CPU" else None)
        profiler.stage_end("Load Reranker Model", {"device": self.device})

    def rerank(self, query: str, chunks: List[dict], top_k: int = TOP_K) -> List[dict]:
        profiler.stage_start("Reranking")
        if not chunks:
            profiler.stage_end("Reranking", {"returned": 0})
            return []
        pairs = [[query, c["text"]] for c in chunks]
        predict_start = time.perf_counter()
        scores = self.model.predict(pairs, batch_size=BATCH_SIZE, show_progress_bar=False)
        predict_ms = (time.perf_counter() - predict_start) * 1000
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        sort_start = time.perf_counter()
        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        sort_ms = (time.perf_counter() - sort_start) * 1000
        result = reranked[:top_k]
        profiler.stage_end("Reranking", {
            "input": len(chunks),
            "returned": len(result),
            "predict_ms": f"{predict_ms:.1f}",
            "sort_ms": f"{sort_ms:.1f}",
            "device": self.device,
        })
        return result