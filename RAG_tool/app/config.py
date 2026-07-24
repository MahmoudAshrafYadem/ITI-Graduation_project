"""Centralized configuration for local embedded Qdrant."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Local Qdrant Path (No Docker!)
QDRANT_PATH = BASE_DIR / "vector_db" / "qdrant_local"
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "telecom_3gpp")

# Embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# Ollama (local LLM server)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")

# Retrieval
TOP_K = int(os.getenv("TOP_K", "5"))

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))