"""SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):  # type: ignore[misc]
    """SQLAlchemy declarative base for all models."""

    pass
