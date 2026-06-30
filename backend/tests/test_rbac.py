"""Tests for RBAC enforcement.

Two layers of testing:

1. **Unit tests** — verify get_allowed_access_levels() and can_access_level()
   produce the correct mappings.

2. **Integration tests** — insert real Document + DocumentChunk rows at all 4
   access levels with mock embeddings, then call retrieve_relevant_chunks()
   as each role and verify only the correct chunks are returned.
   This proves the SQL-level WHERE clause enforces RBAC end-to-end.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.user import User
from app.security.rbac import (
    ROLE_ACCESS_MAP,
    VALID_ROLES,
    can_access_level,
    get_allowed_access_levels,
)
from app.services.rag_service import retrieve_relevant_chunks


# ==========================================================================
# Unit tests for RBAC mapping functions
# ==========================================================================


class TestGetAllowedAccessLevels:
    """Unit tests for get_allowed_access_levels()."""

    def test_admin_sees_all_levels(self):
        levels = get_allowed_access_levels("admin")
        assert set(levels) == {"public", "internal", "confidential", "restricted"}

    def test_manager_sees_public_internal_confidential(self):
        levels = get_allowed_access_levels("manager")
        assert set(levels) == {"public", "internal", "confidential"}

    def test_employee_sees_public_and_internal(self):
        levels = get_allowed_access_levels("employee")
        assert set(levels) == {"public", "internal"}

    def test_unknown_role_raises_error(self):
        with pytest.raises(ValueError, match="Unknown role"):
            get_allowed_access_levels("intern")

    def test_empty_role_raises_error(self):
        with pytest.raises(ValueError, match="Unknown role"):
            get_allowed_access_levels("")


class TestCanAccessLevel:
    """Unit tests for can_access_level()."""

    def test_admin_can_access_restricted(self):
        assert can_access_level("admin", "restricted") is True

    def test_manager_cannot_access_restricted(self):
        assert can_access_level("manager", "restricted") is False

    def test_employee_cannot_access_confidential(self):
        assert can_access_level("employee", "confidential") is False

    def test_employee_can_access_public(self):
        assert can_access_level("employee", "public") is True

    def test_employee_can_access_internal(self):
        assert can_access_level("employee", "internal") is True

    def test_manager_can_access_confidential(self):
        assert can_access_level("manager", "confidential") is True


class TestRoleAccessMapCompleteness:
    """Verify the role-access mapping covers all roles."""

    def test_all_valid_roles_have_mappings(self):
        for role in VALID_ROLES:
            assert role in ROLE_ACCESS_MAP

    def test_role_access_levels_are_subsets(self):
        """Employee ⊂ Manager ⊂ Admin in terms of access."""
        employee = set(ROLE_ACCESS_MAP["employee"])
        manager = set(ROLE_ACCESS_MAP["manager"])
        admin = set(ROLE_ACCESS_MAP["admin"])

        assert employee.issubset(manager)
        assert manager.issubset(admin)


# ==========================================================================
# Integration tests: real document_chunks + retrieve_relevant_chunks()
# ==========================================================================


MOCK_EMBEDDING = [0.1] * 3072

# Access levels with test document titles
ACCESS_LEVELS = [
    ("public", "Public Company Overview"),
    ("internal", "Internal Engineering Wiki"),
    ("confidential", "Confidential Strategy Memo"),
    ("restricted", "Restricted Board Minutes"),
]


@pytest_asyncio.fixture
async def seeded_chunks(db_session: AsyncSession, admin_user: User):
    """Insert one Document + one DocumentChunk at each access level.

    All chunks share the same mock embedding so that cosine similarity
    is identical — the only differentiator is the RBAC filter.

    Returns a dict mapping access_level → chunk_id for assertions.
    """
    access_to_chunk_id = {}

    for access_level, title in ACCESS_LEVELS:
        # Create the parent document
        doc = Document(
            title=title,
            filename=f"{access_level}_doc.pdf",
            file_size_bytes=1024,
            access_level=access_level,
            processing_status="completed",
            total_chunks=1,
            uploaded_by=admin_user.id,
        )
        db_session.add(doc)
        await db_session.flush()

        # Create a chunk with a mock embedding
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content=f"This is the {access_level} document content about {title}.",
            token_count=15,
            embedding=MOCK_EMBEDDING,
            access_level=access_level,
        )
        db_session.add(chunk)
        await db_session.flush()

        access_to_chunk_id[access_level] = chunk.id

    await db_session.commit()
    return access_to_chunk_id


class TestRBACVectorSearchIntegration:
    """Integration tests that verify RBAC filtering in retrieve_relevant_chunks().

    These tests insert real rows into document_chunks at all 4 access levels,
    then mock only the embedding API call (no real OpenAI needed), and verify
    that the SQL WHERE clause correctly filters by the user's role.
    """

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_employee_sees_only_public_and_internal(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Employee role should retrieve only public + internal chunks."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me about the company",
            user_role="employee",
            db=db_session,
            top_k=10,
        )

        returned_levels = {c["access_level"] for c in chunks}
        assert returned_levels <= {"public", "internal"}, (
            f"Employee saw levels {returned_levels}, expected only public/internal"
        )
        # Should NOT contain any confidential or restricted chunks
        assert "confidential" not in returned_levels
        assert "restricted" not in returned_levels

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_manager_sees_public_internal_confidential(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Manager role should retrieve public + internal + confidential."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me about the strategy",
            user_role="manager",
            db=db_session,
            top_k=10,
        )

        returned_levels = {c["access_level"] for c in chunks}
        assert returned_levels <= {"public", "internal", "confidential"}, (
            f"Manager saw levels {returned_levels}"
        )
        assert "restricted" not in returned_levels

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_admin_sees_all_levels(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Admin role should retrieve chunks at all 4 access levels."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me everything",
            user_role="admin",
            db=db_session,
            top_k=10,
        )

        returned_levels = {c["access_level"] for c in chunks}
        assert returned_levels == {"public", "internal", "confidential", "restricted"}, (
            f"Admin saw levels {returned_levels}, expected all 4"
        )

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_employee_cannot_see_confidential(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Explicitly verify employee cannot see confidential chunks."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me the strategy",
            user_role="employee",
            db=db_session,
            top_k=10,
        )

        chunk_ids = {c["chunk_id"] for c in chunks}
        confidential_id = seeded_chunks["confidential"]
        assert confidential_id not in chunk_ids, (
            "Employee should NOT see confidential chunk"
        )

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_employee_cannot_see_restricted(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Explicitly verify employee cannot see restricted chunks."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me the board minutes",
            user_role="employee",
            db=db_session,
            top_k=10,
        )

        chunk_ids = {c["chunk_id"] for c in chunks}
        restricted_id = seeded_chunks["restricted"]
        assert restricted_id not in chunk_ids, (
            "Employee should NOT see restricted chunk"
        )

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_manager_cannot_see_restricted(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Explicitly verify manager cannot see restricted chunks."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Tell me the board decisions",
            user_role="manager",
            db=db_session,
            top_k=10,
        )

        chunk_ids = {c["chunk_id"] for c in chunks}
        restricted_id = seeded_chunks["restricted"]
        assert restricted_id not in chunk_ids, (
            "Manager should NOT see restricted chunk"
        )

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_admin_can_see_restricted(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Admin should be able to see restricted chunks."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Board meeting notes",
            user_role="admin",
            db=db_session,
            top_k=10,
        )

        chunk_ids = {c["chunk_id"] for c in chunks}
        restricted_id = seeded_chunks["restricted"]
        assert restricted_id in chunk_ids, (
            "Admin SHOULD see restricted chunk"
        )

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_retrieved_chunks_have_correct_structure(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Verify the returned chunk dicts have all expected fields."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Overview",
            user_role="admin",
            db=db_session,
            top_k=10,
        )

        assert len(chunks) > 0, "Should retrieve at least one chunk"

        first = chunks[0]
        assert "chunk_id" in first
        assert "document_id" in first
        assert "document_title" in first
        assert "content" in first
        assert "chunk_index" in first
        assert "access_level" in first
        assert "similarity_score" in first
        assert isinstance(first["similarity_score"], float)

    @pytest.mark.asyncio
    @patch("app.services.rag_service.generate_embedding", new_callable=AsyncMock)
    async def test_top_k_limits_results(
        self, mock_embed, db_session, seeded_chunks
    ):
        """Verify that top_k parameter limits the number of results."""
        mock_embed.return_value = MOCK_EMBEDDING

        chunks = await retrieve_relevant_chunks(
            query_text="Documents",
            user_role="admin",
            db=db_session,
            top_k=2,
        )

        assert len(chunks) <= 2, (
            f"Should return at most 2 chunks, got {len(chunks)}"
        )
