import os
from pathlib import Path

from dotenv import load_dotenv

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

project_root_env = PROJECT_ROOT / ".env"
load_dotenv(project_root_env if project_root_env.exists() else None, override=True)


class Config:
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL_NAME: str = os.environ.get("LLM_MODEL_NAME", "ministral-3:14b-cloud")

    EMBEDDING_MODEL_NAME: str = os.environ.get("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")

    HYBRID_SEARCH_MULTIPLIER: int = int(os.environ.get("HYBRID_SEARCH_MULTIPLIER", "100"))
    LLM_RERANK_MULTIPLIER: int = int(os.environ.get("LLM_RERANK_MULTIPLIER", "2"))

    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 100

    DATA_DIR: Path = PROJECT_ROOT / "data"

    CHROMA_BASE_URL: str = os.environ.get("CHROMA_BASE_URL", "http://localhost")
    CHROMA_SERVER_PORT: int = int(os.environ.get("CHROMA_SERVER_PORT", "6333"))
    CHROMA_PERSIST_DIR: str | None = os.environ.get("CHROMA_PERSIST_DIR")

    BM25_CACHE_DIR: Path = PROJECT_ROOT / "cache"
    BM25_SKIP_COLLECTIONS: list[str] = ["faq"]

config = Config()
