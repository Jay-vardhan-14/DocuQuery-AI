"""Document chunking service using LangChain's RecursiveCharacterTextSplitter.

Splits extracted document text into overlapping chunks suitable for
embedding and vector search. Uses tiktoken for accurate token counting.
"""

import logging
from typing import List, TypedDict

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)


class ChunkResult(TypedDict):
    """Typed dictionary for a document chunk."""
    content: str
    token_count: int
    chunk_index: int


# Initialize tiktoken encoder for token counting
# cl100k_base is the encoding used by text-embedding-3-small and gpt-4o-mini
_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string.

    Uses tiktoken with cl100k_base encoding (same as OpenAI models).

    Args:
        text: Input text to count tokens for.

    Returns:
        Number of tokens.
    """
    return len(_encoder.encode(text))


def chunk_document(text: str) -> List[ChunkResult]:
    """Split document text into overlapping chunks.

    Uses LangChain's RecursiveCharacterTextSplitter with token-based
    splitting (chunk_size=500 tokens, chunk_overlap=50 tokens).

    The splitter respects paragraph boundaries where possible,
    falling back to sentence and word boundaries.

    Args:
        text: Full document text to chunk.

    Returns:
        List of ChunkResult dicts with content, token_count, and chunk_index.

    Raises:
        ValueError: If the input text is empty or whitespace-only.
    """
    if not text or not text.strip():
        raise ValueError("Cannot chunk empty document text")

    # Create splitter with token-based length function
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=count_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True,
    )

    # Split the text
    raw_chunks = splitter.split_text(text)

    if not raw_chunks:
        # Edge case: text exists but splitter returned nothing
        # (shouldn't happen, but handle defensively)
        logger.warning("Splitter returned no chunks; using full text as single chunk")
        raw_chunks = [text.strip()]

    # Build result with token counts and indexes
    chunks: List[ChunkResult] = []
    for index, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        token_count = count_tokens(chunk_text)
        chunks.append(
            ChunkResult(
                content=chunk_text,
                token_count=token_count,
                chunk_index=index,
            )
        )

    logger.info(
        "Chunked document into %d chunks (avg %d tokens/chunk)",
        len(chunks),
        sum(c["token_count"] for c in chunks) // max(len(chunks), 1),
    )

    return chunks
