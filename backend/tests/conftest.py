import os

import pytest
from fastapi.testclient import TestClient

os.environ.update(JOBBR_DATABASE_URL="sqlite://", JOBBR_ALLOW_PRIVATE_FETCH="1", JOBBR_STATIC_DIR="/nonexistent")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBBR_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.delenv("JOBBR_ANTHROPIC_API_KEY", raising=False)
    from jobbr import config, db
    config.get_settings.cache_clear()
    db.reset_engine()
    from jobbr.main import create_app
    with TestClient(create_app()) as c:
        yield c
