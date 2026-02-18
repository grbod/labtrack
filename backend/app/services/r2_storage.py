"""Cloudflare R2 storage implementation using boto3."""

import logging
from typing import BinaryIO, Union
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class R2StorageService(StorageService):
    """Cloudflare R2 storage implementation (S3-compatible)."""

    def __init__(self):
        """Initialize R2 client with credentials from settings."""
        self.bucket_name = settings.r2_bucket_name
        self.presigned_expiry = settings.presigned_url_expiry

        # Configure boto3 for R2
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
            region_name="auto",  # R2 uses 'auto' region
        )

    def upload(
        self,
        file: Union[BinaryIO, bytes],
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to R2."""
        try:
            # Convert bytes to file-like object if needed
            if isinstance(file, bytes):
                file = BytesIO(file)

            self.client.upload_fileobj(
                file,
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info(f"Uploaded file to R2: {key}")
            return key
        except ClientError as e:
            logger.error(f"Failed to upload to R2: {e}")
            raise

    def download(self, key: str) -> bytes:
        """Download a file from R2."""
        try:
            buffer = BytesIO()
            self.client.download_fileobj(self.bucket_name, key, buffer)
            buffer.seek(0)
            return buffer.read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"File not found in R2: {key}")
            logger.error(f"Failed to download from R2: {e}")
            raise

    def delete(self, key: str) -> bool:
        """Delete a file from R2."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted file from R2: {key}")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error(f"Failed to delete from R2: {e}")
            raise

    def get_presigned_url(self, key: str, expires_in: int = None) -> str:
        """Generate a presigned URL for temporary access."""
        if expires_in is None:
            expires_in = self.presigned_expiry

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def exists(self, key: str) -> bool:
        """Check if a file exists in R2."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def list_files(self, prefix: str = "") -> list[str]:
        """List files in R2 bucket with optional prefix."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )
            files = []
            for obj in response.get("Contents", []):
                files.append(obj["Key"])

            # Handle pagination
            while response.get("IsTruncated"):
                response = self.client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    ContinuationToken=response["NextContinuationToken"],
                )
                for obj in response.get("Contents", []):
                    files.append(obj["Key"])

            return files
        except ClientError as e:
            logger.error(f"Failed to list files from R2: {e}")
            raise
