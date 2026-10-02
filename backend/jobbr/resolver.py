"""Deadline-bounded DNS in a killable, capped subprocess; no resolver threads."""

import ipaddress
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

MAX_ADDRESSES = 128
MAX_OUTPUT_BYTES = 8192
_slots = threading.BoundedSemaphore(4)
_WORKER = Path(__file__).resolve()


class ResolutionError(ValueError):
    """Fixed messages only: DNS diagnostics and hostnames are never returned."""


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ResolutionError("Page DNS resolution timed out.")
    return remaining


def resolve_addresses(host: str, port: int, deadline: float) -> list[str]:
    """Return every answer, or reject; timeout kills and reaps the worker."""
    _remaining(deadline)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [str(literal)]
    if not _slots.acquire(timeout=_remaining(deadline)):
        raise ResolutionError("Page DNS resolution is busy or timed out.")
    try:
        try:
            result = subprocess.run(  # noqa: S603 -- trusted script, no shell; host is only data
                [sys.executable, "-I", "-B", str(_WORKER), host, str(port)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={},
                timeout=_remaining(deadline),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.run kills and waits for its child before raising.
            raise ResolutionError("Page DNS resolution timed out.") from exc
        except OSError as exc:
            raise ResolutionError("Page DNS resolution failed.") from exc
        _remaining(deadline)
        if result.returncode or len(result.stdout) > MAX_OUTPUT_BYTES:
            raise ResolutionError("Page DNS resolution failed.")
        try:
            addresses = json.loads(result.stdout)
            if not isinstance(addresses, list) or not 1 <= len(addresses) <= MAX_ADDRESSES:
                raise ResolutionError("Invalid DNS answer set.")
            if any(not isinstance(address, str) or "%" in address for address in addresses):
                raise ResolutionError("Invalid DNS answer set.")
            return list(dict.fromkeys(str(ipaddress.ip_address(address)) for address in addresses))
        except (ValueError, TypeError, RecursionError) as exc:
            raise ResolutionError("Page DNS resolution failed.") from exc
    finally:
        _slots.release()


def _worker() -> None:
    if os.name == "posix":
        import resource  # noqa: PLC0415 -- worker-only POSIX limits

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (64 * 1024 * 1024, 64 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    try:
        host, port = sys.argv[1], int(sys.argv[2])
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = list(
            dict.fromkeys(str(ipaddress.ip_address(answer[4][0])) for answer in answers)
        )
        if not 1 <= len(addresses) <= MAX_ADDRESSES or any("%" in item for item in addresses):
            sys.exit(1)
        output = json.dumps(addresses)
        if len(output) > MAX_OUTPUT_BYTES:
            sys.exit(1)
        sys.stdout.write(output)
    except (ValueError, OSError, IndexError, MemoryError):
        sys.exit(1)


if __name__ == "__main__":
    _worker()
