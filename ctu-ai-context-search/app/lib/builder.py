import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from tqdm import tqdm

from app.config import PROJECT_ROOT, config
from app.utils.bm25_indexer import BM25Indexer
from app.utils.chroma_client import ChromaClient
from app.utils.text_utils import split_text_into_chunks

logger = logging.getLogger(__name__)

BATCH_SIZE = 256


class StoreBuilder:
    """Builds dense and sparse vector stores from markdown files.

    This class coordinates both ChromaDB (dense vectors) and BM25 (sparse vectors).
    ChromaClient handles only vector storage. BM25Indexer is updated separately
    to maintain separation of concerns.
    """

    HASH_LENGTH = 8
    DATETIME_FORMAT = "%Y%m%d_%H%M%S"

    def __init__(
        self,
        data_dir: Union[str, Path],
        collection_name: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        headers_to_split_on: Optional[list[tuple[str, str]]] = None,
        reset: bool = False,
    ):
        self.data_dir = Path(data_dir).resolve()
        self.collection_name = collection_name
        self.chunk_size = chunk_size or config.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.DEFAULT_CHUNK_OVERLAP
        self.headers_to_split_on = headers_to_split_on
        self.reset = reset
        self.client = ChromaClient.get_instance()
        self.timestamp = datetime.now(timezone.utc).strftime(self.DATETIME_FORMAT)

    def generate_id(self, chunk: str, index: int = 0, file_mtime: float = 0.0) -> str:
        """Generate a deterministic ID: collection_name_datetime_index_mtime_content_hash."""
        content_hash = hashlib.sha256(chunk.encode()).hexdigest()
        mtime_hex = hex(int(file_mtime))[2:]
        return f"{self.collection_name}_{self.timestamp}_{index}_{mtime_hex}_{content_hash[:16]}"

    def generate_json_entries(
        self, chunks: list[str], ids: list[str], metadatas: list[dict]
    ) -> list[dict]:
        """Generate JSON entries for chunk tracking."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": id_,
                "content": chunk,
                "created_at": now,
                "updated_at": now,
                "metadata": {
                    "file_name": Path(meta.get("source", "")).name,
                    "file_path": meta.get("source", ""),
                },
            }
            for chunk, id_, meta in zip(chunks, ids, metadatas)
        ]

    def find_markdown_files(self) -> list[Path]:
        """Recursively find all .md files in data_dir."""
        files = sorted(self.data_dir.rglob("*.md"))
        logger.info(f"Found {len(files)} markdown files in {self.data_dir}")
        return files

    def process_file(self, file_path: Path) -> tuple[list[str], list[str], list[dict]]:
        """Read and chunk a single markdown file.

        Returns (chunks, ids, metadatas).
        """
        text = file_path.read_text(encoding="utf-8")
        chunks = split_text_into_chunks(
            text,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            headers_to_split_on=self.headers_to_split_on,
        )

        mtime = file_path.stat().st_mtime
        ids = [self.generate_id(chunk, i, mtime) for i, chunk in enumerate(chunks)]
        try:
            relative_path = str(file_path.relative_to(PROJECT_ROOT))
        except ValueError:
            relative_path = str(file_path.resolve().relative_to(PROJECT_ROOT.resolve()))
        metadatas = [
            {"source": relative_path, "chunk_index": i} for i in range(len(chunks))
        ]

        return chunks, ids, metadatas

    def ingest_batch(
        self,
        all_chunks: list[str],
        all_ids: list[str],
        all_metadatas: list[dict],
        *,
        collection_name: Optional[str] = None,
        show_progress: bool = True,
    ) -> None:
        """Ingest documents in batches to ChromaDB.

        Args:
            all_chunks: List of document texts.
            all_ids: List of document IDs.
            all_metadatas: List of metadata dicts.
            collection_name: Collection to ingest into.
            show_progress: Whether to show progress bar for embedding stage.
        """
        n_batches = (len(all_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        batch_iter = tqdm(
            range(0, len(all_chunks), BATCH_SIZE),
            desc="Embedding",
            unit="batch",
            total=n_batches,
            disable=not show_progress,
        )
        for i in batch_iter:
            batch_chunks = all_chunks[i : i + BATCH_SIZE]
            batch_ids = all_ids[i : i + BATCH_SIZE]
            batch_metadatas = all_metadatas[i : i + BATCH_SIZE]

            self.client.add_documents(
                collection_name=collection_name,
                documents=batch_chunks,
                ids=batch_ids,
                metadatas=batch_metadatas,
            )
            batch_iter.set_postfix_str(f"{len(batch_chunks)} docs")

    def update_bm25_incremental(
        self,
        texts: list[str],
        ids: list[str],
        metadatas: list[dict],
        collection_name: str,
    ) -> None:
        """Incrementally update BM25 index with new documents.

        Loads existing index if present, adds new documents, and saves.

        Args:
            texts: New document texts to add.
            ids: Document IDs.
            metadatas: Metadata dicts.
            collection_name: Collection name.
        """
        bm25_indexer = BM25Indexer.get_instance()
        if bm25_indexer.load_index(collection_name):
            # Existing index found, add documents incrementally
            bm25_indexer.add_documents(
                texts=texts,
                ids=ids,
                metadatas=metadatas,
                collection_name=collection_name,
            )
            bm25_indexer.save_index(collection_name)
            logger.info(
                f"Incrementally updated BM25 index for collection '{collection_name}'"
            )
        else:
            logger.debug(f"No existing BM25 index for collection '{collection_name}'")

    def delete_collection(self, name: str) -> None:
        """Delete a collection and its associated BM25 index."""
        try:
            self.client.delete_collection(name)
            logger.info(f"Deleted collection: {name}")
        except ValueError:
            pass

        # Also delete associated BM25 index file
        bm25_indexer = BM25Indexer.get_instance()
        state_path = bm25_indexer.base_path / f"{name}_bm25.pkl"
        if state_path.exists():
            state_path.unlink()
            logger.info(f"Deleted BM25 index at {state_path}")

    def build(self, build_bm25: bool = True, show_progress: bool = True) -> dict:
        """Build vector store from markdown files.

        Args:
            build_bm25: Whether to also build BM25 index. Defaults to True.
                       When False, BM25 index is not built or updated.

        Returns a summary dict with counts.
        """
        if self.reset:
            self.delete_collection(self.collection_name)

        files = self.find_markdown_files()
        if not files:
            logger.warning(f"No markdown files found in {self.data_dir}")
            return {"files": 0, "chunks": 0}

        all_chunks, all_ids, all_metadatas = self.collect_all_chunks(
            files, show_progress=show_progress
        )

        logger.info(f"Total chunks: {len(all_chunks)} from {len(files)} files")

        # Check if BM25 index already exists (for incremental update)
        bm25_indexer = BM25Indexer.get_instance()
        existing_bm25_path = bm25_indexer.base_path / f"{self.collection_name}_bm25.pkl"
        has_existing_bm25 = existing_bm25_path.exists()

        # Ingest documents to ChromaDB
        self.ingest_batch(
            all_chunks,
            all_ids,
            all_metadatas,
            collection_name=self.collection_name,
            show_progress=show_progress,
        )
        json_path = self.save_json_index(all_chunks, all_ids, all_metadatas)

        result = {
            "files": len(files),
            "chunks": len(all_chunks),
            "collection": self.collection_name,
            "json_index": str(json_path),
        }

        # Handle BM25: either build new or update existing incrementally
        if build_bm25:
            if has_existing_bm25:
                # Update existing index incrementally with all documents
                self.update_bm25_incremental(
                    all_chunks, all_ids, all_metadatas, self.collection_name
                )
                result["bm25_index"] = str(existing_bm25_path)
                result["bm25_mode"] = "incremental"
            else:
                # Build new BM25 index
                bm25_path = self.build_bm25_index(all_chunks, all_ids, all_metadatas)
                result["bm25_index"] = str(bm25_path)
                result["bm25_mode"] = "full"

        return result

    def build_bm25_index(
        self,
        chunks: list[str],
        ids: list[str],
        metadatas: list[dict],
        collection_name: Optional[str] = None,
    ) -> Path:
        """Build and persist BM25 index using LangChain BM25Retriever.

        Args:
            chunks: List of text chunks.
            ids: List of chunk IDs.
            metadatas: List of metadata dicts.
            collection_name: Collection name for the index. Defaults to self.collection_name.

        Returns:
            Path where BM25 index was saved.
        """
        collection_name = collection_name or self.collection_name
        logger.info(f"Building BM25 index for collection '{collection_name}'...")
        bm25_indexer = BM25Indexer.get_instance()
        bm25_indexer.index_documents(
            texts=chunks,
            ids=ids,
            metadatas=metadatas,
            collection_name=collection_name,
        )
        persist_path = bm25_indexer.save_index(collection_name=collection_name)
        logger.info(f"BM25 index saved to {persist_path}")
        return persist_path

    def collect_all_chunks(
        self, files: list[Path], *, show_progress: bool = True
    ) -> tuple[list[str], list[str], list[dict]]:
        """Collect all chunks from markdown files into parallel lists."""
        all_chunks: list[str] = []
        all_ids: list[str] = []
        all_metadatas: list[dict] = []

        file_iter = tqdm(
            files, desc="Processing files", unit="file", disable=not show_progress
        )
        for idx, file_path in enumerate(file_iter, 1):
            file_iter.set_postfix_str(file_path.name)
            chunks, ids, metadatas = self.process_file(file_path)
            all_chunks.extend(chunks)
            all_ids.extend(ids)
            all_metadatas.extend(metadatas)

        return all_chunks, all_ids, all_metadatas

    def save_json_index(
        self, chunks: list[str], ids: list[str], metadatas: list[dict]
    ) -> Path:
        """Save chunk index to JSON file in data directory."""
        entries = self.generate_json_entries(chunks, ids, metadatas)
        json_path = self.data_dir / f"{self.collection_name}_chunks.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved chunk index to {json_path}")
        return json_path

    def add_documents_incremental(
        self,
        texts: list[str],
        ids: list[str],
        metadatas: list[dict],
        collection_name: Optional[str] = None,
    ) -> None:
        """Add documents incrementally to both ChromaDB and BM25 index.

        This method is for adding new documents to an existing collection.
        It updates both the vector store and the BM25 index.

        Args:
            texts: List of document texts.
            ids: List of document IDs.
            metadatas: List of metadata dicts.
            collection_name: Collection name. Defaults to self.collection_name.
        """
        collection_name = collection_name or self.collection_name

        # Add to ChromaDB (dense vectors)
        self.client.add_documents(
            collection_name=collection_name,
            documents=texts,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info(
            f"Added {len(texts)} documents to ChromaDB collection '{collection_name}'"
        )

        # Incrementally update BM25 index
        self.update_bm25_incremental(texts, ids, metadatas, collection_name)
