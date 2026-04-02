from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if isinstance(value, str):
        value = value.strip()
    return value


def _require_env(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise ValueError(f"Required environment variable is not set: {name}")
    return value


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _to_int(value: Optional[str], default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer value: {value}") from exc


@dataclass(frozen=True)
class GCPSettings:
    project_id: str
    region: str
    bigquery_dataset: str


@dataclass(frozen=True)
class LotterySettings:
    stats_target_draws: int
    prediction_count: int
    loto6_number_min: int
    loto6_number_max: int
    loto6_pick_count: int
    loto7_number_min: int
    loto7_number_max: int
    loto7_pick_count: int


@dataclass(frozen=True)
class LineSettings:
    channel_access_token: str
    user_id: str


@dataclass(frozen=True)
class LoggingSettings:
    level: str
    json_logs: bool
    service_name: str


@dataclass(frozen=True)
class AppSettings:
    env: str
    timezone: str
    gcp: GCPSettings
    lottery: LotterySettings
    line: LineSettings
    logging: LoggingSettings

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    def safe_dict(self) -> dict[str, object]:
        return {
            "env": self.env,
            "timezone": self.timezone,
            "gcp": {
                "project_id": self.gcp.project_id,
                "region": self.gcp.region,
                "bigquery_dataset": self.gcp.bigquery_dataset,
            },
            "lottery": {
                "stats_target_draws": self.lottery.stats_target_draws,
                "prediction_count": self.lottery.prediction_count,
                "loto6_number_min": self.lottery.loto6_number_min,
                "loto6_number_max": self.lottery.loto6_number_max,
                "loto6_pick_count": self.lottery.loto6_pick_count,
                "loto7_number_min": self.lottery.loto7_number_min,
                "loto7_number_max": self.lottery.loto7_number_max,
                "loto7_pick_count": self.lottery.loto7_pick_count,
            },
            "logging": {
                "level": self.logging.level,
                "json_logs": self.logging.json_logs,
                "service_name": self.logging.service_name,
            },
            "line": {
                "user_id_configured": bool(self.line.user_id),
                "channel_access_token_configured": bool(self.line.channel_access_token),
            },
        }


def _validate_settings(settings: AppSettings) -> None:
    if settings.lottery.prediction_count <= 0:
        raise ValueError("PREDICTION_COUNT must be greater than 0")

    if settings.lottery.stats_target_draws <= 0:
        raise ValueError("STATS_TARGET_DRAWS must be greater than 0")

    if settings.lottery.loto6_number_min >= settings.lottery.loto6_number_max:
        raise ValueError("LOTO6 number range is invalid")

    if settings.lottery.loto7_number_min >= settings.lottery.loto7_number_max:
        raise ValueError("LOTO7 number range is invalid")

    loto6_population = settings.lottery.loto6_number_max - settings.lottery.loto6_number_min + 1
    loto7_population = settings.lottery.loto7_number_max - settings.lottery.loto7_number_min + 1

    if settings.lottery.loto6_pick_count > loto6_population:
        raise ValueError("LOTO6_PICK_COUNT is larger than available number range")

    if settings.lottery.loto7_pick_count > loto7_population:
        raise ValueError("LOTO7_PICK_COUNT is larger than available number range")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings(
        env=_get_env("APP_ENV", "dev") or "dev",
        timezone=_get_env("APP_TIMEZONE", "Asia/Tokyo") or "Asia/Tokyo",
        gcp=GCPSettings(
            project_id=_require_env("GCP_PROJECT_ID"),
            region=_get_env("GCP_REGION", "asia-northeast1") or "asia-northeast1",
            bigquery_dataset=_require_env("BIGQUERY_DATASET"),
        ),
        lottery=LotterySettings(
            stats_target_draws=_to_int(_get_env("STATS_TARGET_DRAWS"), 100),
            prediction_count=_to_int(_get_env("PREDICTION_COUNT"), 5),
            loto6_number_min=_to_int(_get_env("LOTO6_NUMBER_MIN"), 1),
            loto6_number_max=_to_int(_get_env("LOTO6_NUMBER_MAX"), 43),
            loto6_pick_count=_to_int(_get_env("LOTO6_PICK_COUNT"), 6),
            loto7_number_min=_to_int(_get_env("LOTO7_NUMBER_MIN"), 1),
            loto7_number_max=_to_int(_get_env("LOTO7_NUMBER_MAX"), 37),
            loto7_pick_count=_to_int(_get_env("LOTO7_PICK_COUNT"), 7),
        ),
        line=LineSettings(
            channel_access_token=_require_env("LINE_CHANNEL_ACCESS_TOKEN"),
            user_id=_require_env("LINE_USER_ID"),
        ),
        logging=LoggingSettings(
            level=_get_env("LOG_LEVEL", "INFO") or "INFO",
            json_logs=_to_bool(_get_env("LOG_JSON"), True),
            service_name=_get_env("SERVICE_NAME", "loto-predict-line") or "loto-predict-line",
        ),
    )

    _validate_settings(settings)
    return settings
