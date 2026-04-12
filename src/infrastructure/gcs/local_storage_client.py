from __future__ import annotations

import os


class LocalStorageClient:
    def __init__(self, base_path: str):
        self.base_path = base_path

    def upload_bytes(
        self,
        bucket_name: str,
        blob_name: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        path = os.path.join(self.base_path, blob_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as f:
            f.write(payload)

        return f"file://{path}"

    def download_text(self, bucket_name: str, blob_name: str) -> str:
        path = os.path.join(self.base_path, blob_name)

        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def parse_gcs_uri(self, uri: str):
        # file://対応
        if uri.startswith("file://"):
            path = uri.replace("file://", "")
            return None, path

        raise ValueError("Unsupported URI for local mode")
