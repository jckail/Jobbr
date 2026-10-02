import ipaddress
import json
import os
import subprocess
import threading
import time

import pytest

from jobbr import resolver, safefetch


def completed(addresses, code=0):
    return subprocess.CompletedProcess([], code, json.dumps(addresses).encode())


def test_localhost_worker_lookup_returns_loopback_addresses():
    addresses = resolver.resolve_addresses("localhost", 443, time.monotonic() + 5)
    assert addresses
    assert all(ipaddress.ip_address(address).is_loopback for address in addresses)


@pytest.mark.parametrize("host", ["93.184.216.34", "2001:4860:4860::8888"])
def test_literal_addresses_skip_worker(monkeypatch, host):
    monkeypatch.setattr(resolver.subprocess, "run", lambda *a, **kw: pytest.fail("Worker started"))
    assert resolver.resolve_addresses(host, 443, time.monotonic() + 1) == [host]


def test_worker_receives_only_hostname_and_minimal_environment(monkeypatch):
    def run(command, **kwargs):
        assert command[-2:] == ["example.invalid", "443"]
        assert command[1:3] == ["-I", "-B"]
        assert kwargs["env"] == {}
        assert kwargs["stdin"] == kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["stdout"] == subprocess.PIPE
        assert 0 < kwargs["timeout"] <= 1
        return completed(["93.184.216.34", "93.184.216.34", "2001:4860:4860::8888"])

    monkeypatch.setattr(resolver.subprocess, "run", run)
    assert resolver.resolve_addresses("example.invalid", 443, time.monotonic() + 1) == [
        "93.184.216.34",
        "2001:4860:4860::8888",
    ]


@pytest.mark.parametrize(
    "output",
    [
        [],
        ["not-an-ip"],
        ["fe80::1%eth0"],
        [123],
        {"address": "93.184.216.34"},
        ["93.184.216.34"] * (resolver.MAX_ADDRESSES + 1),
    ],
)
def test_bad_worker_answers_rejected_and_slot_released(monkeypatch, output):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(resolver, "_slots", slots)
    monkeypatch.setattr(resolver.subprocess, "run", lambda *a, **kw: completed(output))
    with pytest.raises(resolver.ResolutionError, match="failed"):
        resolver.resolve_addresses("example.invalid", 443, time.monotonic() + 1)
    assert slots.acquire(blocking=False)
    slots.release()


@pytest.mark.parametrize(
    "failure", [OSError("sensitive diagnostic"), subprocess.TimeoutExpired("secret", 1)]
)
def test_worker_failure_is_sanitized_and_slot_released(monkeypatch, failure):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(resolver, "_slots", slots)

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(resolver.subprocess, "run", fail)
    with pytest.raises(resolver.ResolutionError) as error:
        resolver.resolve_addresses("example.invalid", 443, time.monotonic() + 1)
    assert "sensitive" not in str(error.value)
    assert "secret" not in str(error.value)
    assert slots.acquire(blocking=False)
    slots.release()


def test_four_worker_slots_bound_concurrency_and_wait_budget(monkeypatch):
    slots = threading.BoundedSemaphore(4)
    monkeypatch.setattr(resolver, "_slots", slots)
    for _ in range(4):
        assert slots.acquire(blocking=False)
    monkeypatch.setattr(
        resolver.subprocess, "run", lambda *a, **kw: pytest.fail("Fifth worker started")
    )
    started = time.monotonic()
    try:
        with pytest.raises(resolver.ResolutionError, match="busy or timed out"):
            resolver.resolve_addresses("example.invalid", 443, started + 0.05)
    finally:
        for _ in range(4):
            slots.release()
    assert time.monotonic() - started < 1


@pytest.mark.skipif(os.name != "posix", reason="POSIX child termination return code")
def test_timed_out_worker_is_killed_and_reaped(monkeypatch, tmp_path):
    worker = tmp_path / "slow_resolver.py"
    worker.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(resolver, "_WORKER", worker)
    real_popen = subprocess.Popen
    processes = []

    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(resolver.subprocess, "Popen", popen)
    started = time.monotonic()
    with pytest.raises(resolver.ResolutionError, match="timed out"):
        resolver.resolve_addresses("example.invalid", 443, started + 0.2)
    assert len(processes) == 1
    assert processes[0].returncode is not None
    assert processes[0].returncode < 0
    assert time.monotonic() - started < 2


def test_resolution_finishing_after_deadline_is_rejected(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(resolver.time, "monotonic", lambda: clock[0])

    def run(*args, **kwargs):
        clock[0] = 2.0
        return completed(["93.184.216.34"])

    monkeypatch.setattr(resolver.subprocess, "run", run)
    with pytest.raises(resolver.ResolutionError, match="timed out"):
        resolver.resolve_addresses("example.invalid", 443, 1.0)


def test_fetch_preserves_dns_timeout_message(monkeypatch):
    def fail(*args, **kwargs):
        raise resolver.ResolutionError("Page DNS resolution timed out.")

    monkeypatch.setattr(safefetch, "resolve_addresses", fail)
    with pytest.raises(safefetch.FetchError, match="DNS resolution timed out"):
        safefetch._resolve_url("https://example.invalid/", time.monotonic() + 1)
