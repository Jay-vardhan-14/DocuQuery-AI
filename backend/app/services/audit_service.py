"""Audit logging service for the RAG query pipeline.

Provides:
  - log_query(): persist an audit record after every RAG query
  - get_user_query_history(): fetch recent queries for a user
"""

import logging
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_query(
    user_id: UUID,
    query_text: str,
    chunk_ids: List[UUID],
    document_ids: List[UUID],
    response_summary: str,
    latency_ms: int,
    tokens_used: Optional[int],
    cost_usd: Optional[Decimal],
    db: AsyncSession,
) -> Optional[AuditLog]:
    """Create an audit log entry for a RAG query.

    This is intentionally fire-and-forget: errors are logged
    but never raised, so audit failures don't break the query flow.

    Args:
        user_id: UUID of the querying user.
        query_text: The user's original question.
        chunk_ids: IDs of retrieved document chunks.
        document_ids: IDs of parent documents for retrieved chunks.
        response_summary: First 200 chars of the generated answer.
        latency_ms: Total pipeline latency in milliseconds.
        tokens_used: Total tokens consumed (embedding + completion).
        cost_usd: Estimated cost in USD.
        db: Async database session.

    Returns:
        The created AuditLog record, or None if logging failed.
    """
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            query_text=query_text,
            retrieved_chunk_ids=chunk_ids,
            retrieved_document_ids=document_ids,
            response_summary=response_summary[:200] if response_summary else None,
            latency_ms=latency_ms,
            total_tokens_used=tokens_used,
            estimated_cost_usd=cost_usd,
        )
        db.add(audit_entry)
        await db.commit()
        await db.refresh(audit_entry)

        logger.info(
            "Audit log created: id=%s, user=%s, latency=%dms",
            audit_entry.id,
            user_id,
            latency_ms,
        )
        return audit_entry

    except Exception as e:
        logger.error(
            "Failed to create audit log for user %s: %s",
            user_id,
            str(e),
        )
        # Roll back the failed audit insert so the session stays usable
        await db.rollback()
        return None


async def get_user_query_history(
    user_id: UUID,
    db: AsyncSession,
    limit: int = 20,
) -> List[AuditLog]:
    """Fetch recent query history for a user.

    Args:
        user_id: UUID of the user.
        db: Async database session.
        limit: Maximum number of entries to return (default 20).

    Returns:
        List of AuditLog records, most recent first.
    """
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
