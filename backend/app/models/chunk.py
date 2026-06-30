"""DocumentChunk ORM model with pgvector embedding."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base
from app.config import settings


class DocumentChunk(Base):
    """Document chunk with vector embedding for similarity search.

    The access_level is denormalized from the parent Document for fast
    filtering during vector search queries (avoids JOIN on hot path).
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSIONS),
        nullable=True,
    )
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        Index("idx_chunks_document", "document_id"),
        Index("idx_chunks_access", "access_level"),
        {"comment": "Document chunks with vector embeddings for RAG retrieval"},
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, doc={self.document_id}, "
            f"index={self.chunk_index}, tokens={self.token_count})>"
        )
