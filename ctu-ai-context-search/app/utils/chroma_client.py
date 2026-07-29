import logging
from pathlib import Path
from typing import Optional

import chromadb

from app.config import config
from app.utils.embeddings import EmbeddingModel

logger = logging.getLogger(__name__)


class ChromaClient:
    """ChromaDB client wrapper. Uses persistent client if CHROMA_PERSIST_DIR is set, otherwise HTTP."""

    _instance: Optional["ChromaClient"] = None

    def __init__(self):
        if config.CHROMA_PERSIST_DIR:
            persist_path = Path(config.CHROMA_PERSIST_DIR)
            persist_path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(persist_path))
            logger.info(f"ChromaDB client initialized with persistent storage at: {persist_path}")
        else:
            self.client = chromadb.HttpClient(host=config.CHROMA_BASE_URL, port=config.CHROMA_SERVER_PORT)
            logger.info(f"ChromaDB client initialized with base URL: {config.CHROMA_BASE_URL}:{config.CHROMA_SERVER_PORT}")
        self.embedding_model = EmbeddingModel.get_instance()

    @classmethod
    def get_instance(cls) -> "ChromaClient":
        """Get singleton instance of ChromaClient."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get or create a collection by name."""
        collection = self.client.get_or_create_collection(name=name)
        logger.debug(f"Collection '{name}' accessed/created")
        return collection

    def list_collections(self) -> list[str]:
        """List all collection names."""
        collections = self.client.list_collections()
        return [col.name for col in collections]

    def delete_collection(self, name: str) -> None:
        """Delete a collection by name."""
        self.client.delete_collection(name=name)
        logger.info(f"Collection '{name}' deleted")

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """Add documents to a collection."""
        collection = self.get_or_create_collection(collection_name)
        embeddings = self.embedding_model.embed_documents(documents)

        collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(documents)} documents to collection '{collection_name}'")

    def upsert_documents(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """Upsert documents to a collection (add or update)."""
        collection = self.get_or_create_collection(collection_name)
        embeddings = self.embedding_model.embed_documents(documents)

        collection.upsert(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(documents)} documents to collection '{collection_name}'")

    def update_document(
        self,
        collection_name: str,
        id: str,
        document: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Update a specific document in a collection."""
        collection = self.get_or_create_collection(collection_name)

        # Get existing document if not provided
        existing = collection.get(ids=[id])
        if not existing["documents"]:
            raise ValueError(f"Document with id '{id}' not found in collection '{collection_name}'")

        # Use existing document if not provided
        doc = document if document else existing["documents"][0]
        # Merge metadata if provided
        meta = metadata if metadata else existing["metadatas"][0] if existing["metadatas"] else None

        # Get embedding for the document
        embedding = self.embedding_model.embed_query(doc)

        collection.upsert(
            documents=[doc],
            embeddings=[embedding],
            ids=[id],
            metadatas=[meta] if meta else None,
        )
        logger.info(f"Updated document '{id}' in collection '{collection_name}'")

    def query(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
    ) -> dict:
        """Query a collection with a text query."""
        collection = self.get_or_create_collection(collection_name)
        query_embedding = self.embedding_model.embed_query(query_text)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        logger.debug(f"Query '{query_text}' returned {len(results['documents'][0])} results")
        return results

    def delete_document(self, collection_name: str, id: str) -> None:
        """Delete a specific document from a collection."""
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=[id])
        logger.info(f"Deleted document '{id}' from collection '{collection_name}'")

    def get_documents(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """Get documents from a collection with optional filters."""
        collection = self.get_or_create_collection(collection_name)
        results = collection.get(ids=ids, limit=limit)
        return results
