"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.session import get_db
from app.models.document import Base


# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_gcs_client():
    """Create a mock GCS client."""
    mock = MagicMock()
    mock.bucket.return_value.blob.return_value.upload_from_file = MagicMock()
    mock.bucket.return_value.blob.return_value.download_as_bytes = MagicMock(
        return_value=b"test file content"
    )
    mock.bucket.return_value.blob.return_value.generate_signed_url = MagicMock(
        return_value="https://storage.googleapis.com/test-signed-url"
    )
    return mock


@pytest.fixture
def mock_document_ai_client():
    """Create a mock Document AI client."""
    mock = AsyncMock()
    mock.process_document.return_value = {
        "document_type": "financial_statement",
        "extracted_data": {
            "revenue": 1000000,
            "ebitda": 250000,
            "period_end_date": "2024-12-31",
        },
        "confidence": 0.92,
    }
    return mock


@pytest.fixture
def mock_claude_client():
    """Create a mock Claude API client."""
    mock = AsyncMock()
    mock.extract.return_value = {
        "document_type": "covenant_compliance",
        "extracted_data": {
            "leverage_ratio": 3.5,
            "interest_coverage": 2.1,
            "compliant": True,
        },
        "confidence": 0.88,
    }
    return mock


@pytest.fixture
def sample_document_data():
    """Sample document data for testing."""
    return {
        "original_filename": "test_financials_Q4_2024.pdf",
        "gcs_path": "inbox/test_financials_Q4_2024.pdf",
        "file_size_bytes": 1024000,
        "content_type": "application/pdf",
    }


@pytest.fixture
def sample_exception_data():
    """Sample exception data for testing."""
    return {
        "category": "validation_error",
        "reason": "Revenue value outside expected range",
        "field_name": "revenue",
        "expected_value": "> 0",
        "actual_value": "-50000",
        "priority": "high",
    }
