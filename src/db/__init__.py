"""Database layer with SQLAlchemy and async session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.lib.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_recycle=3600,  # Recycle connections after 1 hour to prevent stale connections
    pool_size=10,  # Default pool size
    max_overflow=20,  # Allow up to 30 total connections (10 + 20)
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_async_engine() -> AsyncEngine:
    """Get the async engine instance."""
    return engine


__all__ = ["Base", "SessionLocal", "get_db", "engine", "get_async_engine"]
