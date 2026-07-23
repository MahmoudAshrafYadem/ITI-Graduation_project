"""Wrapper around SentenceTransformer (BGE)"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from .config import EMBEDDING_MODEL

class Embedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        return self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress,
            normalize_embeddings=True, convert_to_numpy=True,
        )

    def encode_query(self, query: str) -> np.ndarray:
        return self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]