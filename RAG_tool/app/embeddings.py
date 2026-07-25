"""Wrapper around SentenceTransformer (BGE)"""
from typing import List
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from .config import EMBEDDING_MODEL
from . import profiler

class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        profiler.stage_start("Load Embedding Model")
        self.model = SentenceTransformer(model_name)
        profiler.stage_end("Load Embedding Model")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        profiler.stage_start("Batch Embedding")
        result = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress,
            normalize_embeddings=True, convert_to_numpy=True,
        )
        profiler.stage_end("Batch Embedding", {"count": len(texts)})
        return result

    def encode_query(self, query: str) -> np.ndarray:
        profiler.stage_start("Query Embedding")
        result = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        profiler.stage_end("Query Embedding")
        return result