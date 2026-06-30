"""Embedding generation service using OpenAI's text-embedding-3-small.

Supports single and batch embedding generation with retry logic
and token usage tracking for cost estimation.
"""

import logging
import asyncio
from typing import List

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize async OpenAI client
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Get or create the async OpenAI client (lazy singleton)."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    return _client


# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_BATCH_SIZE = 100  # OpenAI batch limit


class EmbeddingError(Exception):
    """Raised when embedding generation fails after all retries."""
    pass


async def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for a single text string.

    Calls OpenAI text-embedding-3-small and returns a 1536-dim vector.

    Args:
        text: Input text to embed.

    Returns:
        List of 1536 floats representing the embedding vector.

    Raises:
        EmbeddingError: If embedding generation fails after retries.
    """
    result = await generate_embeddings_batch([text])
    return result[0]


async def generate_embeddings_batch(
    texts: List[str],
) -> List[List[float]]:
    """Generate embedding vectors for a batch of texts.

    Uses OpenAI's batch embedding API for efficiency.
    Includes retry logic with exponential backoff for API failures.
    Splits large batches into sub-batches of MAX_BATCH_SIZE.

    Args:
        texts: List of input texts to embed.

    Returns:
        List of embedding vectors (each 1536 floats), in the same order.

    Raises:
        EmbeddingError: If embedding generation fails after retries.
        ValueError: If texts list is empty.
    """
    if not texts:
        raise ValueError("Cannot generate embeddings for empty text list")

    client = _get_client()
    all_embeddings: List[List[float]] = []
    total_tokens = 0

    # Process in sub-batches to stay within API limits
    for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[batch_start:batch_start + MAX_BATCH_SIZE]
        batch_embeddings = await _embed_with_retry(client, batch)
        all_embeddings.extend(batch_embeddings["embeddings"])
        total_tokens += batch_embeddings["token_count"]

    logger.info(
        "Generated %d embeddings, total tokens used: %d",
        len(all_embeddings),
        total_tokens,
    )

    return all_embeddings


async def _embed_with_retry(
    client: AsyncOpenAI,
    texts: List[str],
) -> dict:
    """Call the OpenAI embedding API with exponential backoff retry.

    Args:
        client: Async OpenAI client.
        texts: Batch of texts to embed.

    Returns:
        Dict with "embeddings" (list of vectors) and "token_count" (int).

    Raises:
        EmbeddingError: After all retries are exhausted.
    """
    if settings.OPENAI_API_KEY in ("your-key-here", "", None):
        import numpy as np
        logger.info("Using MOCK embeddings for batch (OPENAI_API_KEY not configured)")
        return {
            "embeddings": [np.random.rand(1536).tolist() for _ in texts],
            "token_count": len(" ".join(texts)) // 4,
        }

    last_exception: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.embeddings.create(
                input=texts,
                model=settings.EMBEDDING_MODEL,
            )

            # Extract embeddings in correct order
            embeddings = [item.embedding for item in response.data]
            token_count = response.usage.total_tokens if response.usage else 0

            if attempt > 0:
                logger.info(
                    "Embedding API succeeded on attempt %d", attempt + 1
                )

            return {
                "embeddings": embeddings,
                "token_count": token_count,
            }

        except RateLimitError as e:
            last_exception = e
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(
                "OpenAI rate limit hit (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                MAX_RETRIES,
                delay,
                str(e),
            )
            await asyncio.sleep(delay)

        except APIConnectionError as e:
            last_exception = e
            delay = BASE_DELAY * (2 ** attempt)
            logger.warning(
                "OpenAI connection error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                MAX_RETRIES,
                delay,
                str(e),
            )
            await asyncio.sleep(delay)

        except APIError as e:
            last_exception = e
            if e.status_code and e.status_code >= 500:
                # Server error — retry
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "OpenAI server error %d (attempt %d/%d), retrying in %.1fs",
                    e.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                # Client error — don't retry
                logger.error(
                    "OpenAI client error %d: %s",
                    e.status_code,
                    str(e),
                )
                raise EmbeddingError(
                    f"OpenAI API error ({e.status_code}): {str(e)}"
                )

    # All retries exhausted
    logger.error(
        "Embedding generation failed after %d attempts: %s",
        MAX_RETRIES,
        str(last_exception),
    )
    raise EmbeddingError(
        f"Embedding generation failed after {MAX_RETRIES} attempts: "
        f"{str(last_exception)}"
    )


def estimate_embedding_cost(token_count: int) -> float:
    """Estimate the cost of embedding generation in USD.

    Based on OpenAI text-embedding-3-small pricing: $0.02 per 1M tokens.

    Args:
        token_count: Total tokens used.

    Returns:
        Estimated cost in USD.
    """
    cost_per_million = 0.02
    return (token_count / 1_000_000) * cost_per_million
