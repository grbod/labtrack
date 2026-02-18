"""Abstract storage service for file operations."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Union, TYPE_CHECKING
from pathlib import Path
from functools import lru_cache

if TYPE_CHECKING:
    from app.services.r2_storage import R2StorageService
    from app.services.local_storage import LocalStorageService


class StorageService(ABC):
    """Abstract base class for storage backends.

    All methods are synchronous since the underlying storage operations
    (boto3, filesystem) are blocking anyway.
    """

    @abstractmethod
    def upload(
        self,
        file: Union[BinaryIO, bytes],
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a file to storage.

        Args:
            file: File-like object or bytes to upload
            key: Storage key/path for the file
            content_type: MIME type of the file

        Returns:
            The storage key where the file was saved
        """
        pass

    @abstractmethod
    def download(self, key: str) -> bytes:
        """
        Download a file from storage.

        Args:
            key: Storage key/path of the file

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a file from storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if deleted, False if file didn't exist
        """
        pass

    @abstractmethod
    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Get a temporary URL for downloading a file.

        Args:
            key: Storage key/path of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for downloading the file
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            key: Storage key/path of the file

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in storage with optional prefix filter.

        Args:
            prefix: Optional prefix to filter files

        Returns:
            List of file keys matching the prefix
        """
        pass


# Storage service singleton
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """
    Get the configured storage service instance.

    Returns R2StorageService for production (STORAGE_BACKEND=r2)
    or LocalStorageService for development (STORAGE_BACKEND=local).

    The service is created once and reused for all requests.
    """
    global _storage_service

    if _storage_service is None:
        from app.config import settings

        if settings.storage_backend == "r2":
            from app.services.r2_storage import R2StorageService
            _storage_service = R2StorageService()
        else:
            from app.services.local_storage import LocalStorageService
            _storage_service = LocalStorageService()

    return _storage_service


def reset_storage_service() -> None:
    """Reset the storage service singleton. Useful for testing."""
    global _storage_service
    _storage_service = None
