from __future__ import annotations

from google.cloud import storage


class GCSClient:
    def __init__(self, project_id: str):
        self.client = storage.Client(project=project_id)

    def upload_bytes(self, bucket_name: str, blob_name: str, payload: bytes, content_type: str) -> str:
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(payload, content_type=content_type)
        return f"gs://{bucket_name}/{blob_name}"

    def download_text_from_gcs_uri(self, gcs_uri: str) -> str:
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid gcs uri: {gcs_uri}")

        rest = gcs_uri[len("gs://"):]
        bucket_name, blob_name = rest.split("/", 1)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_text(encoding="utf-8")
