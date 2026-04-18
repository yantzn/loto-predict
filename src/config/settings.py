from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _first_env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: Optional[str], default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(str(value).strip())


@dataclass(frozen=True)
class GCPSettings:
    project_id: str
    region: str
    bigquery_dataset: str
    raw_bucket_name: str
    import_topic_name: str
    notify_topic_name: str


@dataclass(frozen=True)
class LotterySettings:
    default_stats_target_draws: int
    history_limit_loto6: int
    history_limit_loto7: int
    prediction_count: int
    loto6_number_min: int
    loto6_number_max: int
    loto6_pick_count: int
    loto7_number_min: int
    loto7_number_max: int
    loto7_pick_count: int

    def stats_target_draws_for(self, lottery_type: str) -> int:
        normalized = lottery_type.strip().lower()
        if normalized == "loto6":
            return self.history_limit_loto6 or self.default_stats_target_draws
        if normalized == "loto7":
            return self.history_limit_loto7 or self.default_stats_target_draws
        raise ValueError(f"unsupported lottery_type: {lottery_type}")


@dataclass(frozen=True)
class LineSettings:
    channel_access_token: str
    import os
    from dataclasses import dataclass, asdict

    @dataclass
    class LotterySettings:
        prediction_count: int = int(os.getenv("PREDICTION_COUNT", 5))
        history_limit_loto6: int = int(os.getenv("HISTORY_LIMIT_LOTO6", 100))
        history_limit_loto7: int = int(os.getenv("HISTORY_LIMIT_LOTO7", 100))
        stats_target_draws: int = int(os.getenv("STATS_TARGET_DRAWS", 50))

        def stats_target_draws_for(self, lottery_type: str) -> int:
            if lottery_type == "loto6":
                return self.history_limit_loto6
            elif lottery_type == "loto7":
                return self.history_limit_loto7
            return self.stats_target_draws

    @dataclass
    class LocalSettings:
        storage_path: str = os.getenv("LOCAL_STORAGE_PATH", "./local_storage")


    # AppSettingsにapp_envのみを持たせ、is_local/is_productionはapp_envで判定
    @dataclass(frozen=True)
    class AppSettings:
        app_env: str
        timezone: str
        gcp: GCPSettings
        lottery: LotterySettings
        line: LineSettings
        logging: 'LoggingSettings'
        local: LocalSettings

        @property
        def is_local(self) -> bool:
            return self.app_env == "local"

        @property
        def is_production(self) -> bool:
            return self.app_env == "production"

        def safe_dict(self) -> dict[str, object]:
            return {
                "app_env": self.app_env,
                "timezone": self.timezone,
                "gcp": {
                    "project_id": self.gcp.project_id,
                    "region": self.gcp.region,
                    "bigquery_dataset": self.gcp.bigquery_dataset,
                    "raw_bucket_name": self.gcp.raw_bucket_name,
                    "import_topic_name": self.gcp.import_topic_name,
                    "notify_topic_name": self.gcp.notify_topic_name,
                },
                "lottery": {
                    "default_stats_target_draws": self.lottery.default_stats_target_draws,
                    "history_limit_loto6": self.lottery.history_limit_loto6,
                    "history_limit_loto7": self.lottery.history_limit_loto7,
                    "prediction_count": self.lottery.prediction_count,
                },
                "line": {
                    "channel_access_token_configured": bool(self.line.channel_access_token),
                    "user_id_configured": bool(self.line.user_id),
                },
                "local": {
                    "storage_path": self.local.storage_path,
                },
            }


def _validate(settings: AppSettings) -> None:
    if settings.lottery.prediction_count <= 0:
        raise ValueError("PREDICTION_COUNT must be greater than 0")

    if settings.lottery.loto6_pick_count > (
        settings.lottery.loto6_number_max - settings.lottery.loto6_number_min + 1
    ):
        raise ValueError("LOTO6_PICK_COUNT is larger than available range")

    if settings.lottery.loto7_pick_count > (
        settings.lottery.loto7_number_max - settings.lottery.loto7_number_min + 1
    ):
        raise ValueError("LOTO7_PICK_COUNT is larger than available range")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    env = _first_env("APP_ENV", "ENV", default="local") or "local"

    settings = AppSettings(
        env=env,
        timezone=_first_env("APP_TIMEZONE", "TIMEZONE", default="Asia/Tokyo") or "Asia/Tokyo",
        gcp=GCPSettings(
            project_id=_first_env("GCP_PROJECT_ID", default="") or "",
            region=_first_env("GCP_REGION", default="asia-northeast1") or "asia-northeast1",
            bigquery_dataset=_first_env("BIGQUERY_DATASET", "BQ_DATASET", default="loto_predict") or "loto_predict",
            raw_bucket_name=_first_env("GCS_BUCKET_RAW", "RAW_BUCKET_NAME", default="") or "",
            import_topic_name=_first_env("PUBSUB_IMPORT_TOPIC", default="import-loto-results") or "import-loto-results",
            notify_topic_name=_first_env("PUBSUB_NOTIFY_TOPIC", default="notify-loto-prediction") or "notify-loto-prediction",
        ),
        lottery=LotterySettings(
            default_stats_target_draws=_to_int(_first_env("STATS_TARGET_DRAWS"), 100),
            history_limit_loto6=_to_int(_first_env("HISTORY_LIMIT_LOTO6", "STATS_TARGET_DRAWS"), 100),
            history_limit_loto7=_to_int(_first_env("HISTORY_LIMIT_LOTO7", "STATS_TARGET_DRAWS"), 100),
            prediction_count=_to_int(_first_env("PREDICTION_COUNT"), 5),
            loto6_number_min=_to_int(_first_env("LOTO6_NUMBER_MIN"), 1),
            loto6_number_max=_to_int(_first_env("LOTO6_NUMBER_MAX"), 43),
            loto6_pick_count=_to_int(_first_env("LOTO6_PICK_COUNT"), 6),
            loto7_number_min=_to_int(_first_env("LOTO7_NUMBER_MIN"), 1),
            loto7_number_max=_to_int(_first_env("LOTO7_NUMBER_MAX"), 37),
            loto7_pick_count=_to_int(_first_env("LOTO7_PICK_COUNT"), 7),
        ),
        line=LineSettings(
            channel_access_token=_first_env("LINE_CHANNEL_ACCESS_TOKEN", default="") or "",
            user_id=_first_env("LINE_USER_ID", default="") or "",
        ),
        logging=LoggingSettings(
            level=_first_env("LOG_LEVEL", default="INFO") or "INFO",
            service_name=_first_env("SERVICE_NAME", default="loto-predict") or "loto-predict",
        ),
        local=LocalSettings(
            storage_path=_first_env("LOCAL_STORAGE_PATH", default="./local_storage") or "./local_storage",
        ),
    )
    _validate(settings)
    return settings
