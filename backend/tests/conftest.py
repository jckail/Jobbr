import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JOBBR_STATIC_DIR", "/nonexistent")

from jobbr import config, db
from jobbr.main import create_app

API = "/jobbr/api"

ARTICLE = """<html><head><script type="application/ld+json">
{"@type":"JobPosting","title":"Senior Data Engineer","hiringOrganization":{"name":"Acme"},
 "description":"<p>Build pipelines</p><ul><li>Own Airflow DAGs</li></ul> Python, SQL and Kafka.",
 "jobLocationType":"TELECOMMUTE",
 "baseSalary":{"currency":"USD","value":{"minValue":90,"maxValue":120,"unitText":"HOUR"}},
 "datePosted":"2026-09-01"}</script></head>
<body><main>Senior Data Engineer at Acme. Remote. Python SQL Kafka pipelines every day for our
platform team.</main></body></html>"""


def reset_settings() -> None:
    config.get_settings.cache_clear()
    db.reset_engine()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> pytest.MonkeyPatch:
    """Isolated settings: fresh SQLite file, no API key, private fetch allowed."""
    monkeypatch.setenv("JOBBR_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("JOBBR_ALLOW_PRIVATE_FETCH", "1")
    for var in ("JOBBR_ANTHROPIC_API_KEY", "JOBBR_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    reset_settings()
    yield monkeypatch
    reset_settings()


@pytest.fixture
def client(env: pytest.MonkeyPatch) -> Iterator[TestClient]:
    env.setattr("jobbr.services.fetch_html", lambda url: (url, ARTICLE))
    with TestClient(create_app()) as c:
        yield c
