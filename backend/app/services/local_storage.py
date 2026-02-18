"""Local filesystem storage implementation for development."""

import logging
from pathlib import Path
from typing import BinaryIO, Union
from urllib.parse import quote

from app.config import settings
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class LocalStorageService(StorageService):
    """Local filesystem storage implementation."""

    def __init__(self, base_path: Path = None):
        """
        Initialize local storage.

        Args:
            base_path: Base directory for file storage. Defaults to settings.upload_path
        """
        self.base_path = base_path or settings.upload_path
        self.base_path = Path(self.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, key: str) -> Path:
        """Get the full filesystem path for a storage key."""
        # Ensure key doesn't escape base path
        safe_key = key.lstrip("/").lstrip("\\")
        full_path = self.base_path / safe_key
        # Resolve to catch any path traversal attempts
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Invalid storage key: {key}")
        return full_path

    def upload(
        self,
        file: Union[BinaryIO, bytes],
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to local storage."""
        full_path = self._get_full_path(key)

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Get file content
        if isinstance(file, bytes):
            content = file
        else:
            content = file.read()

        # Write to disk
        full_path.write_bytes(content)
        logger.info(f"Saved file locally: {key}")
        return key

    def download(self, key: str) -> bytes:
        """Download a file from local storage."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        return full_path.read_bytes()

    def delete(self, key: str) -> bool:
        """Delete a file from local storage."""
        full_path = self._get_full_path(key)

        if not full_path.exists():
            return False

        full_path.unlink()
        logger.info(f"Deleted local file: {key}")

        # Clean up empty parent directories
        try:
            parent = full_path.parent
            while parent != self.base_path and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass  # Directory not empty or other issue

        return True

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Get a URL for the file.

        For local storage, this returns a relative path that the application
        can serve. In development, this would be handled by the FastAPI
        static files or a dedicated endpoint.
        """
        # Return a URL path that the API can serve
        # The frontend/API will need to handle serving these files
        encoded_key = quote(key, safe="/")
        return f"/api/v1/files/{encoded_key}"

    def exists(self, key: str) -> bool:
        """Check if a file exists in local storage."""
        full_path = self._get_full_path(key)
        return full_path.exists()

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in local storage with optional prefix."""
        files = []
        search_path = self._get_full_path(prefix) if prefix else self.base_path

        if not search_path.exists():
            return files

        if search_path.is_file():
            # Prefix is a specific file
            return [prefix]

        for path in search_path.rglob("*"):
            if path.is_file():
                # Get relative path from base
                rel_path = path.relative_to(self.base_path)
                files.append(str(rel_path))

        return sorted(files)
