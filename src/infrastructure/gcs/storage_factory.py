from src.config.settings import settings
from src.infrastructure.gcs.gcs_client import GCSClient
from src.infrastructure.gcs.local_storage_client import LocalStorageClient


def create_storage_client():
    if settings.app_env == "local":
        return LocalStorageClient(settings.local_storage_path)
    return GCSClient(project_id=settings.gcp_project_id)
