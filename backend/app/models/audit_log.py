"""AuditLog ORM model for query audit trail."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Audit log entry for every RAG query.

    Tracks: who queried, what they asked, which documents were retrieved,
    the response summary, latency, token usage, and estimated cost.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    retrieved_chunk_ids = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    retrieved_document_ids = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
    )
    response_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_created", "created_at"),
        {"comment": "Audit trail for all RAG queries"},
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user={self.user_id}, "
            f"latency={self.latency_ms}ms)>"
        )
