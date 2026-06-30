"""Admin API routes.

Provides admin-only endpoints for:
  - User management (list, update role/status)
  - Audit log viewer with filtering
  - System metrics dashboard data

All endpoints require admin role via the require_admin dependency.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.models.audit_log import AuditLog
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.user import User
from app.schemas.admin import (
    AuditLogResponse,
    MetricsResponse,
    QueriesPerDay,
    TopQueriedDocument,
    UserListResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=list[UserListResponse],
    summary="List all users",
)
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserListResponse]:
    """List all registered users.

    Admin only. Returns user profiles with role and status information.
    """
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [UserListResponse.model_validate(u) for u in users]


@router.patch(
    "/users/{user_id}",
    response_model=UserListResponse,
    summary="Update user role or status",
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """Update a user's role or active status.

    Admin only. Admins cannot deactivate themselves.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deactivation
    if user_id == current_user.id and data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    # Prevent self-demotion from admin
    if user_id == current_user.id and data.role and data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin role",
        )

    if data.role is not None:
        user.role = data.role
        logger.info(
            "Admin %s changed user %s role to %s",
            current_user.email, user.email, data.role,
        )

    if data.is_active is not None:
        user.is_active = data.is_active
        logger.info(
            "Admin %s set user %s active=%s",
            current_user.email, user.email, data.is_active,
        )

    await db.commit()
    await db.refresh(user)

    return UserListResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Audit log viewer
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    response_model=list[AuditLogResponse],
    summary="View audit logs",
)
async def list_audit_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    """List audit log entries with optional filters.

    Admin only. Supports filtering by user ID and date range,
    with pagination.
    """
    query = select(AuditLog)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)

    query = (
        query
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    return [AuditLogResponse.model_validate(log) for log in logs]


# ---------------------------------------------------------------------------
# Metrics dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Get system metrics",
)
async def get_metrics(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    """Get system metrics for the admin dashboard.

    Admin only. Returns aggregate statistics for the last 30 days
    including query counts, latency, costs, and document stats.
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total queries in last 30 days
    total_queries_result = await db.execute(
        select(func.count(AuditLog.id))
        .where(AuditLog.created_at >= thirty_days_ago)
    )
    total_queries_30d = total_queries_result.scalar() or 0

    # Average latency
    avg_latency_result = await db.execute(
        select(func.avg(AuditLog.latency_ms))
        .where(AuditLog.created_at >= thirty_days_ago)
    )
    avg_latency_ms = float(avg_latency_result.scalar() or 0)

    # Total documents
    total_docs_result = await db.execute(select(func.count(Document.id)))
    total_documents = total_docs_result.scalar() or 0

    # Total chunks
    total_chunks_result = await db.execute(select(func.count(DocumentChunk.id)))
    total_chunks = total_chunks_result.scalar() or 0

    # Total cost in last 30 days
    cost_result = await db.execute(
        select(func.sum(AuditLog.estimated_cost_usd))
        .where(AuditLog.created_at >= thirty_days_ago)
    )
    cost_30d_usd = float(cost_result.scalar() or 0)

    # Queries per day (last 30 days)
    queries_per_day_result = await db.execute(
        select(
            cast(AuditLog.created_at, Date).label("date"),
            func.count(AuditLog.id).label("count"),
        )
        .where(AuditLog.created_at >= thirty_days_ago)
        .group_by(cast(AuditLog.created_at, Date))
        .order_by(cast(AuditLog.created_at, Date))
    )
    queries_per_day = [
        QueriesPerDay(date=str(row.date), count=row.count)
        for row in queries_per_day_result.fetchall()
    ]

    # Top queried documents (by frequency of retrieval in audit logs)
    # Use a simpler approach: count documents from the unnested array
    top_docs_result = await db.execute(
        select(
            Document.title,
            func.count(AuditLog.id).label("query_count"),
        )
        .select_from(AuditLog)
        .join(
            Document,
            Document.id == func.any_(AuditLog.retrieved_document_ids),
        )
        .where(AuditLog.created_at >= thirty_days_ago)
        .group_by(Document.title)
        .order_by(func.count(AuditLog.id).desc())
        .limit(5)
    )
    top_queried_documents = [
        TopQueriedDocument(title=row.title, query_count=row.query_count)
        for row in top_docs_result.fetchall()
    ]

    return MetricsResponse(
        total_queries_30d=total_queries_30d,
        avg_latency_ms=round(avg_latency_ms, 1),
        total_documents=total_documents,
        total_chunks=total_chunks,
        queries_per_day=queries_per_day,
        cost_30d_usd=round(cost_30d_usd, 4),
        top_queried_documents=top_queried_documents,
    )
