from __future__ import annotations

from src.config.settings import get_settings
from src.infrastructure.gcs.gcs_client import GCSClient
from src.infrastructure.gcs.local_storage_client import LocalStorageClient


def create_storage_client():
    """
    実行環境に応じて保存先クライアントを切り替える。
    local ではローカルディレクトリ、その他は GCS を利用する。
    """
    settings = get_settings()

    if settings.is_local:
        return LocalStorageClient(settings.local.storage_path)

    return GCSClient(project_id=settings.gcp.project_id)
