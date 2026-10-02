"""Read-only public ATS board snapshots; no scraping, capture or application submission."""

import json
import re
import time
from datetime import UTC, datetime
from functools import partial
from html import unescape
from typing import Annotated, Literal
from urllib.parse import urlsplit

import anyio
import httpcore
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import safefetch
from .api import require_access
from .canonical import Identity, identity_for_url
from .config import get_settings
from .parsing import html_to_text

Provider = Literal["greenhouse", "lever"]
Remote = Literal["remote", "hybrid", "onsite", "unknown"]
MAX_RESULTS = 100
TEXT_CAP = 20_000
BOARD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")
WORKPLACE_MAP: dict[str, Remote] = {"remote": "remote", "hybrid": "hybrid", "on-site": "onsite"}
HOSTS = {"greenhouse": "boards-api.greenhouse.io", "lever": "api.lever.co"}
LINK_HOSTS = {
    "greenhouse": {"boards.greenhouse.io", "job-boards.greenhouse.io"},
    "lever": {"jobs.lever.co"},
}
router = APIRouter(prefix="/api/discovery", dependencies=[Depends(require_access)])


class DiscoveryError(RuntimeError):
    """Public board data unavailable or not safe to present."""


class DiscoveryPosting(BaseModel):
    source_id: str
    title: str
    company: str | None
    location: str | None
    url: str
    raw_text: str
    remote_policy: Remote = "unknown"


class DiscoverySnapshot(BaseModel):
    provider: Provider
    board: str
    source_url: str
    fetched_at: datetime
    postings: list[DiscoveryPosting]
    truncated: bool
    skipped_unsafe_links: int = 0


class _Location(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str | None = None


class _GreenhousePosting(BaseModel):
    model_config = ConfigDict(strict=True)
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=500)
    absolute_url: str
    location: _Location = Field(default_factory=_Location)
    content: str = ""
    company_name: str | None = None


class _LeverCategories(BaseModel):
    model_config = ConfigDict(strict=True)
    location: str | None = None


class _LeverList(BaseModel):
    model_config = ConfigDict(strict=True)
    text: str = ""
    content: str = ""


class _LeverPosting(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=500)
    hostedUrl: str
    categories: _LeverCategories = Field(default_factory=_LeverCategories)
    descriptionPlain: str = ""
    additionalPlain: str = ""
    lists: list[_LeverList] = Field(default_factory=list)
    workplaceType: str | None = None


def board_endpoint(provider: Provider, board: str) -> str:
    if provider not in HOSTS or not BOARD_PATTERN.fullmatch(board):
        raise ValueError("Choose Greenhouse or Lever and a valid board token.")
    if provider == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    return f"https://api.lever.co/v0/postings/{board}?mode=json&limit=100"


