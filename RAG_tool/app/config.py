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

# OpenRouter API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "3000"))

# Debug Mode: enables pipeline profiling, timing, and prompt statistics
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Performance Thresholds (seconds)
WARN_INFERENCE_THRESHOLD = float(os.getenv("WARN_INFERENCE_THRESHOLD", "20"))
WARN_PROMPT_THRESHOLD = int(os.getenv("WARN_PROMPT_THRESHOLD", "8000"))

# Optimization Parameters
MAX_PROMPT_TOKENS = int(os.getenv("MAX_PROMPT_TOKENS", "6000"))
REMOVE_DUPLICATES = os.getenv("REMOVE_DUPLICATES", "true").lower() == "true"
FILTER_ASN1 = os.getenv("FILTER_ASN1", "true").lower() == "true"
FILTER_CHANGE_HISTORY = os.getenv("FILTER_CHANGE_HISTORY", "true").lower() == "true"

# Retrieval
TOP_K = int(os.getenv("TOP_K", "7"))
FETCH_MULTIPLIER = int(os.getenv("FETCH_MULTIPLIER", "3"))

# Chunking
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "300"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
