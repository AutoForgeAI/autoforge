"""Tests for alternative API provider env construction (registry.get_effective_sdk_env)."""

import pytest

import registry


def _env_for(monkeypatch: pytest.MonkeyPatch, settings: dict[str, str]) -> dict[str, str]:
    monkeypatch.setattr(registry, "get_all_settings", lambda: settings)
    return registry.get_effective_sdk_env()


def test_kimi_code_uses_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env_for(monkeypatch, {"api_provider": "kimi", "api_auth_token": "sk-kimi-abc"})
    assert env["ANTHROPIC_BASE_URL"] == "https://api.kimi.com/coding/"
    assert env["ANTHROPIC_API_KEY"] == "sk-kimi-abc"
    assert env["ANTHROPIC_AUTH_TOKEN"] == ""
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "kimi-k2.5"


def test_moonshot_platform_uses_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env_for(monkeypatch, {"api_provider": "moonshot", "api_auth_token": "sk-platform"})
    assert env["ANTHROPIC_BASE_URL"] == "https://api.moonshot.ai/anthropic"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-platform"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "kimi-k2.5"


def test_moonshot_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env_for(monkeypatch, {
        "api_provider": "moonshot",
        "api_base_url": "https://api.moonshot.cn/anthropic",
        "api_auth_token": "sk-platform",
    })
    assert env["ANTHROPIC_BASE_URL"] == "https://api.moonshot.cn/anthropic"


def test_auth_token_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env_for(monkeypatch, {"api_provider": "kimi", "api_auth_token": "  sk-kimi-abc\n"})
    assert env["ANTHROPIC_API_KEY"] == "sk-kimi-abc"


def test_blank_base_url_falls_back_to_provider_default(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _env_for(monkeypatch, {"api_provider": "moonshot", "api_base_url": "  "})
    assert env["ANTHROPIC_BASE_URL"] == "https://api.moonshot.ai/anthropic"
