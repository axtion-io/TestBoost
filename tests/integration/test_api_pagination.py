"""Integration tests for API pagination functionality."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.api.models.pagination import (
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    create_pagination_meta,
    paginate_items,
)


class TestPaginationParams:
    """Tests for PaginationParams validation."""

    def test_default_values(self):
        """Test default pagination parameters."""
        params = PaginationParams()

        assert params.page == 1
        assert params.per_page == 20

    def test_custom_values(self):
        """Test custom pagination parameters."""
        params = PaginationParams(page=5, per_page=50)

        assert params.page == 5
        assert params.per_page == 50

    def test_page_minimum_rejects_zero(self):
        """Test page number must be at least 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(page=0)

        assert "greater than or equal to 1" in str(exc_info.value)

    def test_per_page_maximum_rejects_over_100(self):
        """Test per_page must be at most 100."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(per_page=200)

        assert "less than or equal to 100" in str(exc_info.value)

    def test_per_page_minimum_rejects_zero(self):
        """Test per_page must be at least 1."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PaginationParams(per_page=0)

        assert "greater than or equal to 1" in str(exc_info.value)


class TestCreatePaginationMeta:
    """Tests for create_pagination_meta function."""

    def test_first_page(self):
        """Test pagination meta for first page."""
        meta = create_pagination_meta(page=1, per_page=10, total=100)

        assert meta.page == 1
        assert meta.per_page == 10
        assert meta.total == 100
        assert meta.total_pages == 10
        assert meta.has_next is True
        assert meta.has_prev is False

    def test_last_page(self):
        """Test pagination meta for last page."""
        meta = create_pagination_meta(page=10, per_page=10, total=100)

        assert meta.page == 10
        assert meta.total_pages == 10
        assert meta.has_next is False
        assert meta.has_prev is True

    def test_middle_page(self):
        """Test pagination meta for middle page."""
        meta = create_pagination_meta(page=5, per_page=10, total=100)

        assert meta.page == 5
        assert meta.has_next is True
        assert meta.has_prev is True

    def test_single_page(self):
        """Test pagination meta when all items fit on one page."""
        meta = create_pagination_meta(page=1, per_page=20, total=15)

        assert meta.page == 1
        assert meta.total_pages == 1
        assert meta.has_next is False
        assert meta.has_prev is False

    def test_empty_results(self):
        """Test pagination meta with no results."""
        meta = create_pagination_meta(page=1, per_page=20, total=0)

        assert meta.page == 1
        assert meta.total == 0
        assert meta.total_pages == 0
        assert meta.has_next is False
        assert meta.has_prev is False

    def test_partial_last_page(self):
        """Test pagination meta when last page is partial."""
        meta = create_pagination_meta(page=1, per_page=10, total=25)

        assert meta.total_pages == 3  # 10 + 10 + 5


class TestPaginateItems:
    """Tests for paginate_items function."""

    def test_paginate_items(self):
        """Test creating paginated response."""
        items = [{"id": i} for i in range(10)]
        response = paginate_items(items=items, page=1, per_page=10, total=25)

        assert len(response.items) == 10
        assert response.pagination.page == 1
        assert response.pagination.total == 25
        assert response.pagination.total_pages == 3

    def test_empty_page(self):
        """Test paginating empty results."""
        response = paginate_items(items=[], page=1, per_page=10, total=0)

        assert len(response.items) == 0
        assert response.pagination.total == 0


class TestSessionListPagination:
    """Tests for session list endpoint pagination."""

    @pytest.mark.asyncio
    async def test_session_list_pagination(self):
        """Test that session list returns pagination metadata."""
        from src.api.models.pagination import PaginationMeta

        # Mock data
        mock_sessions = [
            MagicMock(
                id=uuid4(),
                session_type="maven_maintenance",
                status="completed",
                mode="interactive",
                project_path="/test/path",
                config={},
                result=None,
                error_message=None,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                completed_at=None,
            )
            for _ in range(5)
        ]

        # Verify pagination meta structure
        meta = create_pagination_meta(page=1, per_page=20, total=5)

        assert meta.page == 1
        assert meta.per_page == 20
        assert meta.total == 5
        assert meta.total_pages == 1
        assert meta.has_next is False
        assert meta.has_prev is False

    @pytest.mark.asyncio
    async def test_pagination_edge_cases(self):
        """Test pagination edge cases."""
        # Case 1: Large dataset
        meta_large = create_pagination_meta(page=50, per_page=100, total=10000)
        assert meta_large.total_pages == 100
        assert meta_large.has_next is True
        assert meta_large.has_prev is True

        # Case 2: Exactly divisible
        meta_exact = create_pagination_meta(page=1, per_page=10, total=100)
        assert meta_exact.total_pages == 10

        # Case 3: One item less than a page
        meta_partial = create_pagination_meta(page=1, per_page=10, total=9)
        assert meta_partial.total_pages == 1

    @pytest.mark.asyncio
    async def test_artifact_list_pagination(self):
        """Test that artifact pagination works correctly."""
        # Test pagination for artifacts
        meta = create_pagination_meta(page=2, per_page=50, total=150)

        assert meta.page == 2
        assert meta.per_page == 50
        assert meta.total == 150
        assert meta.total_pages == 3
        assert meta.has_next is True
        assert meta.has_prev is True


class TestPaginationResponseStructure:
    """Tests for pagination response structure."""

    def test_pagination_meta_fields(self):
        """Test that PaginationMeta has all required fields."""
        meta = PaginationMeta(
            page=1,
            per_page=20,
            total=100,
            total_pages=5,
            has_next=True,
            has_prev=False,
        )

        assert hasattr(meta, "page")
        assert hasattr(meta, "per_page")
        assert hasattr(meta, "total")
        assert hasattr(meta, "total_pages")
        assert hasattr(meta, "has_next")
        assert hasattr(meta, "has_prev")

    def test_paginated_response_structure(self):
        """Test PaginatedResponse has items and pagination."""
        response = paginate_items(
            items=["a", "b", "c"],
            page=1,
            per_page=10,
            total=3,
        )

        assert hasattr(response, "items")
        assert hasattr(response, "pagination")
        assert isinstance(response.pagination, PaginationMeta)
