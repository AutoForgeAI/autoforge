"""Tests for alternative API provider env construction (registry.get_effective_sdk_env)."""

import pytest

import registry


@pytest.fixture
def settings(monkeypatch):
    store: dict[str, str] = {}
    monkeypatch.setattr(registry, "get_all_settings", lambda: dict(store))
    return store


def test_glm_defaults(settings):
    settings.update({"api_provider": "glm", "api_auth_token": "zai-key"})
    env = registry.get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://api.z.ai/api/anthropic"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "zai-key"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["API_TIMEOUT_MS"] == "3000000"
    for tier in ("OPUS", "SONNET", "HAIKU"):
        assert env[f"ANTHROPIC_DEFAULT_{tier}_MODEL"] == "glm-4.7"


def test_glm_overrides(settings):
    settings.update({
        "api_provider": "glm",
        "api_auth_token": "key",
        "api_base_url": "https://open.bigmodel.cn/api/anthropic",
        "api_model": "glm-4.6",
        "api_timeout_ms": "600000",
    })
    env = registry.get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://open.bigmodel.cn/api/anthropic"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "glm-4.6"
    assert env["API_TIMEOUT_MS"] == "600000"


def test_glm_lists_4x_models():
    ids = {m["id"] for m in registry.API_PROVIDERS["glm"]["models"]}
    assert {"glm-4.7", "glm-4.6", "glm-4.5", "glm-4.5-air"} <= ids


def test_providers_without_default_timeout_leave_it_unset(settings):
    settings.update({"api_provider": "kimi", "api_auth_token": "k"})
    assert "API_TIMEOUT_MS" not in registry.get_effective_sdk_env()
