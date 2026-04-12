from src.config.settings import get_settings
from src.infrastructure.gcs.gcs_client import GCSClient
from src.infrastructure.gcs.local_storage_client import LocalStorageClient



#
# ストレージクライアントのファクトリ関数
# - 環境設定に応じてGCS/ローカルを切り替え
#
def create_storage_client():
    settings = get_settings()
    if settings.env == "local":
        return LocalStorageClient("./local_storage")
    return GCSClient(project_id=settings.gcp.project_id)
