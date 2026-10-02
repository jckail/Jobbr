"""Private-data and paid-action boundaries through the real ASGI app."""

import pytest
from fastapi.testclient import TestClient

from jobbr.main import create_app
from tests.conftest import API, reset_settings


def test_private_mode_rejects_unconfigured_access(env):
    env.setenv("JOBBR_PRIVATE_INSTANCE", "true")
    reset_settings()
    with pytest.raises(RuntimeError, match="Private instances require"):
        create_app()


def test_private_token_locks_reads_and_writes(env):
    env.setenv("JOBBR_PRIVATE_INSTANCE", "true")
    env.setenv("JOBBR_API_TOKEN", "owner-only")
    reset_settings()
    with TestClient(create_app()) as client:
        for path in ("/jobs", "/profile", "/stats", "/jobs/1"):
            assert client.get(API + path).status_code == 401
            assert client.get(API + path, headers={"X-Jobbr-Token": "wrong"}).status_code == 401
        assert client.get(API + "/jobs", headers={"X-Jobbr-Token": "owner-only"}).status_code == 200
        assert client.get(API + "/config").status_code == 200
        assert client.post(API + "/jobs", json={"text": "Private role"}).status_code == 401


def test_unready_oidc_fails_closed_even_with_api_token(env):
    env.setenv("JOBBR_OPENAI_AUTH_ENABLED", "true")
    env.setenv("JOBBR_API_TOKEN", "owner-only")
    with TestClient(create_app()) as client:
        headers = {"X-Jobbr-Token": "owner-only"}
        assert client.get(API + "/profile", headers=headers).status_code == 503
        assert client.post(API + "/jobs", json={"text": "role"}, headers=headers).status_code == 503
        status = client.get(API + "/auth/session").json()
        assert status["enabled"]
        assert not status["ready"]
        assert not status["authenticated"]


def test_career_api_no_key_is_explicit_and_protected(client, env):
    job = client.post(
        API + "/jobs", json={"text": "Engineer. Python SQL Kubernetes. Remote."}
    ).json()
    path = f"{API}/jobs/{job['id']}/career/cover_letter"
    assert client.post(path).status_code == 503
    assert client.post(f"{API}/jobs/{job['id']}/career/unknown").status_code == 422
    assert client.post(f"{API}/jobs/999/career/cover_letter").status_code == 404
    env.setenv("JOBBR_API_TOKEN", "owner-only")
    reset_settings()
    assert client.post(path).status_code == 401


def test_private_api_headers(client):
    response = client.get(API + "/profile")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
