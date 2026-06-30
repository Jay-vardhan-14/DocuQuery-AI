"""Pydantic schemas for RAG query requests and responses."""

from datetime import datetime
from uuid import UUID
from typing import List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Schema for submitting a question to the RAG pipeline."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language question",
    )


class SourceReference(BaseModel):
    """Schema for a source citation in the RAG response."""

    document_title: str
    chunk_preview: str = Field(..., description="First 100 chars of the chunk")
    similarity_score: float


class QueryMetadata(BaseModel):
    """Schema for query performance metadata."""

    latency_ms: int
    chunks_retrieved: int
    tokens_used: int


class QueryResponse(BaseModel):
    """Schema for the RAG pipeline response."""

    answer: str
    sources: List[SourceReference]
    metadata: QueryMetadata


class QueryHistoryItem(BaseModel):
    """Schema for a single query history entry."""

    id: UUID
    query_text: str
    response_summary: Optional[str]
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}
