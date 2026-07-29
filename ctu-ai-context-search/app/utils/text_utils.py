import re
import string
import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple

from underthesea import word_tokenize
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import config

logger = logging.getLogger(__name__)

CHUNK_SIZE = config.DEFAULT_CHUNK_SIZE
CHUNK_OVERLAP = config.DEFAULT_CHUNK_OVERLAP

DEFAULT_HEADERS_TO_SPLIT_ON: List[Tuple[str, str]] = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3"),
]

STOPWORDS_FILE = Path(__file__).parent.parent / "data" / "vietnamese-stopwords.txt"

def load_stopwords() -> Set[str]:
    if not STOPWORDS_FILE.exists():
        return set()
    with open(STOPWORDS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())
    
VIETNAMESE_STOPWORDS = load_stopwords()


def tokenize(text: str) -> List[str]:
    """Underthesea Vietnamese tokenizer."""
    return word_tokenize(text)


def normalize_tokenize(text: str) -> List[str]:
    """Normalize: lowercase, remove punctuation, filter stopwords, tokenize."""
    text = text.lower()
    text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
    tokens = word_tokenize(text)
    return [t for t in tokens if t and t.lower() not in VIETNAMESE_STOPWORDS]


def split_text_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    headers_to_split_on: Optional[List[Tuple[str, str]]] = None,
) -> list[str]:
    """Split text using MarkdownHeaderTextSplitter then RecursiveCharacterTextSplitter."""
    if headers_to_split_on is None:
        headers_to_split_on = DEFAULT_HEADERS_TO_SPLIT_ON

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )
    header_chunks = header_splitter.split_text(text)

    char_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n", "\n",
            ".", ",", "!", "?",
            "(", ")", "[", "]", "{", "}",
            ":", ";", "/", "\\", "|", "_",
            "-", "+", "=", "*","<", ">", " "
        ],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    final_chunks = []
    for header_chunk in header_chunks:
        if len(header_chunk.page_content) <= chunk_size:
            final_chunks.append(header_chunk.page_content)
        else:
            sub_chunks = char_splitter.split_documents([header_chunk])
            final_chunks.extend([doc.page_content for doc in sub_chunks])

    return final_chunks
