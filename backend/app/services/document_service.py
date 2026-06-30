"""Document processing service.

Orchestrates the full document pipeline:
  Upload → Parse → Chunk → Embed → Store

Also handles listing (with RBAC filtering), updating, and deletion.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.security.rbac import get_allowed_access_levels, VALID_ACCESS_LEVELS
from app.services.chunking_service import chunk_document
from app.services.embedding_service import generate_embeddings_batch
from app.utils.parsers import extract_text, detect_file_type, ParsingError

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Raised when document processing fails at any stage."""
    pass


async def process_document(
    file: UploadFile,
    title: str,
    access_level: str,
    user_id: UUID,
    db: AsyncSession,
) -> Document:
    """Process an uploaded document through the full pipeline.

    Pipeline stages:
        1. Validate file type (PDF/DOCX) and size (< 20MB)
        2. Create Document record with status="processing"
        3. Extract text using parsers
        4. Chunk the text into ~500-token segments
        5. Generate embeddings for all chunks (batch)
        6. Store chunks + embeddings with denormalized access_level
        7. Update Document status to "completed" with total_chunks count

    On any failure, the document status is set to "failed".

    Args:
        file: Uploaded file object.
        title: Document title.
        access_level: Access level (public/internal/confidential/restricted).
        user_id: UUID of the uploading admin.
        db: Async database session.

    Returns:
        The created Document object.

    Raises:
        DocumentProcessingError: If validation fails (file type, size).
    """
    # --- Stage 1: Validate ---
    filename = file.filename or "unknown"

    try:
        detect_file_type(filename)
    except ValueError as e:
        raise DocumentProcessingError(str(e))

    if access_level not in VALID_ACCESS_LEVELS:
        raise DocumentProcessingError(
            f"Invalid access level: '{access_level}'. "
            f"Must be one of: {', '.join(VALID_ACCESS_LEVELS)}"
        )

    # Read file content
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise DocumentProcessingError("Uploaded file is empty")

    if file_size > settings.max_file_size_bytes:
        raise DocumentProcessingError(
            f"File size ({file_size / (1024*1024):.1f} MB) exceeds "
            f"maximum allowed size ({settings.MAX_FILE_SIZE_MB} MB)"
        )

    # --- Stage 2: Create Document record ---
    document = Document(
        title=title,
        filename=filename,
        file_size_bytes=file_size,
        access_level=access_level,
        processing_status="processing",
        uploaded_by=user_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    logger.info(
        "Document record created: id=%s, title=%s, access=%s",
        document.id,
        title,
        access_level,
    )

    try:
        # --- Stage 3: Extract text ---
        logger.info("Extracting text from %s", filename)
        text = extract_text(file_bytes, filename)
        logger.info(
            "Text extracted: %d characters from %s", len(text), filename
        )

        # --- Stage 4: Chunk the text ---
        logger.info("Chunking document text")
        chunks = chunk_document(text)
        logger.info("Created %d chunks", len(chunks))

        # --- Stage 5: Generate embeddings ---
        logger.info("Generating embeddings for %d chunks", len(chunks))
        chunk_texts = [c["content"] for c in chunks]
        embeddings = await generate_embeddings_batch(chunk_texts)
        logger.info("Embeddings generated successfully")

        # --- Stage 6: Store chunks + embeddings ---
        logger.info("Storing chunks in database")
        chunk_records: List[DocumentChunk] = []

        for chunk_data, embedding in zip(chunks, embeddings):
            chunk_record = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                embedding=embedding,
                access_level=access_level,  # Denormalized from parent document
            )
            chunk_records.append(chunk_record)

        db.add_all(chunk_records)

        # --- Stage 7: Update document status ---
        document.processing_status = "completed"
        document.total_chunks = len(chunks)
        await db.commit()
        await db.refresh(document)

        logger.info(
            "Document processing completed: id=%s, chunks=%d",
            document.id,
            len(chunks),
        )

        return document

    except Exception as e:
        # On any failure, mark as failed
        logger.error(
            "Document processing failed for id=%s: %s",
            document.id,
            str(e),
        )
        document.processing_status = "failed"
        await db.commit()
        raise DocumentProcessingError(
            f"Document processing failed: {str(e)}"
        )


