from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


_LOCAL_ENV_LOADED = False


def _load_local_env_file() -> None:
    global _LOCAL_ENV_LOADED
    if _LOCAL_ENV_LOADED:
        return

    # pytest 実行時はテスト側の環境制御を優先し、ローカル .env の自動注入で
    # 期待値が変わらないようにする。
    if os.getenv("PYTEST_CURRENT_TEST"):
        _LOCAL_ENV_LOADED = True
        return

    root_dir = Path(__file__).resolve().parents[2]
    env_path = root_dir / ".env.local"
    if not env_path.exists():
        _LOCAL_ENV_LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        # 実行時に明示された環境変数を最優先し、.env.local は不足分だけ補完する。
        if os.getenv(key) is None:
            os.environ[key] = value

    _LOCAL_ENV_LOADED = True


def _first_env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _to_int(value: Optional[str], default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(str(value).strip())


@dataclass(frozen=True)
class GCPSettings:
    project_id: str
    region: str
    bigquery_dataset: str
    table_loto6_history: str
    table_loto7_history: str
    table_prediction_runs: str
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
        normalized = str(lottery_type).strip().lower()
        if normalized == "loto6":
            return self.history_limit_loto6 or self.default_stats_target_draws
        if normalized == "loto7":
            return self.history_limit_loto7 or self.default_stats_target_draws
        raise ValueError(f"unsupported lottery_type: {lottery_type}")


@dataclass(frozen=True)
class LineSettings:
    channel_access_token: Optional[str]
    user_id: Optional[str]


@dataclass(frozen=True)
class LoggingSettings:
    level: str
    service_name: str


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    app_timezone: str
    gcp: GCPSettings
    lottery: LotterySettings
    line: LineSettings
    logging: LoggingSettings
    local_storage_path: str

    @property
    def is_local(self) -> bool:
        return self.app_env.lower() == "local"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod", "gcp"}


def _validate(settings: AppSettings) -> None:
    lottery = settings.lottery

    if lottery.default_stats_target_draws <= 0:
        raise ValueError("STATS_TARGET_DRAWS must be greater than 0")
    if lottery.history_limit_loto6 <= 0:
        raise ValueError("HISTORY_LIMIT_LOTO6 must be greater than 0")
    if lottery.history_limit_loto7 <= 0:
        raise ValueError("HISTORY_LIMIT_LOTO7 must be greater than 0")
    if lottery.prediction_count <= 0:
        raise ValueError("PREDICTION_COUNT must be greater than 0")
    if lottery.loto6_number_min > lottery.loto6_number_max:
        raise ValueError("LOTO6_NUMBER_MIN must be <= LOTO6_NUMBER_MAX")
    if lottery.loto7_number_min > lottery.loto7_number_max:
        raise ValueError("LOTO7_NUMBER_MIN must be <= LOTO7_NUMBER_MAX")
    if lottery.loto6_pick_count <= 0:
        raise ValueError("LOTO6_PICK_COUNT must be greater than 0")
    if lottery.loto7_pick_count <= 0:
        raise ValueError("LOTO7_PICK_COUNT must be greater than 0")
    if lottery.loto6_pick_count > (lottery.loto6_number_max - lottery.loto6_number_min + 1):
        raise ValueError("LOTO6_PICK_COUNT is larger than available range")
    if lottery.loto7_pick_count > (lottery.loto7_number_max - lottery.loto7_number_min + 1):
        raise ValueError("LOTO7_PICK_COUNT is larger than available range")


def require_line_settings(settings: AppSettings) -> None:
    if not settings.line.channel_access_token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is required")
    if not settings.line.user_id:
        raise ValueError("LINE_USER_ID is required")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    _load_local_env_file()

    app_env = _first_env("APP_ENV", default="local") or "local"
    app_timezone = _first_env("APP_TIMEZONE", default="Asia/Tokyo") or "Asia/Tokyo"
    default_stats_target_draws = _to_int(_first_env("STATS_TARGET_DRAWS"), 100)

    settings = AppSettings(
        app_env=app_env,
        app_timezone=app_timezone,
        gcp=GCPSettings(
            project_id=_first_env("GCP_PROJECT_ID", default="") or "",
            region=_first_env("GCP_REGION", default="asia-northeast1") or "asia-northeast1",
            bigquery_dataset=_first_env("BQ_DATASET", default="loto_predict") or "loto_predict",
            table_loto6_history=_first_env("BQ_TABLE_LOTO6_HISTORY", default="loto6_history") or "loto6_history",
            table_loto7_history=_first_env("BQ_TABLE_LOTO7_HISTORY", default="loto7_history") or "loto7_history",
            table_prediction_runs=_first_env("BQ_TABLE_PREDICTION_RUNS", default="prediction_runs") or "prediction_runs",
            raw_bucket_name=_first_env("GCS_BUCKET_RAW", default="") or "",
            import_topic_name=_first_env("PUBSUB_IMPORT_TOPIC", default="import-loto-results") or "import-loto-results",
            notify_topic_name=_first_env("PUBSUB_NOTIFY_TOPIC", default="notify-loto-prediction") or "notify-loto-prediction",
        ),
        lottery=LotterySettings(
            default_stats_target_draws=default_stats_target_draws,
            history_limit_loto6=_to_int(_first_env("HISTORY_LIMIT_LOTO6"), default_stats_target_draws),
            history_limit_loto7=_to_int(_first_env("HISTORY_LIMIT_LOTO7"), default_stats_target_draws),
            prediction_count=_to_int(_first_env("PREDICTION_COUNT"), 5),
            loto6_number_min=_to_int(_first_env("LOTO6_NUMBER_MIN"), 1),
            loto6_number_max=_to_int(_first_env("LOTO6_NUMBER_MAX"), 43),
            loto6_pick_count=_to_int(_first_env("LOTO6_PICK_COUNT"), 6),
            loto7_number_min=_to_int(_first_env("LOTO7_NUMBER_MIN"), 1),
            loto7_number_max=_to_int(_first_env("LOTO7_NUMBER_MAX"), 37),
            loto7_pick_count=_to_int(_first_env("LOTO7_PICK_COUNT"), 7),
        ),
        line=LineSettings(
            channel_access_token=_first_env("LINE_CHANNEL_ACCESS_TOKEN", default=None),
            user_id=_first_env("LINE_USER_ID", default=None),
        ),
        logging=LoggingSettings(
            level=_first_env("LOG_LEVEL", default="INFO") or "INFO",
            service_name=_first_env("SERVICE_NAME", default="loto-predict") or "loto-predict",
        ),
        local_storage_path=_first_env("LOCAL_STORAGE_PATH", default="./local_storage") or "./local_storage",
    )
    _validate(settings)

    # local は dry-run を許容し、本番系環境では LINE 設定を必須にする。
    if settings.is_production:
        require_line_settings(settings)

    return settings
