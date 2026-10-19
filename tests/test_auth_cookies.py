from types import SimpleNamespace

import pytest
from fastapi import Response

import app.services.auth as auth_service


@pytest.fixture
def configured_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        app_env="production",
        auth_cookie_samesite="lax",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
        api_prefix="/custom/v2/",
    )
    monkeypatch.setattr(auth_service, "get_settings", lambda: settings)


def cookie_headers(response: Response) -> list[str]:
    return [
        value.decode("latin-1")
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    ]


def test_auth_cookies_use_configured_api_prefix(
    configured_settings: None,
) -> None:
    response = Response()
    tokens = auth_service.AuthTokens(access_token="access-token", refresh_token="refresh-token")

    auth_service.set_auth_cookies(response, tokens)

    headers = cookie_headers(response)
    assert any("access_token=" in value and "Path=/" in value for value in headers)
    assert any(
        "refresh_token=refresh-token" in value and "Path=/custom/v2/auth" in value
        for value in headers
    )
    assert all("Secure" in value and "HttpOnly" in value for value in headers)


def test_clear_auth_cookies_use_configured_api_prefix(
    configured_settings: None,
) -> None:
    response = Response()

    auth_service.clear_auth_cookies(response)

    headers = cookie_headers(response)
    assert any("access_token=" in value and "Path=/" in value for value in headers)
    assert any("refresh_token=" in value and "Path=/custom/v2/auth" in value for value in headers)
