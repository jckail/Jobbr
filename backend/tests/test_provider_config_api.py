from unittest.mock import Mock

import pytest

from jobbr import config
from tests.conftest import API


def test_selected_provider_requires_its_own_key_and_config_never_exposes_keys(client, env):
    env.setenv("JOBBR_OPENAI_API_KEY", "synthetic-openai-key-never-used")
    env.setenv("JOBBR_AI_PROVIDER", "anthropic")
    env.setenv("JOBBR_ANTHROPIC_MODEL", "claude-test-model")
    config.get_settings.cache_clear()
    response = client.get(f"{API}/config")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_provider"] == "anthropic"
    assert body["ai_provider_label"] == "Claude"
    assert body["ai_model"] == "claude-test-model"
    assert body["model"] is None
    assert body["llm_enabled"] is False
    assert body["career_enabled"] is False
    assert body["available_ai_providers"]["openai"]["configured"] is True
    assert "synthetic-openai-key" not in response.text
    env.setenv("JOBBR_ANTHROPIC_API_KEY", "synthetic-anthropic-key-never-used")
    config.get_settings.cache_clear()
    enabled = client.get(f"{API}/config")
    assert enabled.json()["model"] == "claude-test-model"
    assert enabled.json()["llm_enabled"] is True
    assert "synthetic-anthropic-key" not in enabled.text


@pytest.mark.parametrize("changed", ["provider", "model", "enabled"])
def test_stale_selection_blocks_all_ai_actions_before_execution(client, env, monkeypatch, changed):
    created = client.post(f"{API}/jobs", json={"text": "Python engineer at Acme"})
    assert created.status_code == 201
    job_id = created.json()["id"]
    initial = client.get(f"{API}/config").json()
    headers = {
        "X-Jobbr-AI-Provider": initial["ai_provider"],
        "X-Jobbr-AI-Model": initial["ai_model"],
        "X-Jobbr-AI-Enabled": "false",
    }
    if changed == "provider":
        env.setenv("JOBBR_AI_PROVIDER", "anthropic")
    elif changed == "model":
        env.setenv("JOBBR_MODEL", "changed-test-model")
    else:
        env.setenv("JOBBR_OPENAI_API_KEY", "synthetic-key-not-used")
    config.get_settings.cache_clear()
    ingestion = Mock(side_effect=AssertionError("Stale consent must not ingest"))
    generation = Mock(side_effect=AssertionError("Stale consent must not generate"))
    reextraction = Mock(side_effect=AssertionError("Stale consent must not re-extract"))
    monkeypatch.setattr("jobbr.api.services.ingest", ingestion)
    monkeypatch.setattr("jobbr.api.generate_career", generation)
    monkeypatch.setattr("jobbr.api.services.reextract", reextraction)
    for path, body in (
        (f"{API}/jobs", {"text": "Python role"}),
        (f"{API}/jobs/{job_id}/reextract", None),
        (f"{API}/jobs/{job_id}/career/cover_letter", None),
    ):
        assert client.post(path, json=body, headers=headers).status_code == 409
    ingestion.assert_not_called()
    generation.assert_not_called()
    reextraction.assert_not_called()


def test_matching_selection_allows_offline_ingest_but_partial_selection_is_rejected(client):
    settings = client.get(f"{API}/config").json()
    headers = {
        "X-Jobbr-AI-Provider": settings["ai_provider"],
        "X-Jobbr-AI-Model": settings["ai_model"],
        "X-Jobbr-AI-Enabled": "false",
    }
    body = {"text": "Python engineer at Acme"}
    assert client.post(f"{API}/jobs", json=body, headers=headers).status_code == 201
    headers.pop("X-Jobbr-AI-Enabled")
    assert client.post(f"{API}/jobs", json=body, headers=headers).status_code == 422
