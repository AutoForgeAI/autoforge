"""Tests for API provider presets and the SDK environment they produce."""

import pytest

import registry
from registry import API_PROVIDERS, get_effective_sdk_env


@pytest.mark.parametrize("provider_id", list(API_PROVIDERS))
def test_provider_definitions_are_well_formed(provider_id):
    provider = API_PROVIDERS[provider_id]
    assert provider["name"]
    model_ids = [m["id"] for m in provider["models"]]
    if provider["default_model"]:
        assert provider["default_model"] in model_ids


def test_gemini_provider_uses_gateway_defaults(monkeypatch):
    monkeypatch.setattr(registry, "get_all_settings", lambda: {"api_provider": "gemini"})

    env = get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:4000"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "gemini-2.5-pro"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "gemini-2.5-pro"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "gemini-2.5-pro"
    # Ambient Anthropic/Vertex credentials must not leak into the gateway session
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["CLAUDE_CODE_USE_VERTEX"] == ""


def test_gemini_provider_honours_user_overrides(monkeypatch):
    monkeypatch.setattr(registry, "get_all_settings", lambda: {
        "api_provider": "gemini",
        "api_base_url": "https://litellm.internal.example.com",
        "api_auth_token": "sk-litellm-master",
        "api_model": "gemini-2.5-flash",
    })

    env = get_effective_sdk_env()

    assert env["ANTHROPIC_BASE_URL"] == "https://litellm.internal.example.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-litellm-master"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "gemini-2.5-flash"
