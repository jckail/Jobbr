"""Regression tests for review findings: address policy, login flood, worker env, static paths."""

import asyncio
import ipaddress

import pytest
from fastapi.testclient import TestClient

from jobbr import config, db, resume
from jobbr.main import create_app
from jobbr.safefetch import is_public_address
from tests.test_resume import pdf_bytes


@pytest.mark.parametrize(
    "address",
    [
        "93.184.216.34",
        "8.8.8.8",
        "2606:4700:4700::1111",
        "64:ff9b::5db8:d822",  # NAT64 of 93.184.216.34
        "::ffff:93.184.216.34",
    ],
)
def test_public_addresses_allowed(address):
    assert is_public_address(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "::",
        "ff02::1",
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::127.0.0.1",  # deprecated IPv4-compatible
        "fec0::1",  # deprecated site-local
        "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        "64:ff9b::a9fe:a9fe",  # NAT64 of the cloud metadata service
        "64:ff9b:1::1",  # local-use NAT64
        "2002:7f00:1::",  # 6to4 of 127.0.0.1
    ],
)
def test_internal_addresses_blocked_however_wrapped(address):
    assert not is_public_address(ipaddress.ip_address(address))


def test_pdf_worker_does_not_inherit_secrets(env, monkeypatch):
    monkeypatch.setenv("JOBBR_OPENAI_API_KEY", "sk-must-not-leak")
    seen = {}
    original = asyncio.create_subprocess_exec

    async def spy(*args, **kwargs):
        seen.update(kwargs)
        return await original(*args, **kwargs)

    monkeypatch.setattr(resume.asyncio, "create_subprocess_exec", spy)
    asyncio.run(resume.parse_isolated(pdf_bytes()))
    assert seen["env"] == {}
    assert seen["close_fds"] is True


@pytest.mark.parametrize("path", ["%00", "a%00b.js", "x" * 5000])
def test_odd_static_paths_serve_the_app_not_a_500(env, tmp_path, path):
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>spa</html>")
    env.setenv("JOBBR_STATIC_DIR", str(static))
    config.get_settings.cache_clear()
    db.reset_engine()
    with TestClient(create_app()) as client:
        response = client.get(f"/jobbr/{path}")
    assert response.status_code == 200
    assert "spa" in response.text
