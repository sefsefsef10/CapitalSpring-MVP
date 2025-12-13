"""Tests for documents API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus, DocumentType


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient):
    """Test listing documents when none exist."""
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_documents_with_data(
    client: AsyncClient, db_session: AsyncSession, sample_document_data: dict
):
    """Test listing documents with existing data."""
    # Create a test document
    doc = Document(
        original_filename=sample_document_data["original_filename"],
        gcs_path=sample_document_data["gcs_path"],
        file_size_bytes=sample_document_data["file_size_bytes"],
        content_type=sample_document_data["content_type"],
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["original_filename"] == sample_document_data["original_filename"]


@pytest.mark.asyncio
async def test_list_documents_with_status_filter(
    client: AsyncClient, db_session: AsyncSession
):
    """Test filtering documents by status."""
    # Create documents with different statuses
    pending_doc = Document(
        original_filename="pending.pdf",
        gcs_path="inbox/pending.pdf",
        status=DocumentStatus.PENDING,
    )
    processed_doc = Document(
        original_filename="processed.pdf",
        gcs_path="complete/processed.pdf",
        status=DocumentStatus.PROCESSED,
    )
    db_session.add_all([pending_doc, processed_doc])
    await db_session.commit()

    # Filter by pending status
    response = await client.get("/api/v1/documents", params={"status": "pending"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "pending"

    # Filter by processed status
    response = await client.get("/api/v1/documents", params={"status": "processed"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "processed"


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient):
    """Test getting a document that doesn't exist."""
    response = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_document_detail(
    client: AsyncClient, db_session: AsyncSession, sample_document_data: dict
):
    """Test getting document details."""
    doc = Document(
        original_filename=sample_document_data["original_filename"],
        gcs_path=sample_document_data["gcs_path"],
        file_size_bytes=sample_document_data["file_size_bytes"],
        status=DocumentStatus.PROCESSED,
        doc_type=DocumentType.FINANCIAL_STATEMENT,
        confidence=0.95,
        extracted_data={"revenue": 1000000, "ebitda": 250000},
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.get(f"/api/v1/documents/{doc.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(doc.id)
    assert data["original_filename"] == sample_document_data["original_filename"]
    assert data["status"] == "processed"
    assert data["confidence"] == 0.95
    assert data["extracted_data"]["revenue"] == 1000000


@pytest.mark.asyncio
async def test_update_document(
    client: AsyncClient, db_session: AsyncSession, sample_document_data: dict
):
    """Test updating document extracted data."""
    doc = Document(
        original_filename=sample_document_data["original_filename"],
        gcs_path=sample_document_data["gcs_path"],
        status=DocumentStatus.NEEDS_REVIEW,
        extracted_data={"revenue": 1000000},
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    # Update extracted data
    response = await client.patch(
        f"/api/v1/documents/{doc.id}",
        json={"extracted_data": {"revenue": 1200000, "ebitda": 300000}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["extracted_data"]["revenue"] == 1200000
    assert data["extracted_data"]["ebitda"] == 300000


@pytest.mark.asyncio
async def test_delete_document(
    client: AsyncClient, db_session: AsyncSession, sample_document_data: dict
):
    """Test deleting a document."""
    doc = Document(
        original_filename=sample_document_data["original_filename"],
        gcs_path=sample_document_data["gcs_path"],
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    response = await client.delete(f"/api/v1/documents/{doc.id}")
    assert response.status_code == 204

    # Verify document is deleted
    response = await client.get(f"/api/v1/documents/{doc.id}")
    assert response.status_code == 404
