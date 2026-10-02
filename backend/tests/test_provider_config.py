import pytest
from pydantic import ValidationError

from jobbr.config import Settings


@pytest.mark.parametrize(
    ("selected", "openai_key", "claude_key", "enabled"),
    [
        ("openai", "openai-key", None, True),
        ("anthropic", None, "claude-key", True),
        ("openai", None, "claude-key", False),
        ("anthropic", "openai-key", None, False),
        ("anthropic", "openai-key", " ", False),
        ("openai", " ", "claude-key", False),
    ],
)
def test_only_selected_key_enables_ai(selected, openai_key, claude_key, enabled):
    settings = Settings(
        ai_provider=selected,
        openai_api_key=openai_key,
        anthropic_api_key=claude_key,
        _env_file=None,
    )
    assert settings.llm_enabled is enabled
    assert settings.ai_model == (
        settings.model if selected == "openai" else settings.anthropic_model
    )


@pytest.mark.parametrize("name", ["JOBBR_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"])
def test_anthropic_key_environment_aliases(monkeypatch, name):
    monkeypatch.delenv("JOBBR_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv(name, "fake-claude-key")
    settings = Settings(ai_provider="anthropic", _env_file=None)
    assert settings.anthropic_api_key == "fake-claude-key"
    assert settings.llm_enabled


def test_anthropic_specific_alias_has_precedence(monkeypatch):
    monkeypatch.setenv("JOBBR_ANTHROPIC_API_KEY", "jobbr-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "generic-key")
    assert Settings(ai_provider="anthropic", _env_file=None).anthropic_api_key == "jobbr-key"


def test_provider_default_and_model_overrides(monkeypatch):
    for name in ("JOBBR_AI_PROVIDER", "JOBBR_MODEL", "JOBBR_ANTHROPIC_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.ai_provider == "openai"
    assert settings.ai_model == "gpt-4.1-mini"
    claude = Settings(ai_provider="anthropic", anthropic_model="custom-claude", _env_file=None)
    assert claude.ai_model == "custom-claude"
    with pytest.raises(ValidationError):
        Settings(ai_provider="unknown-provider", _env_file=None)
