"""Pagination models and utilities for API responses."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

    @field_validator("page")
    @classmethod
    def validate_page(cls, v: int) -> int:
        """Ensure page is at least 1."""
        return max(1, v)

    @field_validator("per_page")
    @classmethod
    def validate_per_page(cls, v: int) -> int:
        """Ensure per_page is between 1 and 100."""
        return min(max(1, v), 100)


class PaginationMeta(BaseModel):
    """Pagination metadata for responses."""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""

    items: list[T] = Field(..., description="List of items for current page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


def create_pagination_meta(
    page: int,
    per_page: int,
    total: int,
) -> PaginationMeta:
    """
    Create pagination metadata from query parameters and total count.

    Args:
        page: Current page number (1-indexed)
        per_page: Items per page
        total: Total number of items

    Returns:
        PaginationMeta with calculated values
    """
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def paginate_items(
    items: list[T],
    page: int,
    per_page: int,
    total: int,
) -> PaginatedResponse[T]:
    """
    Create a paginated response from items and pagination parameters.

    Args:
        items: List of items for the current page
        page: Current page number
        per_page: Items per page
        total: Total number of items

    Returns:
        PaginatedResponse with items and metadata
    """
    return PaginatedResponse(
        items=items,
        pagination=create_pagination_meta(page, per_page, total),
    )


__all__ = [
    "PaginationParams",
    "PaginationMeta",
    "PaginatedResponse",
    "create_pagination_meta",
    "paginate_items",
]
