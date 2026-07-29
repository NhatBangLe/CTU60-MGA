import hashlib
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


class CollectionUpdater:
    """Updates an existing ChromaDB collection with new documents or deletes it.

    This class supports adding new markdown files to an existing collection,
    rebuilding the BM25 index accordingly. It does NOT auto-create collections.
    """

    HASH_LENGTH = 8
    DATETIME_FORMAT = "%Y%m%d_%H%M%S"

    def __init__(
        self,
        collection_name: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        headers_to_split_on: Optional[list[tuple[str, str]]] = None,
    ):
        self.collection_name = collection_name
        self.chunk_size = chunk_size or config.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or config.DEFAULT_CHUNK_OVERLAP
        self.headers_to_split_on = headers_to_split_on
        self.client = ChromaClient.get_instance()
        self.timestamp = datetime.now(timezone.utc).strftime(self.DATETIME_FORMAT)

    def collection_exists(self) -> bool:
        """Check if collection exists in ChromaDB."""
        return self.collection_name in self.client.list_collections()

    def generate_id(self, chunk: str, index: int = 0, file_mtime: float = 0.0) -> str:
        """Generate a deterministic ID: collection_name_datetime_index_mtime_content_hash."""
        content_hash = hashlib.sha256(chunk.encode()).hexdigest()
        mtime_hex = hex(int(file_mtime))[2:]
        return f"{self.collection_name}_{self.timestamp}_{index}_{mtime_hex}_{content_hash[:16]}"

    def find_markdown_files(self, data_dir: Union[str, Path]) -> list[Path]:
        """Recursively find all .md files in data_dir."""
        data_path = Path(data_dir).resolve()
        files = sorted(data_path.rglob("*.md"))
        logger.info(f"Found {len(files)} markdown files in {data_path}")
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

    def upsert_batch(
        self,
        all_chunks: list[str],
        all_ids: list[str],
        all_metadatas: list[dict],
        *,
        show_progress: bool = True,
    ) -> None:
        """Ingest documents in batches to ChromaDB using upsert.

        Upsert handles both new documents and updates to existing ones.
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

            self.client.upsert_documents(
                collection_name=self.collection_name,
                documents=batch_chunks,
                ids=batch_ids,
                metadatas=batch_metadatas,
            )
            batch_iter.set_postfix_str(f"{len(batch_chunks)} docs")

    def rebuild_bm25_index(
        self,
        chunks: list[str],
        ids: list[str],
        metadatas: list[dict],
    ) -> Path:
        """Rebuild BM25 index from all documents in collection.

        Loads existing index, adds new documents, and saves.
        """
        bm25_indexer = BM25Indexer.get_instance()

        if bm25_indexer.load_index(self.collection_name):
            bm25_indexer.add_documents(
                texts=chunks,
                ids=ids,
                metadatas=metadatas,
                collection_name=self.collection_name,
            )
            bm25_indexer.save_index(collection_name=self.collection_name)
            logger.info(f"Updated BM25 index for collection '{self.collection_name}'")
        else:
            bm25_indexer.index_documents(
                texts=chunks,
                ids=ids,
                metadatas=metadatas,
                collection_name=self.collection_name,
            )
            bm25_indexer.save_index(collection_name=self.collection_name)
            logger.info(f"Built new BM25 index for collection '{self.collection_name}'")

        return bm25_indexer.base_path / f"{self.collection_name}_bm25.pkl"

    def delete_collection(self) -> dict:
        """Delete the collection and its BM25 index.

        Returns:
            dict with deletion details.

        Raises:
            ValueError if collection does not exist.
        """
        if not self.collection_exists():
            raise ValueError(f"Collection '{self.collection_name}' does not exist.")

        self.client.delete_collection(self.collection_name)
        logger.info(f"Deleted collection: {self.collection_name}")

        bm25_indexer = BM25Indexer.get_instance()
        bm25_path = bm25_indexer.base_path / f"{self.collection_name}_bm25.pkl"
        if bm25_path.exists():
            bm25_path.unlink()
            logger.info(f"Deleted BM25 index at {bm25_path}")

        return {
            "collection": self.collection_name,
            "bm25_index_deleted": str(bm25_path),
        }

    def add_documents(
        self,
        data_dir: Union[str, Path],
        *,
        build_bm25: bool = True,
        show_progress: bool = True,
    ) -> dict:
        """Add new markdown files to an existing collection.

        Args:
            data_dir: Path to folder containing .md files (searched recursively).
            build_bm25: Whether to rebuild BM25 index. Defaults to True.

        Returns:
            dict with counts and paths.

        Raises:
            ValueError if collection does not exist.
        """
        if not self.collection_exists():
            raise ValueError(
                f"Collection '{self.collection_name}' does not exist. "
                "Use 'build' command to create a new collection first."
            )

        files = self.find_markdown_files(data_dir)
        if not files:
            logger.warning(f"No markdown files found in {data_dir}")
            return {"files": 0, "chunks": 0}

        all_chunks, all_ids, all_metadatas = self.collect_all_chunks(
            files, show_progress=show_progress
        )
        logger.info(f"Total chunks: {len(all_chunks)} from {len(files)} files")

        self.upsert_batch(
            all_chunks, all_ids, all_metadatas, show_progress=show_progress
        )

        bm25_path = None
        if build_bm25:
            bm25_path = self.rebuild_bm25_index(all_chunks, all_ids, all_metadatas)

        result = {
            "files": len(files),
            "chunks": len(all_chunks),
            "collection": self.collection_name,
        }
        if bm25_path:
            result["bm25_index"] = str(bm25_path)

        return result
