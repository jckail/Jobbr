import json

import httpcore
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from jobbr import discovery
from jobbr.api import require_access


def greenhouse(**changes):
    row = {
        "id": 123,
        "title": "Data Engineer",
        "location": {"name": "US"},
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
        "content": "&lt;p&gt;Build Python pipelines.&lt;/p&gt;",
    }
    return {**row, **changes}


def lever(**changes):
    row = {
        "id": "abc-123",
        "text": "Remote Engineer",
        "categories": {"location": "US"},
        "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        "descriptionPlain": "Python",
        "workplaceType": "remote",
        "lists": [{"text": "Requirements", "content": "<p>SQL</p>"}],
    }
    return {**row, **changes}


def response(monkeypatch, payload):
    calls = []

    def fetch(endpoint):
        calls.append(endpoint)
        return json.dumps(payload)

    monkeypatch.setattr(discovery, "fetch_board_json", fetch)
    return calls


def test_greenhouse_real_facts_and_provenance(monkeypatch):
    calls = response(monkeypatch, {"jobs": [greenhouse()]})
    result = discovery.discover("greenhouse", "acme", q="python")
    assert calls == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"]
    assert result.postings[0].source_id == "123"
    assert result.postings[0].company is None
    assert result.postings[0].raw_text == "Build Python pipelines."
    assert result.postings[0].remote_policy == "unknown"
    assert result.fetched_at.tzinfo is not None
    assert result.source_url == calls[0]


def test_lever_normalization_and_filters(monkeypatch):
    calls = response(
        monkeypatch,
        [
            lever(),
            lever(
                id="office", hostedUrl="https://jobs.lever.co/acme/office", workplaceType="on-site"
            ),
        ],
    )
    result = discovery.discover("lever", "acme", q="sql", remote="remote")
    assert len(result.postings) == 1
    assert "Requirements\nSQL" in result.postings[0].raw_text
    assert calls[0] == "https://api.lever.co/v0/postings/acme?mode=json&limit=100"


@pytest.mark.parametrize(
    "board",
    [
        "https://internal.example",
        "../secret",
        "x/y",
        "x?callback=evil",
        "x%2fy",
        "x@evil",
        "a" * 81,
        "bücher",
        "",
        "x\n",
    ],
)
def test_tokens_rejected_before_fetch(monkeypatch, board):
    def fail(*args):
        pytest.fail("Invalid board reached fetch")

    monkeypatch.setattr(discovery, "fetch_board_json", fail)
    with pytest.raises(ValueError, match="board token"):
        discovery.discover("lever", board)


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.lever.co/acme/abc-123",
        "https://user:secret@jobs.lever.co/acme/abc-123",
        "https://jobs.lever.co.evil/acme/abc-123",
        "https://127.0.0.1/acme/abc-123",
        "https://jobs.lever.co:444/acme/abc-123",
        "https://jobs.lever.co/other/abc-123",
        "javascript:alert(1)",
        "https://jobs.lever.co/acme/abc-123\n",
    ],
)
def test_unsafe_links_omitted_explicitly(monkeypatch, url):
    response(monkeypatch, [lever(hostedUrl=url)])
    result = discovery.discover("lever", "acme")
    assert result.postings == []
    assert result.skipped_unsafe_links == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "bad"},
        {"jobs": {}},
        {"jobs": [greenhouse(id="123")]},
        {"jobs": [greenhouse(location="not object")]},
        {"jobs": [greenhouse(title={})]},
    ],
)
def test_malformed_greenhouse_fails_not_empty(monkeypatch, payload):
    response(monkeypatch, payload)
    with pytest.raises(discovery.DiscoveryError):
        discovery.discover("greenhouse", "acme")


def test_invalid_json_sanitized(monkeypatch):
    monkeypatch.setattr(discovery, "fetch_board_json", lambda _: "private secret invalid JSON")
    with pytest.raises(discovery.DiscoveryError) as exc:
        discovery.discover("lever", "acme")
    assert "private secret" not in str(exc.value)


def test_results_and_text_bounded(monkeypatch):
    response(monkeypatch, {"jobs": [greenhouse(content="x" * 30000)] * 101})
    result = discovery.discover("greenhouse", "acme")
    assert len(result.postings) == 100
    assert result.truncated
    assert len(result.postings[0].raw_text) == discovery.TEXT_CAP


def test_valid_empty_board_is_explicit_success(monkeypatch):
    response(monkeypatch, [])
    assert discovery.discover("lever", "acme").postings == []


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://api.lever.co/v0/postings/acme?mode=json&limit=100",
        "https://api.lever.co.evil/v0/postings/acme",
        "https://api.lever.co/v0/postings/../secrets",
        "https://boards-api.greenhouse.io/arbitrary",
        "https://user@api.lever.co/v0/postings/acme?mode=json&limit=100",
    ],
)
def test_arbitrary_endpoints_rejected(endpoint):
    with pytest.raises(discovery.DiscoveryError, match="endpoint"):
        discovery.fetch_board_json(endpoint)


def test_fetch_reuses_guards_and_rejects_redirect(monkeypatch):
    calls = []

    def resolve(endpoint, deadline):
        calls.append(endpoint)
        return httpx.URL(endpoint), "93.184.216.34"

    monkeypatch.setattr(discovery.safefetch, "_resolve_url", resolve)

    def transport(url, address, deadline):
        assert address == "93.184.216.34"

        def handler(request):
            assert request.headers["accept-encoding"] == "identity"
            return httpx.Response(302, headers={"Location": "https://evil.example"})

        return httpx.MockTransport(handler)

    monkeypatch.setattr(discovery.safefetch, "_PinnedTransport", transport)
    with pytest.raises(discovery.DiscoveryError, match="unavailable"):
        discovery.fetch_board_json(discovery.board_endpoint("lever", "acme"))
    assert len(calls) == 1


def test_network_error_explicit_sanitized(monkeypatch):
    def fail(endpoint, deadline):
        raise httpcore.ConnectError("upstream secret")

    monkeypatch.setattr(discovery.safefetch, "_resolve_url", fail)
    with pytest.raises(discovery.DiscoveryError) as exc:
        discovery.fetch_board_json(discovery.board_endpoint("lever", "acme"))
    assert "upstream secret" not in str(exc.value)


def test_router_requires_access_before_network(monkeypatch):
    app = FastAPI()
    app.include_router(discovery.router)

    def denied():
        raise HTTPException(401, "Unauthorized")

    app.dependency_overrides[require_access] = denied
    with TestClient(app) as client:
        assert client.get("/api/discovery/boards/lever/acme").status_code == 401
