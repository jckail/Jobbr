"""Offline board observation fixtures; no provider or public network dispatch."""

import json

import anyio
import pytest

from jobbr import discovery
from jobbr.canonical import Identity

GH = Identity("greenhouse", "acme", "123")
LEVER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
LEVER = Identity("lever", "acme", LEVER_ID)


def row(posting_id=123, **changes):
    return {
        "id": posting_id,
        "title": "Engineer",
        "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{posting_id}",
        **changes,
    }


def check(monkeypatch, payload, identity=GH):
    calls = []

    def fetch(endpoint, *, deadline=None):
        assert deadline is not None
        calls.append(endpoint)
        return json.dumps(payload)

    monkeypatch.setattr(discovery, "fetch_board_json", fetch)
    result = anyio.run(discovery.observe_identity, identity)
    assert len(calls) == 1
    assert result.checked_at.tzinfo is not None
    return result


@pytest.mark.parametrize(
    ("payload", "state", "reason"),
    [
        ({"jobs": [row()], "meta": {"total": 1}}, "available", "listed"),
        ({"jobs": [row(456)], "meta": {"total": 1}}, "unavailable", "absent_complete_board"),
        ({"jobs": [], "meta": {"total": 0}}, "unavailable", "absent_complete_board"),
        ({"jobs": [], "meta": {"total": True}}, "unknown", "incomplete_snapshot"),
        ({"jobs": [], "meta": {"total": 1}}, "unknown", "incomplete_snapshot"),
        ({"jobs": []}, "unknown", "incomplete_snapshot"),
        ({"jobs": [row(absolute_url="https://evil.example/123")]}, "unknown", "invalid_data"),
        ({"jobs": [row(), row()]}, "unknown", "invalid_data"),
        ({"jobs": [{"id": "123"}]}, "unknown", "invalid_data"),
        ({"error": "not a board"}, "unknown", "invalid_data"),
    ],
)
def test_board_observations(monkeypatch, payload, state, reason):
    result = check(monkeypatch, payload)
    assert (result.state, result.reason) == (state, reason)


def test_large_board_can_prove_presence_but_not_absence(monkeypatch):
    rows = [row(i) for i in range(1, 102)]
    present = check(
        monkeypatch, {"jobs": rows, "meta": {"total": 101}}, Identity("greenhouse", "acme", "1")
    )
    missed = check(
        monkeypatch, {"jobs": rows, "meta": {"total": 101}}, Identity("greenhouse", "acme", "101")
    )
    assert present.state == "available"
    assert (missed.state, missed.reason) == ("unknown", "incomplete_snapshot")


def test_lever_short_result_does_not_prove_absence(monkeypatch):
    absent = check(monkeypatch, [], LEVER)
    present = check(
        monkeypatch,
        [
            {
                "id": LEVER_ID,
                "text": "Engineer",
                "hostedUrl": f"https://jobs.lever.co/acme/{LEVER_ID}",
            }
        ],
        LEVER,
    )
    assert (absent.state, absent.reason) == ("unknown", "incomplete_snapshot")
    assert present.state == "available"


@pytest.mark.parametrize(
    "identity",
    [None, Identity("greenhouse", "../private", "123"), Identity("lever", "acme", "bad-id")],
)
def test_unsupported_identity_never_fetches(monkeypatch, identity):
    def no_fetch(*args, **kwargs):
        raise AssertionError("Unsupported identity fetched")

    monkeypatch.setattr(discovery, "fetch_board_json", no_fetch)
    result = anyio.run(discovery.observe_identity, identity)
    assert (result.state, result.reason, result.source_url) == (
        "unknown",
        "unsupported_identity",
        None,
    )


def test_upstream_failure_is_unknown(monkeypatch):
    def down(*args, **kwargs):
        raise discovery.DiscoveryError("private upstream error")

    monkeypatch.setattr(discovery, "fetch_board_json", down)
    result = anyio.run(discovery.observe_identity, GH)
    assert (result.state, result.reason) == ("unknown", "upstream_unavailable")
    assert "private" not in result.model_dump_json()


def test_malformed_and_oversize_response(monkeypatch):
    for content, reason in (
        ("{", "invalid_data"),
        (" " * (discovery.OBSERVATION_BYTES + 1), "incomplete_snapshot"),
    ):
        monkeypatch.setattr(
            discovery, "fetch_board_json", lambda *args, content=content, **kwargs: content
        )
        result = anyio.run(discovery.observe_identity, GH)
        assert (result.state, result.reason) == ("unknown", reason)
