import logging
from typing import Optional

import torch
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import config

for lib in ("sentence_transformers", "transformers", "huggingface_hub", "httpx"):
    logging.getLogger(lib).setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """ChromaDB-compatible embedding model using SentenceTransformerEmbeddingFunction."""

    _instance: Optional["EmbeddingModel"] = None
    _device: Optional[str] = None

    def __init__(self, model_name: Optional[str] = None):
        if EmbeddingModel._device is None:
            EmbeddingModel._device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = EmbeddingModel._device
        self.model_name = model_name or config.EMBEDDING_MODEL_NAME
        self.model = SentenceTransformerEmbeddingFunction(
            model_name=self.model_name,
            device=self.device,
            normalize_embeddings=False
        )
        logger.info(f"Loading embedding model: {self.model_name} on {self.device}")

    @classmethod
    def get_instance(cls) -> "EmbeddingModel":
        """Get singleton instance of EmbeddingModel."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return self.model(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return self.model([text])[0]
