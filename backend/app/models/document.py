"""Document ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Document(Base):
    """Uploaded document metadata.

    Access levels:
        - public: visible to all authenticated users
        - internal: visible to employees, managers, and admins
        - confidential: visible to managers and admins only
        - restricted: visible to admins only
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="public",
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_documents_access", "access_level"),
        Index("idx_documents_uploaded_by", "uploaded_by"),
        {"comment": "Uploaded documents with access level control"},
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, title={self.title}, "
            f"access={self.access_level}, status={self.processing_status})>"
        )
