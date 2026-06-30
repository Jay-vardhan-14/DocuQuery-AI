"""Document management API routes.

Handles document upload, listing, details, access level updates,
deletion, and processing status checks.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.document import (
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUpdate,
)
from app.services.document_service import (
    DocumentProcessingError,
    delete_document,
    get_document_by_id,
    get_document_status,
    list_documents,
    process_document,
    update_document_access_level,
    update_document_title,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF or DOCX file to upload"),
    title: str = Form(..., description="Document title"),
    access_level: str = Form(
        default="public",
        description="Access level: public, internal, confidential, restricted",
    ),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Upload a document for processing.

    Admin only. Accepts PDF or DOCX files up to 20MB.
    The document is processed asynchronously through the pipeline:
    parse → chunk → embed → store.
    """
    try:
        document = await process_document(
            file=file,
            title=title,
            access_level=access_level,
            user_id=current_user.id,
            db=db,
        )
    except DocumentProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List documents",
)
async def list_docs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List all documents accessible to the current user's role.

    Documents are filtered by access level based on the user's role:
    - admin: all documents
    - manager: public, internal, confidential
    - employee: public, internal
    """
    documents = await list_documents(
        user_role=current_user.role,
        db=db,
    )
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get details of a specific document.

    Returns 404 if the document doesn't exist or the user's role
    doesn't have access to its access level.
    """
    document = await get_document_by_id(
        document_id=document_id,
        user_role=current_user.role,
        db=db,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied",
        )

    return DocumentResponse.model_validate(document)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
)
async def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Update document metadata (title and/or access level).

    Admin only. When access_level is changed, all associated chunks
    are re-stamped with the new level to maintain RBAC consistency.
    """
    document = None

    # Update access level if provided
    if data.access_level is not None:
        try:
            document = await update_document_access_level(
                document_id=document_id,
                new_access_level=data.access_level,
                db=db,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    # Update title if provided
    if data.title is not None:
        document = await update_document_title(
            document_id=document_id,
            new_title=data.title,
            db=db,
        )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_doc(
    document_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document and all its associated chunks/embeddings.

    Admin only. Cascade delete removes all chunks automatically.
    """
    deleted = await delete_document(
        document_id=document_id,
        db=db,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Check document processing status",
)
async def check_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    """Check the processing status of a document.

    Returns the current status (pending/processing/completed/failed)
    and the total number of chunks processed.
    """
    status_data = await get_document_status(
        document_id=document_id,
        db=db,
    )

    if status_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentStatusResponse(**status_data)
