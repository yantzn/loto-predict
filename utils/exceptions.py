from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AppError(Exception):
    message: str
    error_code: str = "APP_ERROR"
    details: Optional[dict[str, Any]] = None
    cause: Optional[Exception] = None
    is_retryable: bool = False

    def __str__(self) -> str:
        return self.message


class ConfigError(AppError):
    def __init__(
        self,
        message: str = "Configuration error occurred.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Validation error occurred.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class DataFetchError(AppError):
    def __init__(
        self,
        message: str = "Failed to fetch draw results.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(
            message=message,
            error_code="DATA_FETCH_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class BigQueryReadError(AppError):
    def __init__(
        self,
        message: str = "Failed to read data from BigQuery.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(
            message=message,
            error_code="BIGQUERY_READ_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class BigQueryWriteError(AppError):
    def __init__(
        self,
        message: str = "Failed to write data to BigQuery.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(
            message=message,
            error_code="BIGQUERY_WRITE_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class StatisticsCalculationError(AppError):
    def __init__(
        self,
        message: str = "Failed to calculate statistics.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(
            message=message,
            error_code="STATISTICS_CALCULATION_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class PredictionGenerationError(AppError):
    def __init__(
        self,
        message: str = "Failed to generate predictions.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(
            message=message,
            error_code="PREDICTION_GENERATION_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )


class NotificationError(AppError):
    def __init__(
        self,
        message: str = "Failed to send notification.",
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = True,
    ) -> None:
        super().__init__(
            message=message,
            error_code="NOTIFICATION_ERROR",
            details=details,
            cause=cause,
            is_retryable=is_retryable,
        )
