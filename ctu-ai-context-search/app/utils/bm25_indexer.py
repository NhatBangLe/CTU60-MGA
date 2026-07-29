"""LangChain BM25 indexer with Vietnamese tokenization support."""

import logging
import pickle
from pathlib import Path
from typing import Optional

from langchain_community.retrievers.bm25 import BM25Retriever

from app.config import config
from app.utils.text_utils import normalize_tokenize

logger = logging.getLogger(__name__)


class BM25Indexer:
    """LangChain BM25 retriever with Vietnamese tokenization.

    Uses LangChain's BM25Retriever with underthesea for Vietnamese NLP.
    Supports persistence to disk for fast reload.
    """

    _instance: Optional["BM25Indexer"] = None

    def __init__(self, persist_path: Optional[Path] = None):
        self.base_path = persist_path or config.BM25_CACHE_DIR
        self._indexes: dict[str, BM25Retriever] = {}
        self._documents: dict[str, list[str]] = {}
        self._ids: dict[str, list[str]] = {}
        self._metadatas: dict[str, list[dict]] = {}
        self._current_collection: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "BM25Indexer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _create_retriever(
        self,
        texts: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> BM25Retriever:
        return BM25Retriever.from_texts(
            texts=texts,
            metadatas=metadatas,
            ids=ids,
            preprocess_func=normalize_tokenize,
        )

    def index_documents(
        self,
        texts: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        if not texts:
            logger.warning("No texts provided for BM25 indexing")
            return

        collection_name = collection_name or "default"
        self._current_collection = collection_name
        metadatas = metadatas or [{} for _ in texts]

        self._documents[collection_name] = texts
        self._ids[collection_name] = ids
        self._metadatas[collection_name] = metadatas
        self._indexes[collection_name] = self._create_retriever(texts, ids, metadatas)

        logger.info(
            f"Indexed {len(texts)} documents in BM25 for collection '{collection_name}'"
        )

    def add_documents(
        self,
        texts: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        if not texts:
            logger.warning("No texts provided for BM25 indexing")
            return

        collection_name = collection_name or self._current_collection or "default"

        if collection_name in self._documents:
            self._documents[collection_name].extend(texts)
            self._ids[collection_name].extend(ids)
            self._metadatas[collection_name].extend(metadatas or [{} for _ in texts])
            self._indexes[collection_name] = self._create_retriever(
                self._documents[collection_name],
                self._ids[collection_name],
                self._metadatas[collection_name],
            )
            logger.info(
                f"Added {len(texts)} documents to BM25 index for collection "
                f"'{collection_name}' (total: {len(self._documents[collection_name])})"
            )
        else:
            self.index_documents(texts, ids, metadatas, collection_name)

    def remove_documents(
        self,
        ids: list[str],
        collection_name: Optional[str] = None,
    ) -> None:
        collection_name = collection_name or self._current_collection

        if collection_name not in self._documents:
            raise ValueError(f"No BM25 index found for collection '{collection_name}'")

        ids_to_remove = set(ids)
        keep_indices = [
            i
            for i, doc_id in enumerate(self._ids[collection_name])
            if doc_id not in ids_to_remove
        ]

        if len(keep_indices) == len(self._ids[collection_name]):
            logger.warning(
                f"None of the provided IDs found in collection '{collection_name}'"
            )
            return

        self._documents[collection_name] = [
            self._documents[collection_name][i] for i in keep_indices
        ]
        self._ids[collection_name] = [
            self._ids[collection_name][i] for i in keep_indices
        ]
        self._metadatas[collection_name] = [
            self._metadatas[collection_name][i] for i in keep_indices
        ]

        if self._documents[collection_name]:
            self._indexes[collection_name] = self._create_retriever(
                self._documents[collection_name],
                self._ids[collection_name],
                self._metadatas[collection_name],
            )
        else:
            del self._indexes[collection_name]
            del self._documents[collection_name]
            del self._ids[collection_name]
            del self._metadatas[collection_name]

        logger.info(
            f"Removed {len(ids_to_remove)} documents from BM25 index for collection "
            f"'{collection_name}' (remaining: {len(self._documents.get(collection_name, []))})"
        )

    def get_relevant_documents(
        self,
        query: str,
        k: int = 5,
        collection_name: Optional[str] = None,
    ) -> list:
        collection_name = collection_name or self._current_collection

        if collection_name not in self._indexes:
            logger.warning(f"BM25 index not found for collection '{collection_name}'")
            return []

        self._indexes[collection_name].k = k
        docs = self._indexes[collection_name].invoke(query)
        for doc in docs:
            doc.metadata["score_type"] = "bm25"
        return docs

    def save_index(self, collection_name: Optional[str] = None) -> Path:
        collection_name = collection_name or self._current_collection

        if collection_name not in self._indexes:
            logger.warning(f"No index to save for collection '{collection_name}'")
            return self.base_path

        state_path = self.base_path / f"{collection_name}_bm25.pkl"
        state = {
            "documents": self._documents.get(collection_name, []),
            "ids": self._ids.get(collection_name, []),
            "metadatas": self._metadatas.get(collection_name, []),
        }

        with open(state_path, "wb") as f:
            pickle.dump(state, f)

        logger.info(f"Saved BM25 index to {state_path}")
        return state_path

    def load_index(self, collection_name: str) -> bool:
        state_path = self.base_path / f"{collection_name}_bm25.pkl"

        if state_path.exists():
            try:
                with open(state_path, "rb") as f:
                    state = pickle.load(f)
                self.index_documents(
                    texts=state["documents"],
                    ids=state["ids"],
                    metadatas=state["metadatas"],
                    collection_name=collection_name,
                )
                logger.info(
                    f"Loaded BM25 index for '{collection_name}' from {state_path}"
                )
                return True
            except Exception as e:
                logger.warning(f"Failed to load BM25 index from {state_path}: {e}")

        from app.utils.chroma_client import ChromaClient

        chroma_client = ChromaClient.get_instance()
        collection = chroma_client.get_or_create_collection(collection_name)
        results = collection.get()

        if not results["documents"]:
            logger.warning(
                f"No documents in ChromaDB collection '{collection_name}' for BM25 rebuild"
            )
            return False

        self.index_documents(
            texts=results["documents"],
            ids=results["ids"],
            metadatas=results.get("metadatas"),
            collection_name=collection_name,
        )
        self.save_index(collection_name)
        logger.info(
            f"Rebuilt BM25 index for '{collection_name}' from ChromaDB ({len(results['documents'])} docs)"
        )
        return True

    def get_index_stats(self, collection_name: Optional[str] = None) -> dict:
        collection_name = collection_name or self._current_collection
        return {
            "collection": collection_name,
            "document_count": len(self._documents.get(collection_name, [])),
            "indexed": collection_name in self._indexes,
            "persist_path": str(self.base_path / f"{collection_name}_bm25.pkl"),
            "available_collections": list(self._indexes.keys()),
        }
