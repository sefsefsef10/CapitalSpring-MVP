"""Storage service for file operations (GCS or local filesystem)."""

import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog
from fastapi import UploadFile

from app.config import settings

logger = structlog.get_logger(__name__)

# Try to import GCS, use local storage if not available
try:
    from google.cloud import storage
    from google.cloud.exceptions import NotFound
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    logger.warning("Google Cloud Storage not available, using local filesystem")


class StorageService:
    """Service for file storage operations (GCS or local filesystem)."""

    def __init__(self):
        """Initialize the storage client."""
        # Use GCS if: flag is set AND library is available AND credentials exist
        use_gcs = (
            settings.use_gcp
            and GCS_AVAILABLE
            and (settings.google_application_credentials or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
        )
        self.use_local = not use_gcs

        if self.use_local:
            # Use local filesystem storage
            self.local_storage_path = Path("./local_storage")
            self.local_storage_path.mkdir(parents=True, exist_ok=True)
            # Create subdirectories
            for prefix in ["inbox", "processing", "complete", "failed", "archive"]:
                (self.local_storage_path / prefix).mkdir(exist_ok=True)
            logger.info("Using local filesystem storage", path=str(self.local_storage_path))
            self.client = None
            self.bucket = None
        else:
            # Load credentials from file if specified
            creds_path = settings.google_application_credentials
            if creds_path and os.path.exists(creds_path):
                self.client = storage.Client.from_service_account_json(
                    creds_path,
                    project=settings.gcp_project_id
                )
                logger.info("Using GCS with service account", path=creds_path)
            else:
                self.client = storage.Client(project=settings.gcp_project_id)
                logger.info("Using GCS with default credentials")
            self.bucket = self.client.bucket(settings.gcs_bucket_name)
            self.local_storage_path = None

    async def upload_file(
        self,
        file: UploadFile,
        destination_prefix: Optional[str] = None,
        custom_filename: Optional[str] = None,
    ) -> str:
        """Upload a file to storage."""
        prefix = (destination_prefix or settings.gcs_inbox_prefix).strip("/")

        # Generate unique filename if not provided
        if custom_filename:
            filename = custom_filename
        else:
            file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
            unique_id = str(uuid.uuid4())[:8]
            original_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
            filename = f"{original_name}_{unique_id}.{file_extension}"

        content = await file.read()

        if self.use_local:
            file_path = self.local_storage_path / prefix / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)
            storage_path = f"local://{prefix}/{filename}"
            logger.info("File uploaded to local storage", path=storage_path, size=len(content))
        else:
            blob_path = f"{prefix}/{filename}"
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(content, content_type=file.content_type or "application/octet-stream")
            storage_path = f"gs://{settings.gcs_bucket_name}/{blob_path}"
            logger.info("File uploaded to GCS", path=storage_path, size=len(content))

        return storage_path

    async def download_file(self, storage_path: str) -> bytes:
        """Download a file from storage."""
        if self.use_local or storage_path.startswith("local://"):
            local_path = self._extract_local_path(storage_path)
            file_path = self.local_storage_path / local_path
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {storage_path}")
            content = file_path.read_bytes()
            logger.info("File downloaded from local storage", path=storage_path, size=len(content))
            return content
        else:
            blob_path = self._extract_blob_path(storage_path)
            blob = self.bucket.blob(blob_path)
            try:
                content = blob.download_as_bytes()
                logger.info("File downloaded from GCS", path=storage_path, size=len(content))
                return content
            except NotFound:
                raise FileNotFoundError(f"File not found: {storage_path}")

    async def move_file(self, source_path: str, destination_prefix: str) -> str:
        """Move a file to a different prefix (folder)."""
        destination_prefix = destination_prefix.strip("/")

        if self.use_local or source_path.startswith("local://"):
            local_path = self._extract_local_path(source_path)
            source_file = self.local_storage_path / local_path
            filename = source_file.name
            dest_file = self.local_storage_path / destination_prefix / filename
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if source_file.exists():
                shutil.move(str(source_file), str(dest_file))

            new_path = f"local://{destination_prefix}/{filename}"
            logger.info("File moved", from_path=source_path, to_path=new_path)
            return new_path
        else:
            source_blob_path = self._extract_blob_path(source_path)
            source_blob = self.bucket.blob(source_blob_path)
            filename = source_blob_path.split("/")[-1]
            destination_path = f"{destination_prefix}/{filename}"

            self.bucket.copy_blob(source_blob, self.bucket, destination_path)
            source_blob.delete()

            new_path = f"gs://{settings.gcs_bucket_name}/{destination_path}"
            logger.info("File moved", from_path=source_path, to_path=new_path)
            return new_path

    async def delete_file(self, storage_path: str) -> None:
        """Delete a file from storage."""
        if self.use_local or storage_path.startswith("local://"):
            local_path = self._extract_local_path(storage_path)
            file_path = self.local_storage_path / local_path
            if file_path.exists():
                file_path.unlink()
                logger.info("File deleted from local storage", path=storage_path)
        else:
            blob_path = self._extract_blob_path(storage_path)
            blob = self.bucket.blob(blob_path)
            try:
                blob.delete()
                logger.info("File deleted from GCS", path=storage_path)
            except NotFound:
                logger.warning("File not found for deletion", path=storage_path)

    async def get_signed_url(self, storage_path: str, expiration_hours: int = 24, method: str = "GET") -> str:
        """Generate a signed URL for temporary access."""
        if self.use_local or storage_path.startswith("local://"):
            # For local storage, return a placeholder URL
            return f"http://localhost:8000/api/v1/documents/download/{storage_path}"
        else:
            blob_path = self._extract_blob_path(storage_path)
            blob = self.bucket.blob(blob_path)
            return blob.generate_signed_url(version="v4", expiration=timedelta(hours=expiration_hours), method=method)

    async def file_exists(self, storage_path: str) -> bool:
        """Check if a file exists."""
        if self.use_local or storage_path.startswith("local://"):
            local_path = self._extract_local_path(storage_path)
            return (self.local_storage_path / local_path).exists()
        else:
            blob_path = self._extract_blob_path(storage_path)
            return self.bucket.blob(blob_path).exists()

    async def get_file_metadata(self, storage_path: str) -> dict:
        """Get metadata for a file."""
        if self.use_local or storage_path.startswith("local://"):
            local_path = self._extract_local_path(storage_path)
            file_path = self.local_storage_path / local_path
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "size": stat.st_size,
                "content_type": "application/octet-stream",
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "updated": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        else:
            blob_path = self._extract_blob_path(storage_path)
            blob = self.bucket.blob(blob_path)
            blob.reload()
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
            }

    async def list_files(self, prefix: str, max_results: int = 100) -> list[dict]:
        """List files in a prefix."""
        prefix = prefix.strip("/")

        if self.use_local:
            files = []
            folder = self.local_storage_path / prefix
            if folder.exists():
                for file_path in list(folder.iterdir())[:max_results]:
                    if file_path.is_file():
                        stat = file_path.stat()
                        files.append({
                            "name": file_path.name,
                            "size": stat.st_size,
                            "content_type": "application/octet-stream",
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "storage_path": f"local://{prefix}/{file_path.name}",
                        })
            return files
        else:
            blobs = self.bucket.list_blobs(prefix=prefix, max_results=max_results)
            return [{
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "storage_path": f"gs://{settings.gcs_bucket_name}/{blob.name}",
            } for blob in blobs]

    def _extract_blob_path(self, gcs_path: str) -> str:
        """Extract blob path from GCS URI."""
        if gcs_path.startswith("gs://"):
            parts = gcs_path[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        return gcs_path

    def _extract_local_path(self, local_path: str) -> str:
        """Extract local path from local:// URI."""
        if local_path.startswith("local://"):
            return local_path[8:]
        return local_path
