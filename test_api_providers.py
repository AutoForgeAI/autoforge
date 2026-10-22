"""
API Provider Environment Tests
==============================

Tests for get_effective_sdk_env() in registry.py, focusing on the GLM
(Zhipu AI / Z.ai) provider.

Run with: python -m pytest test_api_providers.py -v
"""

import unittest
from unittest.mock import patch

from registry import API_PROVIDERS, get_effective_sdk_env


def _env_for(settings: dict[str, str]) -> dict[str, str]:
    with patch("registry.get_all_settings", return_value=settings):
        return get_effective_sdk_env()


class TestGlmProvider(unittest.TestCase):
    def test_glm_4x_models_listed(self):
        model_ids = {m["id"] for m in API_PROVIDERS["glm"]["models"]}
        self.assertTrue({"glm-4.7", "glm-4.6", "glm-4.5-air"} <= model_ids)

    def test_glm_defaults(self):
        env = _env_for({"api_provider": "glm", "api_auth_token": "secret"})
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://api.z.ai/api/anthropic")
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "secret")
        self.assertEqual(env["ANTHROPIC_API_KEY"], "")
        for tier in ("OPUS", "SONNET", "HAIKU"):
            self.assertEqual(env[f"ANTHROPIC_DEFAULT_{tier}_MODEL"], "glm-4.7")
        self.assertEqual(env["API_TIMEOUT_MS"], "3000000")

    def test_glm_custom_model_and_china_endpoint(self):
        env = _env_for({
            "api_provider": "glm",
            "api_model": "glm-4.5",
            "api_base_url": "https://open.bigmodel.cn/api/anthropic",
        })
        self.assertEqual(env["ANTHROPIC_BASE_URL"], "https://open.bigmodel.cn/api/anthropic")
        self.assertEqual(env["ANTHROPIC_DEFAULT_SONNET_MODEL"], "glm-4.5")

    def test_explicit_timeout_overrides_default(self):
        env = _env_for({"api_provider": "glm", "api_timeout_ms": "600000"})
        self.assertEqual(env["API_TIMEOUT_MS"], "600000")

    def test_other_providers_get_no_default_timeout(self):
        env = _env_for({"api_provider": "kimi"})
        self.assertNotIn("API_TIMEOUT_MS", env)


if __name__ == "__main__":
    unittest.main()
