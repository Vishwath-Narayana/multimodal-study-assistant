from app.core.config import Settings, get_settings


def test_settings_have_sane_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
