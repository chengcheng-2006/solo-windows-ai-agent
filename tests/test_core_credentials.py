"""Credential detection tests — validate _is_valid_credential and provider detection.

Scenarios:
1. No env var (unset)
2. Empty env var
3. YOUR_API_KEY placeholder
4. .env.example style placeholder
5. Invalid SecretRef
6. Valid API key (real-looking)
7. Multiple providers, only one valid
8. Output contains no credential values
"""
import os
import pytest

from solo.core.mode import _is_valid_credential, _check_provider_credential, detect_mode_report


class TestIsValidCredential:

    def test_none_is_invalid(self):
        assert _is_valid_credential(None) is False

    def test_empty_is_invalid(self):
        assert _is_valid_credential("") is False
        assert _is_valid_credential("   ") is False

    def test_your_placeholder_is_invalid(self):
        assert _is_valid_credential("YOUR_API_KEY_HERE") is False
        assert _is_valid_credential("YOUR_D…KEY") is False
        assert _is_valid_credential("YOUR_G…WORD") is False

    def test_change_me_is_invalid(self):
        assert _is_valid_credential("CHANGE_ME") is False
        assert _is_valid_credential("change_me_123") is False

    def test_short_value_is_invalid(self):
        assert _is_valid_credential("abc") is False
        assert _is_valid_credential("short") is False

    def test_placeholder_patterns(self):
        assert _is_valid_credential("placeholder") is False
        assert _is_valid_credential("XXXXX_api_key") is False

    def test_env_var_name_is_not_a_key(self):
        # Just the env var name or reference is not a valid key
        assert _is_valid_credential("DEEPSEEK_API_KEY") is False

    def test_real_key_is_valid(self):
        assert _is_valid_credential("sk-abc123def456ghi789jkl012") is True
        assert _is_valid_credential("gAAAAABkZ29vZAo=") is True
        assert _is_valid_credential("a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6") is True

    def test_mixed_placeholder_is_invalid(self):
        assert _is_valid_credential("YOUR_API_KEY") is False
        assert _is_valid_credential("ReplaceWithYourKey") is False


class TestCheckProviderCredential:

    def test_unset_env_var(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        result = _check_provider_credential("DEEPSEEK_API_KEY", "deepseek")
        assert result["configured"] is False
        assert result["provider"] == "deepseek"

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        result = _check_provider_credential("DEEPSEEK_API_KEY", "deepseek")
        assert result["configured"] is False

    def test_your_placeholder_env_var(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "YOUR_D…KEY")
        result = _check_provider_credential("DEEPSEEK_API_KEY", "deepseek")
        assert result["configured"] is False

    def test_valid_env_var(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-key-12345-test")
        result = _check_provider_credential("DEEPSEEK_API_KEY", "deepseek")
        assert result["configured"] is True

    def test_change_me_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "CHANGE_ME")
        result = _check_provider_credential("OPENAI_API_KEY", "openai")
        assert result["configured"] is False


class TestDetectModeReportCredentials:

    def test_report_no_credentials(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
        report = detect_mode_report()
        assert report["model_credentials"]["any_configured"] is False
        assert report["model_credentials"]["providers"] == []

    def test_report_placeholder_not_counted(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "YOUR_D…KEY")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("ZHIPU_API_KEY", "")
        report = detect_mode_report()
        assert report["model_credentials"]["any_configured"] is False

    def test_report_one_valid_provider(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-key-98765")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("ZHIPU_API_KEY", "")
        report = detect_mode_report()
        assert report["model_credentials"]["any_configured"] is True
        assert report["model_credentials"]["providers"] == ["deepseek"]

    def test_report_mixed_providers(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-valid-deepseek-key")
        monkeypatch.setenv("OPENAI_API_KEY", "YOUR_O…KEY")
        monkeypatch.setenv("ZHIPU_API_KEY", "")
        report = detect_mode_report()
        assert report["model_credentials"]["any_configured"] is True
        assert report["model_credentials"]["providers"] == ["deepseek"]

    def test_report_does_not_expose_values(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-super-secret-key-99999")
        report_text = str(detect_mode_report())
        # The value should not appear verbatim in the report
        assert "sk-super-secret-key-99999" not in report_text

    def test_full_mode_readiness_fields(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-key")
        report = detect_mode_report()
        fm = report["full_mode_readiness"]
        assert "docker" in fm
        assert "node" in fm
        assert "gpu" in fm
        assert "api_keys" in fm
        assert "ready" in fm
        # ready should be all(fields) — at minimum api_keys False disables full
        if fm["api_keys"] is False:
            assert fm["ready"] is False

    def test_active_mode_default_lite(self, monkeypatch):
        monkeypatch.delenv("SOLO_MODE", raising=False)
        report = detect_mode_report()
        assert report["active_mode"] == "lite"

    def test_active_mode_override_lite(self, monkeypatch):
        monkeypatch.setenv("SOLO_MODE", "lite")
        report = detect_mode_report()
        assert report["active_mode"] == "lite"

    def test_active_mode_requested_full_not_ready(self, monkeypatch):
        """Full requested but not all deps -> should be lite, not full."""
        monkeypatch.setenv("SOLO_MODE", "full")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        report = detect_mode_report()
        # Full not ready because no api_keys
        assert report["full_mode_readiness"]["ready"] is False
        assert report["active_mode"] == "lite"  # downgrade
