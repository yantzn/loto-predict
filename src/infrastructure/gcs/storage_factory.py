from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.config.settings import AppSettings, get_settings


class StorageClientProtocol(Protocol):
    def upload_bytes(
        self,
        bucket_name: str,
        blob_name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        ...

    def download_text(self, bucket_name: str, blob_name: str, encoding: str = "utf-8") -> str:
        ...


class LocalStorageClient:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)

    def upload_bytes(
        self,
        bucket_name: str,
        blob_name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        del bucket_name, content_type
        path = self.base_path / blob_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return f"file://{path.resolve()}"

    def download_text(self, bucket_name: str, blob_name: str, encoding: str = "utf-8") -> str:
        del bucket_name
        path = self.base_path / blob_name
        return path.read_text(encoding=encoding)


class GCSStorageClient:
    def __init__(self, project_id: str):
        from google.cloud import storage

        self.client = storage.Client(project=project_id or None)

    def upload_bytes(
        self,
        bucket_name: str,
        blob_name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(payload, content_type=content_type)
        return f"gs://{bucket_name}/{blob_name}"

    def download_text(self, bucket_name: str, blob_name: str, encoding: str = "utf-8") -> str:
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_text(encoding=encoding)


def create_storage_client(settings: AppSettings | None = None) -> StorageClientProtocol:
    app_settings = settings or get_settings()
    if app_settings.is_local:
        return LocalStorageClient(app_settings.local_storage_path)
    return GCSStorageClient(project_id=app_settings.gcp.project_id)
