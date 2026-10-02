"""Server-derived ATS identity and metadata-only capture fingerprints."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from .models import Job


@dataclass(frozen=True)
class Identity:
    provider: Literal["greenhouse", "lever"]
    board: str
    posting_id: str


def identity_for_url(url: str | None) -> Identity | None:
    if not url or len(url) > 8192 or "\\" in url or any(ord(c) < 33 or ord(c) == 127 for c in url):
        return None
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
        host = parsed.hostname
    except ValueError:
        return None
    if not valid or parsed.netloc.lower() not in {host, f"{host}:443"}:
        return None
    # Encoded separators, dot segments and multiple spellings must not assert equivalence.
    if "%" not in parsed.path and host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        match = re.fullmatch(r"/([A-Za-z0-9_-]{1,80})/jobs/([0-9]{1,32})", parsed.path)
        if match:
            return Identity("greenhouse", match[1], match[2])
    if "%" not in parsed.path and host == "jobs.lever.co":
        match = re.fullmatch(
            r"/([A-Za-z0-9_-]{1,80})/([A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-"
            r"[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12})",
            parsed.path,
        )
        if match:
            return Identity("lever", match[1], match[2])
    return None


def resource_key(url: str | None, identity: Identity | None = None) -> str | None:
    """Unsupported URLs retain exact identity; text-only requests do not coalesce."""
    if not url:
        return None
    identity = identity if identity is not None else identity_for_url(url)
    value = (
        ["ats", identity.provider, identity.board, identity.posting_id]
        if identity
        else ["url", url]
    )
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def job_baseline(job: Job) -> str:
    """Fence every stored job field; application and private drafts are never hashed."""
    value = json.dumps(job.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()
