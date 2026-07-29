"""Semantic search using ChromaDB vector search."""

import logging

from app.schemas import SearchResult
from app.utils.chroma_client import ChromaClient

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Semantic/dense search using ChromaDB.

    Uses ChromaDB's vector search for semantic similarity matching.
    """

    def __init__(self):
        self.chroma_client = ChromaClient.get_instance()

    @classmethod
    def get_instance(cls) -> "SemanticSearch":
        """Get singleton instance of SemanticSearch."""
        if not hasattr(cls, "_instance") or cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def search(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search collection using semantic vector search.

        Args:
            query: Search query text.
            collection_name: Name of the collection to search.
            top_k: Number of results to return.

        Returns:
            List of SearchResult objects sorted by relevance (highest first).
        """
        try:
            results = self.chroma_client.query(
                collection_name=collection_name,
                query_text=query,
                top_k=top_k,
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return []

        search_results = []
        if not results or not results.get("documents"):
            return []

        documents = results["documents"][0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        for i, doc in enumerate(documents):
            distance = distances[i] if i < len(distances) else 0.0
            score = 1.0 - distance
            search_results.append(
                SearchResult(
                    id=ids[i] if i < len(ids) else f"doc_{i}",
                    document=doc,
                    metadata=metadatas[i] if metadatas and i < len(metadatas) else {},
                    score=score,
                )
            )

        search_results.sort(key=lambda x: x.score, reverse=True)
        logger.debug(f"Semantic search returned {len(search_results)} results")
        return search_results
