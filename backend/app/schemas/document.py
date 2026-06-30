"""Pydantic schemas for document operations."""

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


class DocumentUpload(BaseModel):
    """Schema for document upload metadata."""

    title: str = Field(..., min_length=1, max_length=255, description="Document title")
    access_level: str = Field(
        default="public",
        description="Access level: public, internal, confidential, restricted",
        pattern="^(public|internal|confidential|restricted)$",
    )


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    access_level: Optional[str] = Field(
        None,
        pattern="^(public|internal|confidential|restricted)$",
    )


class DocumentResponse(BaseModel):
    """Schema for document details response."""

    id: UUID
    title: str
    filename: str
    file_size_bytes: int
    access_level: str
    total_chunks: int
    processing_status: str
    uploaded_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """Schema for document processing status."""

    id: UUID
    processing_status: str
    total_chunks: int

    model_config = {"from_attributes": True}
