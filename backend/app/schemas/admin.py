"""Pydantic schemas for admin operations."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional
from decimal import Decimal

from pydantic import BaseModel, Field


class UserUpdate(BaseModel):
    """Schema for updating a user (admin operation)."""

    role: Optional[str] = Field(
        None,
        pattern="^(admin|manager|employee)$",
        description="User role",
    )
    is_active: Optional[bool] = Field(None, description="Active status")


class UserListResponse(BaseModel):
    """Schema for user in admin user list."""

    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    """Schema for audit log entry response."""

    id: UUID
    user_id: UUID
    query_text: str
    retrieved_document_ids: List[UUID]
    response_summary: Optional[str]
    latency_ms: int
    total_tokens_used: Optional[int]
    estimated_cost_usd: Optional[Decimal]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogFilters(BaseModel):
    """Schema for audit log query filters."""

    user_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class QueriesPerDay(BaseModel):
    """Schema for daily query count."""

    date: str
    count: int


class TopQueriedDocument(BaseModel):
    """Schema for top queried document."""

    title: str
    query_count: int


class MetricsResponse(BaseModel):
    """Schema for admin metrics dashboard data."""

    total_queries_30d: int
    avg_latency_ms: float
    total_documents: int
    total_chunks: int
    queries_per_day: List[QueriesPerDay]
    cost_30d_usd: float
    top_queried_documents: List[TopQueriedDocument]
