from dataclasses import dataclass
from functools import lru_cache
import os

@dataclass(frozen=True)
class GCPSettings:
    project_id: str
    bigquery_dataset: str

@dataclass(frozen=True)
class LotterySettings:
    stats_target_draws: int
    prediction_count: int

@dataclass(frozen=True)
class LineSettings:
    channel_access_token: str
    user_id: str

@dataclass(frozen=True)
class AppSettings:
    env: str
    gcp: GCPSettings
    lottery: LotterySettings
    line: LineSettings

@lru_cache()
def get_settings() -> AppSettings:
    env = os.environ.get("ENV", "local")
    gcp = GCPSettings(
        project_id=os.environ.get("GCP_PROJECT_ID", ""),
        bigquery_dataset=os.environ.get("BQ_DATASET", ""),
    )
    lottery = LotterySettings(
        stats_target_draws=int(os.environ.get("STATS_TARGET_DRAWS", 100)),
        prediction_count=int(os.environ.get("PREDICTION_COUNT", 5)),
    )
    line = LineSettings(
        channel_access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
        user_id=os.environ.get("LINE_USER_ID", ""),
    )
    return AppSettings(env=env, gcp=gcp, lottery=lottery, line=line)
