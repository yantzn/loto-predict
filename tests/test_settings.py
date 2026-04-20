import pytest

from src.config.settings import get_settings


def test_get_settings_local_allows_missing_line_settings(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Tokyo")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("BQ_DATASET", "loto_predict")
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("LINE_USER_ID", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_env == "local"
    assert settings.line.user_id is None
    assert settings.is_local is True
    assert settings.lottery.stats_target_draws_for("loto6") == settings.lottery.history_limit_loto6
    assert settings.lottery.stats_target_draws_for("loto7") == settings.lottery.history_limit_loto7


def test_get_settings_production_flag(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "gcp")
    monkeypatch.setenv("LINE_USER_ID", "user-123")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "token")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.is_local is False
    assert settings.is_production is True


def test_get_settings_raises_when_line_missing_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "gcp")
    monkeypatch.delenv("LINE_USER_ID", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="LINE_CHANNEL_ACCESS_TOKEN"):
        get_settings()
