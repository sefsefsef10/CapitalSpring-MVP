"""Database session management."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Create async engine with appropriate settings for database type
def _create_engine():
    """Create database engine with appropriate settings."""
    is_sqlite = settings.database_url.startswith("sqlite")

    if is_sqlite:
        # SQLite doesn't support connection pooling the same way
        return create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL with connection pooling
        return create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
        )


engine = _create_engine()

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection and create tables if needed."""
    async with engine.begin() as conn:
        # Import all models to register them with Base
        from app.models import document, exception, audit  # noqa: F401

        # Create tables (in development only, use migrations in production)
        if settings.environment == "development":
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
