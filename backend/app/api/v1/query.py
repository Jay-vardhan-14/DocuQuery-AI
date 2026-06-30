"""RAG query API routes.

Endpoints:
    POST /api/v1/query       — Submit a question, get a RAG response
    GET  /api/v1/query/history — View the current user's query history

Both endpoints require JWT authentication.
The query endpoint enforces rate limiting and prompt injection detection.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.query import (
    QueryHistoryItem,
    QueryRequest,
    QueryResponse,
)
from app.security.prompt_guard import detect_prompt_injection
from app.security.rate_limiter import check_rate_limit
from app.services.audit_service import get_user_query_history
from app.services.rag_service import query_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    summary="Submit a question to the RAG pipeline",
    responses={
        400: {"description": "Prompt injection detected"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def ask_question(
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Submit a natural-language question and receive a RAG response.

    The pipeline:
      1. Rate limit check (20 req/min per user via Redis)
      2. Prompt injection detection (13+ regex patterns)
      3. RBAC-filtered vector search for relevant chunks
      4. LLM answer generation with citations
      5. Audit log creation

    The user only sees answers derived from documents their role
    is authorized to access.
    """
    # Step 1: Rate limiting
    await check_rate_limit(current_user.id)

    # Step 2: Prompt injection guard
    is_injection, reason = detect_prompt_injection(body.question)
    if is_injection:
        logger.warning(
            "Prompt injection blocked for user %s: reason=%s, text=%s",
            current_user.email,
            reason,
            body.question[:100],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query rejected: {reason}",
        )

    # Step 3: Execute RAG pipeline
    result = await query_pipeline(
        question=body.question,
        user_role=current_user.role,
        user_id=current_user.id,
        db=db,
    )

    return QueryResponse(**result)


@router.get(
    "/history",
    response_model=list[QueryHistoryItem],
    summary="Get current user's query history",
)
async def get_query_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QueryHistoryItem]:
    """Return the current user's recent query history.

    Returns the 20 most recent queries, sorted by created_at descending.
    Each entry includes the query text, response summary, latency,
    and timestamp.
    """
    history = await get_user_query_history(
        user_id=current_user.id,
        db=db,
        limit=20,
    )
    return [QueryHistoryItem.model_validate(entry) for entry in history]
