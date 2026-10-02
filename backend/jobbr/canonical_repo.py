"""Owner-lock-protected identity adoption and fenced capture lease queries.

Callers own locking, commit/rollback and conflict-to-HTTP translation. These
helpers never hold transactions open for provider work or automatically retry.
"""

import time

from sqlalchemy import delete, func, or_
from sqlmodel import Session, col, select

from .canonical import Identity, identity_for_url, job_baseline
from .canonical_models import CaptureLease, JobExternalIdentity
from .models import Job, pk

MAX_LEASES = 128
LEASE_TTL = 300
LEGACY_SCAN_LIMIT = 1000


class CanonicalConflict(Exception):
    """Capture needs explicit review or a later user-initiated attempt."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def mapping(s: Session, identity: Identity) -> JobExternalIdentity | None:
    return s.exec(
        select(JobExternalIdentity)
        .where(
            JobExternalIdentity.provider == identity.provider,
            JobExternalIdentity.board == identity.board,
            JobExternalIdentity.posting_id == identity.posting_id,
        )
        .execution_options(populate_existing=True)
    ).first()


def bind_identity(s: Session, identity: Identity, job_id: int) -> None:
    existing = mapping(s, identity)
    if existing:
        if existing.job_id != job_id:
            raise CanonicalConflict("This posting identity already belongs to another saved job.")
        return
    s.add(
        JobExternalIdentity(
            provider=identity.provider,
            board=identity.board,
            posting_id=identity.posting_id,
            job_id=job_id,
        )
    )
    s.flush()


def resolve_identity(
    s: Session, identity: Identity, *, scan_limit: int = LEGACY_SCAN_LIMIT
) -> Job | None:
    if not 1 <= scan_limit <= LEGACY_SCAN_LIMIT:
        raise ValueError("Legacy scan limit must be bounded between 1 and 1000.")
    existing = mapping(s, identity)
    if existing:
        return existing_job(s, existing.job_id)
    # Coarse lowercase SQL filtering covers only this posting's exact path.
    # The parser below still enforces case-sensitive board and posting IDs.
    hosts = (
        ["boards.greenhouse.io", "job-boards.greenhouse.io"]
        if identity.provider == "greenhouse"
        else ["jobs.lever.co"]
    )
    path = (
        f"/{identity.board}/"
        + ("jobs/" if identity.provider == "greenhouse" else "")
        + identity.posting_id
    )
    prefixes = [f"https://{host}{port}{path}".lower() for host in hosts for port in ("", ":443")]
    lower_url = func.lower(col(Job.url))
    candidates = s.exec(
        select(col(Job.id), col(Job.url))
        .where(
            or_(
                *(
                    condition
                    for prefix in prefixes
                    for condition in (
                        lower_url == prefix,
                        lower_url.startswith(prefix + "?", autoescape=True),
                        lower_url.startswith(prefix + "#", autoescape=True),
                    )
                )
            )
        )
        .order_by(col(Job.id))
        .limit(scan_limit + 1)
        .execution_options(populate_existing=True)
    ).all()
    if len(candidates) > scan_limit:
        raise CanonicalConflict(
            "Legacy posting lookup is too large. Review existing jobs before capture."
        )
    matches = [job_id for job_id, url in candidates if identity_for_url(url) == identity]
    if len(matches) > 1:
        raise CanonicalConflict(
            "Multiple saved jobs match this posting. Review them before capture."
        )
    if not matches:
        return None
    job_id = matches[0]
    if job_id is None:
        raise RuntimeError("Saved posting identity requires a persisted job.")
    job = existing_job(s, job_id)
    if job is None or identity_for_url(job.url) != identity:
        raise CanonicalConflict(
            "The saved posting changed during lookup. Review it before capture."
        )
    bind_identity(s, identity, job_id)
    return job


def lease(s: Session, key: str) -> CaptureLease | None:
    return s.get(CaptureLease, key, populate_existing=True)


def reserve(
    s: Session,
    key: str,
    nonce: str,
    expires_at: float,
    job_id: int | None,
    baseline: str | None,
    *,
    now: float | None = None,
) -> CaptureLease:
    now = time.time() if now is None else now
    if expires_at <= now or expires_at > now + LEASE_TTL:
        raise ValueError("Capture lease deadline must be within the bounded lifetime.")
    current = lease(s, key)
    if current is not None and current.expires_at > now:
        raise CanonicalConflict(
            "This posting is already being captured. Wait before trying again.",
            max(1, int(current.expires_at - now)),
        )
    s.execute(delete(CaptureLease).where(col(CaptureLease.expires_at) <= now))
    if s.exec(select(func.count()).select_from(CaptureLease)).one() >= MAX_LEASES:
        raise CanonicalConflict("Capture reservations are temporarily full. Try again later.", 5)
    row = CaptureLease(
        resource_key=key, nonce=nonce, expires_at=expires_at, job_id=job_id, job_baseline=baseline
    )
    s.add(row)
    s.flush()
    return row


def check(s: Session, key: str, nonce: str, *, now: float | None = None) -> CaptureLease:
    row = lease(s, key)
    now = time.time() if now is None else now
    if row is None or row.nonce != nonce or row.expires_at <= now:
        raise CanonicalConflict(
            "Capture reservation expired or changed. Review Jobbr before retrying."
        )
    if row.job_id is not None:
        job = existing_job(s, row.job_id)
        if job is None or job_baseline(job) != row.job_baseline:
            raise CanonicalConflict(
                "The saved posting changed during capture. Review it before retrying."
            )
    return row


def release(s: Session, key: str, nonce: str) -> bool:
    row = lease(s, key)
    if row is None or row.nonce != nonce:
        return False
    s.delete(row)
    s.flush()
    return True


def delete_job_refs(s: Session, job_id: int) -> None:
    s.execute(delete(CaptureLease).where(col(CaptureLease.job_id) == job_id))
    s.execute(delete(JobExternalIdentity).where(col(JobExternalIdentity.job_id) == job_id))


def exact_job(s: Session, url: str) -> Job | None:
    matches = s.exec(
        select(Job).where(Job.url == url).limit(2).execution_options(populate_existing=True)
    ).all()
    if len(matches) > 1:
        raise CanonicalConflict("Multiple saved jobs use this URL. Review them before capture.")
    return existing_job(s, pk(matches[0])) if matches else None


def attach_identity(s: Session, identity: Identity, job: Job) -> None:
    bind_identity(s, identity, pk(job))


def existing_job(s: Session, job_id: int) -> Job | None:
    return s.exec(
        select(Job)
        .where(col(Job.id) == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def saved_identity(s: Session, job: Job) -> Identity | None:
    """Read server-owned identity without adopting rows or taking write locks."""
    rows = s.exec(
        select(JobExternalIdentity)
        .where(JobExternalIdentity.job_id == pk(job))
        .order_by(col(JobExternalIdentity.id))
        .limit(2)
    ).all()
    if not rows:
        return identity_for_url(job.url)
    if len(rows) != 1:
        return None  # Conflicting mappings cannot assert a posting's availability.
    row = rows[0]
    if row.provider == "greenhouse":
        return Identity("greenhouse", row.board, row.posting_id)
    if row.provider == "lever":
        return Identity("lever", row.board, row.posting_id)
    return None
