"""Cost and latency tracking utilities.

Provides token-cost estimation for OpenAI API calls used in the RAG pipeline.
Pricing is based on OpenAI's published rates as of 2024-12:
  - text-embedding-3-small: $0.02 / 1M tokens
  - gpt-4o-mini input:      $0.15 / 1M tokens
  - gpt-4o-mini output:     $0.60 / 1M tokens
"""

from decimal import Decimal


# Pricing per 1 million tokens (USD)
EMBEDDING_COST_PER_M = Decimal("0.02")
COMPLETION_INPUT_COST_PER_M = Decimal("0.15")
COMPLETION_OUTPUT_COST_PER_M = Decimal("0.60")

_ONE_MILLION = Decimal("1000000")


def estimate_query_cost(
    embedding_tokens: int,
    completion_prompt_tokens: int,
    completion_output_tokens: int,
) -> Decimal:
    """Estimate the total cost of a RAG query in USD.

    Args:
        embedding_tokens: Tokens used for the query embedding.
        completion_prompt_tokens: Input tokens for the chat completion.
        completion_output_tokens: Output tokens from the chat completion.

    Returns:
        Estimated cost in USD as a Decimal for precision.
    """
    embedding_cost = (Decimal(embedding_tokens) / _ONE_MILLION) * EMBEDDING_COST_PER_M
    input_cost = (Decimal(completion_prompt_tokens) / _ONE_MILLION) * COMPLETION_INPUT_COST_PER_M
    output_cost = (Decimal(completion_output_tokens) / _ONE_MILLION) * COMPLETION_OUTPUT_COST_PER_M

    return embedding_cost + input_cost + output_cost