def fetch_board_json(endpoint: str, *, deadline: float | None = None) -> str:
    """Use hardened fetch primitives with no redirects outside the exact vendor endpoint."""
    board_pattern = r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}"
    allowed = (
        rf"https://boards-api\.greenhouse\.io/v1/boards/{board_pattern}/jobs\?content=true",
        rf"https://api\.lever\.co/v0/postings/{board_pattern}\?mode=json&limit=100",
    )
    if not any(re.fullmatch(pattern, endpoint) for pattern in allowed):
        raise DiscoveryError("Unsupported discovery endpoint.")
    deadline = (
        deadline if deadline is not None else time.monotonic() + get_settings().fetch_timeout_s
    )
    try:
        parsed, address = safefetch._resolve_url(endpoint, deadline)
        with (
            httpx.Client(
                transport=safefetch._PinnedTransport(parsed, address, deadline),
                trust_env=False,
                timeout=safefetch._remaining(deadline),
                follow_redirects=False,
                headers={
                    "User-Agent": safefetch.UA,
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            ) as client,
            client.stream("GET", parsed) as response,
        ):
            if not 200 <= response.status_code < 300:
                raise DiscoveryError(
                    "The public board is unavailable; verify its provider and token."
                )
            return safefetch._read_page(response, deadline)
    except (
        safefetch.FetchError,
        httpx.HTTPError,
        httpcore.NetworkError,
        httpcore.TimeoutException,
        httpcore.ProtocolError,
        OSError,
        ValueError,
    ) as exc:
        raise DiscoveryError(
            "The public board could not be fetched safely; try again later."
        ) from exc


def _safe_link(value: str, provider: Provider, board: str, source_id: str) -> str | None:
    if len(value) > safefetch.MAX_URL_CHARS or any(ord(char) < 33 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in LINK_HOSTS[provider]
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            return None
        expected = (
            f"/{board}/jobs/{source_id}" if provider == "greenhouse" else f"/{board}/{source_id}"
        )
        if parsed.path.rstrip("/") != expected:
            return None
    except (ValueError, UnicodeError):
        return None
    return value


def _normalize(
    rows: list[object], provider: Provider, board: str
) -> tuple[list[DiscoveryPosting], int]:
    postings = []
    skipped = 0
    seen: set[str] = set()
    for raw in rows[:MAX_RESULTS]:
        if provider == "greenhouse":
            row = _GreenhousePosting.model_validate(raw)
            source_id, title, location = str(row.id), row.title, row.location.name
            link = _safe_link(row.absolute_url, provider, board, source_id)
            text = html_to_text(unescape(row.content))[:TEXT_CAP]
            company = row.company_name
            remote: Remote = "unknown"  # location labels aren't a verified workplace policy
        else:
            lever = _LeverPosting.model_validate(raw)
            if not ID_PATTERN.fullmatch(lever.id):
                raise DiscoveryError("The public board returned invalid posting identifiers.")
            source_id, title, location = lever.id, lever.text, lever.categories.location
            link = _safe_link(lever.hostedUrl, provider, board, source_id)
            parts = [lever.descriptionPlain]
            parts.extend(f"{item.text}\n{html_to_text(item.content)}" for item in lever.lists)
            parts.append(lever.additionalPlain)
            text = "\n\n".join(part for part in parts if part)[:TEXT_CAP]
            company = None  # API supplies a board identifier, not a verified legal company name
            remote = WORKPLACE_MAP.get(lever.workplaceType or "", "unknown")
        if not title.strip():
            raise DiscoveryError("The public board returned an empty posting title.")
        if link is None:
            skipped += 1
            continue
        if source_id in seen:
            continue
        seen.add(source_id)
        postings.append(
            DiscoveryPosting(
                source_id=source_id,
                title=title.strip(),
                company=company,
                location=location,
                url=link,
                raw_text=text,
                remote_policy=remote,
            )
        )
    return postings, skipped


def discover(
    provider: Provider, board: str, q: str | None = None, remote: Remote | None = None
) -> DiscoverySnapshot:
    endpoint = board_endpoint(provider, board)
    content = fetch_board_json(endpoint)
    try:
        payload = json.loads(content)
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if provider == "lever":
            rows = payload
        if not isinstance(rows, list):
            raise DiscoveryError("The public board returned an unsupported response.")
        postings, skipped = _normalize(rows, provider, board)
    except (json.JSONDecodeError, ValidationError, RecursionError) as exc:
        raise DiscoveryError("The public board returned invalid posting data.") from exc
    query = (q or "").strip().casefold()
    postings = [
        posting
        for posting in postings
        if (
            not query
            or query in f"{posting.title} {posting.location or ''} {posting.raw_text}".casefold()
        )
        and (remote is None or posting.remote_policy == remote)
    ]
    return DiscoverySnapshot(
        provider=provider,
        board=board,
        source_url=endpoint,
        fetched_at=datetime.now(UTC),
        postings=postings,
        truncated=len(rows) >= MAX_RESULTS,
        skipped_unsafe_links=skipped,
    )


@router.get("/boards/{provider}/{board}")
def board_postings(
    provider: Provider,
    board: str,
    q: Annotated[str | None, Query(max_length=200)] = None,
    remote: Literal["remote", "hybrid", "onsite", "unknown"] | None = None,
) -> DiscoverySnapshot:
    try:
        return discover(provider, board, q, remote)
    except ValueError as exc:
        raise HTTPException(422, "Choose a valid board token, not a URL.") from exc
    except DiscoveryError as exc:
        raise HTTPException(502, str(exc)) from exc


AvailabilityReason = Literal[
    "listed",
    "absent_complete_board",
    "incomplete_snapshot",
    "upstream_unavailable",
    "invalid_data",
    "unsupported_identity",
]


class AvailabilityObservation(BaseModel):
    state: Literal["available", "unavailable", "unknown"]
    checked_at: datetime
    source_url: str | None
    reason: AvailabilityReason


# Bounded offload, shared across requests. Workers are never abandoned on cancellation;
# the pinned fetch and subprocess DNS resolver enforce the original monotonic deadline.
_OBSERVATION_LIMITER = anyio.CapacityLimiter(4)
OBSERVATION_BYTES = 1024 * 1024


def _observation(
    state: Literal["available", "unavailable", "unknown"],
    reason: AvailabilityReason,
    source_url: str | None,
) -> AvailabilityObservation:
    return AvailabilityObservation(
        state=state, reason=reason, source_url=source_url, checked_at=datetime.now(UTC)
    )


def _availability_rows(payload: object, provider: Provider) -> list[object]:
    rows = (
        payload
        if provider == "lever"
        else payload.get("jobs")
        if isinstance(payload, dict)
        else None
    )
    if not isinstance(rows, list):
        raise TypeError("Unsupported board payload")
    return rows


def _classify_availability(
    content: str, identity: Identity, endpoint: str
) -> AvailabilityObservation:
    try:
        if len(content.encode("utf-8")) > OBSERVATION_BYTES:
            return _observation("unknown", "incomplete_snapshot", endpoint)
        payload = json.loads(content)
        rows = _availability_rows(payload, identity.provider)
        truncated = len(rows) > MAX_RESULTS
        seen: set[str] = set()
        found = False
        for raw in rows[:MAX_RESULTS]:
            if identity.provider == "greenhouse":
                row = _GreenhousePosting.model_validate(raw)
                source_id, url, title = str(row.id), row.absolute_url, row.title
            else:
                lever = _LeverPosting.model_validate(raw)
                source_id, url, title = lever.id, lever.hostedUrl, lever.text
            expected = Identity(identity.provider, identity.board, source_id)
            if not title.strip() or identity_for_url(url) != expected or source_id in seen:
                return _observation("unknown", "invalid_data", endpoint)
            seen.add(source_id)
            found = found or expected == identity
        if found:
            return _observation("available", "listed", endpoint)
        # Official Greenhouse Job Board API returns all posts and meta.total:
        # https://docs.greenhouse.io/job-board.html#get-list-jobs
        # Require matching explicit total, not merely a short local result window.
        if identity.provider == "greenhouse" and isinstance(payload, dict):
            meta = payload.get("meta")
            total = meta.get("total") if isinstance(meta, dict) else None
            if not truncated and type(total) is int and total >= 0 and total == len(rows):
                return _observation("unavailable", "absent_complete_board", endpoint)
        # Lever documents limit as "at most N", without an explicit total/completion
        # marker: https://github.com/lever/postings-api#get-a-list-of-job-postings
        # A short or empty response alone therefore never proves absence here.
        return _observation("unknown", "incomplete_snapshot", endpoint)
    except (TypeError, ValueError, ValidationError, RecursionError, UnicodeError, OverflowError):
        return _observation("unknown", "invalid_data", endpoint)


async def observe_identity(identity: Identity | None) -> AvailabilityObservation:
    """Observe public listing membership, without capture, profile reads or paid calls."""
    if identity is None:
        return _observation("unknown", "unsupported_identity", None)
    path = (
        f"/{identity.board}/jobs/{identity.posting_id}"
        if identity.provider == "greenhouse"
        else f"/{identity.board}/{identity.posting_id}"
    )
    host = "boards.greenhouse.io" if identity.provider == "greenhouse" else "jobs.lever.co"
    if identity_for_url("https://" + host + path) != identity:
        return _observation("unknown", "unsupported_identity", None)
    try:
        endpoint = board_endpoint(identity.provider, identity.board)
    except ValueError:
        return _observation("unknown", "unsupported_identity", None)
    timeout = get_settings().fetch_timeout_s
    deadline = time.monotonic() + timeout
    try:
        with anyio.fail_after(timeout):
            content = await anyio.to_thread.run_sync(
                partial(fetch_board_json, endpoint, deadline=deadline),
                limiter=_OBSERVATION_LIMITER,
                abandon_on_cancel=False,
            )
    except (DiscoveryError, TimeoutError):
        return _observation("unknown", "upstream_unavailable", endpoint)
    return _classify_availability(content, identity, endpoint)
