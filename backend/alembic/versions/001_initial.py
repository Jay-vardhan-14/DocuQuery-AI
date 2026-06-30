"""Initial schema: users, documents, chunks, audit_logs + pgvector + seed admin.

Revision ID: 001_initial
Revises: None
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Password hashing for seed data
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="employee"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('admin', 'manager', 'employee')", name="ck_users_role"),
        comment="User accounts with RBAC roles",
    )
    op.create_index("idx_users_email", "users", ["email"])

    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False, server_default="public"),
        sa.Column("total_chunks", sa.Integer, server_default="0"),
        sa.Column("processing_status", sa.String(20), server_default="pending"),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "access_level IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_documents_access_level",
        ),
        sa.CheckConstraint(
            "processing_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_documents_processing_status",
        ),
        comment="Uploaded documents with access level control",
    )
    op.create_index("idx_documents_access", "documents", ["access_level"])
    op.create_index("idx_documents_uploaded_by", "documents", ["uploaded_by"])

    # Create document_chunks table (embedding column added via raw SQL for pgvector type)
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        comment="Document chunks with vector embeddings for RAG retrieval",
    )

    # Add the vector embedding column via raw SQL (pgvector type not natively supported in SA Column)
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(3072)")

    op.create_index("idx_chunks_document", "document_chunks", ["document_id"])
    op.create_index("idx_chunks_access", "document_chunks", ["access_level"])

    # No vector index created because gemini-embedding-2 uses 3072 dimensions, 
    # which exceeds pgvector's default 2000 dimension limit for ivfflat/hnsw indexes.
    # Exact nearest neighbor (full scan) will be used instead.

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("retrieved_chunk_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("retrieved_document_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("response_summary", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("total_tokens_used", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        comment="Audit trail for all RAG queries",
    )
    op.create_index("idx_audit_user", "audit_logs", ["user_id"])
    op.create_index("idx_audit_created", "audit_logs", ["created_at"])

    # Seed default admin user (password: password123)
    admin_password_hash = pwd_context.hash("password123")
    op.execute(
        sa.text(
            "INSERT INTO users (email, password_hash, full_name, role) "
            "VALUES (:email, :password_hash, :full_name, :role) "
            "ON CONFLICT (email) DO NOTHING"
        ).bindparams(
            email="admin@docuquery.ai",
            password_hash=admin_password_hash,
            full_name="System Admin",
            role="admin",
        )
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
