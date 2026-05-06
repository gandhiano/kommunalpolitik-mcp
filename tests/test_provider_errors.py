from __future__ import annotations

import requests

from src.agent.providers import ProviderError, _raise_provider_error


def test_openai_quota_error_maps_to_429() -> None:
    response = requests.Response()
    response.status_code = 429
    response._content = b'{"error":{"message":"You exceeded your current quota."}}'

    try:
        _raise_provider_error(response, "openai")
    except ProviderError as exc:
        assert exc.status_code == 429
        assert "quota exceeded" in exc.message
        assert "You exceeded your current quota" in exc.message
    else:
        raise AssertionError("ProviderError was not raised")


def test_provider_auth_error_maps_to_401() -> None:
    response = requests.Response()
    response.status_code = 401
    response._content = b'{"error":{"message":"Incorrect API key provided."}}'

    try:
        _raise_provider_error(response, "openai")
    except ProviderError as exc:
        assert exc.status_code == 401
        assert "authentication failed" in exc.message
    else:
        raise AssertionError("ProviderError was not raised")
