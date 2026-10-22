"""
API Provider Tests
==================

Tests for the alternative API provider env mapping in registry.get_effective_sdk_env().

Run with: python -m pytest test_api_providers.py -v
"""

import pytest

import registry
from registry import API_PROVIDERS, get_effective_sdk_env


@pytest.fixture
def settings(monkeypatch):
    """Patch the settings store with an in-memory dict."""
    store: dict[str, str] = {}
    monkeypatch.setattr(registry, "get_all_settings", lambda: dict(store))
    return store


def test_gemini_provider_definition():
    gemini = API_PROVIDERS["gemini"]
    assert gemini["base_url"] == "http://localhost:4000"
    assert gemini["auth_env_var"] == "ANTHROPIC_AUTH_TOKEN"
    assert gemini["default_model"] in {m["id"] for m in gemini["models"]}


def test_gemini_env_defaults(settings):
    settings.update({"api_provider": "gemini", "api_auth_token": "sk-proxy"})
    env = get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:4000"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-proxy"
    # Real Anthropic key must not leak to the proxy
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["CLAUDE_CODE_USE_VERTEX"] == ""
    for tier in ("OPUS", "SONNET", "HAIKU"):
        assert env[f"ANTHROPIC_DEFAULT_{tier}_MODEL"] == "gemini-2.5-pro"


def test_gemini_env_overrides(settings):
    settings.update({
        "api_provider": "gemini",
        "api_base_url": "http://proxy.internal:8080",
        "api_model": "gemini-2.5-flash",
    })
    env = get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "http://proxy.internal:8080"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "gemini-2.5-flash"
    assert "ANTHROPIC_AUTH_TOKEN" not in env
