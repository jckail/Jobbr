import logging

from fastapi.testclient import TestClient
from sqlalchemy.exc import StatementError

from jobbr.main import create_app


def test_unhandled_database_error_does_not_log_private_parameters(env, caplog):
    private_resume = "PRIVATE_RESUME_SENTINEL_8b9b72"

    def fail(_session):
        raise StatementError(
            "database rejected input",
            "INSERT INTO profile",
            {"resume_text": private_resume},
            ValueError("bad input"),
        )

    env.setattr("jobbr.services.get_profile", fail)
    with (
        caplog.at_level(logging.ERROR, logger="jobbr"),
        TestClient(create_app(), raise_server_exceptions=False) as client,
    ):
        response = client.get("/jobbr/api/profile")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal error"}
    assert "StatementError" in caplog.text
    assert private_resume not in caplog.text
    assert private_resume not in response.text
