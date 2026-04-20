from __future__ import annotations

from google.cloud import storage


#
# Google Cloud Storage操作用クライアント
# - バケットへのアップロード・ダウンロードを簡易化
#
class GCSClient:
    def __init__(self, project_id: str):
        # プロジェクトIDを指定してGCSクライアントを初期化
        self.client = storage.Client(project=project_id)

    #
    # バケットにバイト列をアップロード
    # - content_type指定必須
    # - gs://パスを返す
    #
    def upload_bytes(self, bucket_name: str, blob_name: str, payload: bytes, content_type: str) -> str:
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(payload, content_type=content_type)
        return f"gs://{bucket_name}/{blob_name}"

    #
    # GCS URI（gs://...）からテキストをダウンロード
    # - UTF-8で返す
    #
    def download_text_from_gcs_uri(self, gcs_uri: str) -> str:
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid gcs uri: {gcs_uri}")

        rest = gcs_uri[len("gs://"):]
        bucket_name, blob_name = rest.split("/", 1)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.download_as_text(encoding="utf-8")
