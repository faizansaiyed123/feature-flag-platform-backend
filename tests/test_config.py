import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "production",
        "auth_secret_key": "v2-unique-0123456789abcdef-0123456789abcdef",
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "api.example.com",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_sample_secret() -> None:
    with pytest.raises(ValidationError, match="AUTH_SECRET_KEY"):
        production_settings(
            auth_secret_key="replace-with-a-random-secret-at-least-32-characters"
        )


def test_production_rejects_wildcard_cors_origin() -> None:
    with pytest.raises(ValidationError, match="exact origins"):
        production_settings(cors_origins="*")


def test_production_rejects_http_origin() -> None:
    with pytest.raises(ValidationError, match="HTTPS origins"):
        production_settings(cors_origins="http://app.example.com")


def test_production_accepts_exact_https_origin_and_host() -> None:
    settings = production_settings()
    assert settings.cors_origin_list == ["https://app.example.com"]
    assert settings.allowed_host_list == ["api.example.com"]