async def list_documents(
    user_role: str,
    db: AsyncSession,
) -> List[Document]:
    """List documents filtered by the user's role-based access.

    Args:
        user_role: User's role (admin/manager/employee).
        db: Async database session.

    Returns:
        List of Document objects the user can see.
    """
    allowed_levels = get_allowed_access_levels(user_role)

    result = await db.execute(
        select(Document)
        .where(Document.access_level.in_(allowed_levels))
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()

    logger.info(
        "Listed %d documents for role=%s (allowed levels: %s)",
        len(documents),
        user_role,
        allowed_levels,
    )

    return list(documents)


async def get_document_by_id(
    document_id: UUID,
    user_role: str,
    db: AsyncSession,
) -> Optional[Document]:
    """Get a document by ID if the user's role permits access.

    Args:
        document_id: Document UUID.
        user_role: User's role for access check.
        db: Async database session.

    Returns:
        Document object if found and accessible, None otherwise.
    """
    allowed_levels = get_allowed_access_levels(user_role)

    result = await db.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.access_level.in_(allowed_levels))
    )
    return result.scalar_one_or_none()


async def update_document_access_level(
    document_id: UUID,
    new_access_level: str,
    db: AsyncSession,
) -> Optional[Document]:
    """Update a document's access level and re-stamp all its chunks.

    This is critical for RBAC: when a document's access level changes,
    all denormalized access_level values on its chunks must be updated
    to stay in sync.

    Args:
        document_id: Document UUID.
        new_access_level: New access level to set.
        db: Async database session.

    Returns:
        Updated Document object, or None if not found.
    """
    if new_access_level not in VALID_ACCESS_LEVELS:
        raise ValueError(
            f"Invalid access level: '{new_access_level}'. "
            f"Must be one of: {', '.join(VALID_ACCESS_LEVELS)}"
        )

    # Get the document
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if document is None:
        return None

    old_level = document.access_level

    # Update document access level
    document.access_level = new_access_level

    # Re-stamp all chunks with the new access level (CRITICAL for RBAC)
    await db.execute(
        update(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .values(access_level=new_access_level)
    )

    await db.commit()
    await db.refresh(document)

    logger.info(
        "Document %s access level changed: %s → %s (chunks re-stamped)",
        document_id,
        old_level,
        new_access_level,
    )

    return document


async def update_document_title(
    document_id: UUID,
    new_title: str,
    db: AsyncSession,
) -> Optional[Document]:
    """Update a document's title.

    Args:
        document_id: Document UUID.
        new_title: New title to set.
        db: Async database session.

    Returns:
        Updated Document object, or None if not found.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if document is None:
        return None

    document.title = new_title
    await db.commit()
    await db.refresh(document)

    return document


async def delete_document(
    document_id: UUID,
    db: AsyncSession,
) -> bool:
    """Delete a document and all its associated chunks/embeddings.

    The CASCADE delete on the foreign key ensures all chunks are
    removed when the parent document is deleted.

    Args:
        document_id: Document UUID to delete.
        db: Async database session.

    Returns:
        True if the document was found and deleted, False if not found.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if document is None:
        return False

    await db.delete(document)
    await db.commit()

    logger.info(
        "Document deleted: id=%s, title=%s (chunks cascaded)",
        document_id,
        document.title,
    )

    return True


async def get_document_status(
    document_id: UUID,
    db: AsyncSession,
) -> Optional[dict]:
    """Get the processing status of a document.

    Args:
        document_id: Document UUID.
        db: Async database session.

    Returns:
        Dict with id, processing_status, and total_chunks, or None if not found.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if document is None:
        return None

    return {
        "id": document.id,
        "processing_status": document.processing_status,
        "total_chunks": document.total_chunks,
    }
