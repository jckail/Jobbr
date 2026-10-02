"""Owner-approved PKCE capture grants, bounded metadata and paid-call idempotency."""

import base64
import hashlib
import json
import re
import secrets
import time
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from . import capture_repo as repo
from . import services
from .auth import ISSUER, AuthService, same_value
from .auth_models import AuthSession
from .auth_store import digest
from .capture_models import CaptureGrant, CapturePairing, CaptureReceipt
from .capture_schemas import ApproveIn, CaptureIn, ExchangeIn
from .config import Settings, get_settings
from .models import pk

PAIR_TTL = 300
GRANT_TTL = 900
MAX_ROWS = 128
PAIRINGS_PER_MINUTE = 32
ID_PATTERN = re.compile(r"[a-p]{32}\Z")


class CaptureError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


def timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def allowed_ids() -> set[str]:
    configured = get_settings().extension_allowed_ids
    values = {value.strip() for value in configured.split(",") if value.strip()}
    return values if values and all(ID_PATTERN.fullmatch(value) for value in values) else set()


def extension_origin(origin: str, extension_id: str) -> None:
    if extension_id not in allowed_ids():
        raise CaptureError(403, "This installed extension ID has not been reviewed by the owner.")
    if origin != "chrome-extension://" + extension_id:
        raise CaptureError(403, "Use the reviewed extension origin.")


def destination(auth: AuthService) -> str:
    auth.ensure_ready()
    return auth.settings.origin + auth.base


def policy(settings: Settings | None = None) -> tuple[str, str, bool]:
    settings = settings if settings is not None else get_settings()
    if not settings.ai_model or len(settings.ai_model) > 200:
        raise CaptureError(503, "The configured AI model is invalid.")
    return settings.ai_provider, settings.ai_model, settings.llm_enabled


def _live_session(s: Session, auth: AuthService, key: str, *, locked: bool = True) -> AuthSession:
    row = repo.session(s, key, locked=locked)
    if (
        row is None
        or row.expires_at <= time.time()
        or row.scope_hash != auth.scope
        or row.issuer != ISSUER
        or row.client_id != auth.settings.client_id
        or not same_value(row.subject, auth.settings.allowed_subject)
    ):
        raise CaptureError(401, "The approving website session ended. Connect again in Jobbr.")
    return row


def _pair_key(auth: AuthService, extension_id: str, challenge: str) -> str:
    return digest(extension_id + "\n" + challenge + "\n" + auth.scope)


def _pair(s: Session, auth: AuthService, extension_id: str, challenge: str) -> CapturePairing:
    row = repo.pairing(s, _pair_key(auth, extension_id, challenge))
    if row is None or row.scope_hash != auth.scope:
        raise CaptureError(404, "Extension pairing was not found.")
    if row.expires_at <= time.time():
        raise CaptureError(410, "Extension pairing expired. Start a new connection.")
    if row.extension_id not in allowed_ids():
        raise CaptureError(403, "This extension ID is no longer allowed.")
    if row.consumed:
        raise CaptureError(410, "This extension pairing has already been exchanged.")
    return row


def pairing_detail(
    s: Session, auth: AuthService, extension_id: str, challenge: str
) -> dict[str, Any]:
    if extension_id not in allowed_ids():
        raise CaptureError(403, "This installed extension ID has not been reviewed by the owner.")
    row = repo.pairing(s, _pair_key(auth, extension_id, challenge))
    if row is not None:
        row = _pair(s, auth, extension_id, challenge)
    provider, model, enabled = policy()
    return {
        "request_id": challenge,
        "extension_id": extension_id,
        "challenge": challenge,
        "destination": destination(auth),
        "comparison_code": digest(extension_id + "\n" + challenge)[:8].upper(),
        "expires_at": timestamp(row.expires_at) if row is not None else None,
        "status": "approved" if row is not None else "pending",
        "scope": "jobs:capture",
        "capture_limit": 5,
        "token_ttl_seconds": GRANT_TTL,
        "ai_provider": provider,
        "ai_model": model,
        "llm_enabled": enabled,
    }


def approve(s: Session, auth: AuthService, cookie: str, body: ApproveIn) -> dict[str, Any]:
    destination(auth)
    if body.extension_id not in allowed_ids():
        raise CaptureError(403, "This installed extension ID has not been reviewed by the owner.")
    throttle = repo.lock(s)
    now = time.time()
    repo.purge(s, now)
    if repo.pairing(s, _pair_key(auth, body.extension_id, body.challenge)) is not None:
        raise CaptureError(409, "This challenge was already approved. Start a new connection.")
    selected_policy = policy(get_settings().model_copy(deep=True))
    if (body.ai_provider, body.ai_model, body.llm_enabled) != selected_policy:
        raise CaptureError(409, "AI settings changed. Refresh and review before approving.")
    _live_session(s, auth, digest(cookie))
    if now - throttle.window_start >= 60:
        throttle.window_start, throttle.count = now, 0
    if throttle.count >= PAIRINGS_PER_MINUTE or repo.count(s, CapturePairing) >= MAX_ROWS:
        raise CaptureError(
            429, "Extension approvals are temporarily full. Wait before trying again."
        )
    throttle.count += 1
    s.add(throttle)
    provider, model, enabled = selected_policy
    row = CapturePairing(
        pairing_digest=_pair_key(auth, body.extension_id, body.challenge),
        extension_id=body.extension_id,
        challenge=body.challenge,
        comparison_code=digest(body.extension_id + "\n" + body.challenge)[:8].upper(),
        scope_hash=auth.scope,
        expires_at=now + PAIR_TTL,
        session_digest=digest(cookie),
        ai_provider=provider,
        ai_model=model,
        llm_enabled=enabled,
    )
    s.add(row)
    s.commit()
    return {
        "request_id": body.challenge,
        "status": "approved",
        "expires_at": timestamp(row.expires_at),
    }


def exchange(s: Session, auth: AuthService, body: ExchangeIn, origin: str) -> dict[str, Any]:
    destination(auth)
    extension_origin(origin, body.extension_id)
    row = _pair(s, auth, body.extension_id, body.challenge)
    if row.extension_id != body.extension_id:
        raise CaptureError(403, "Pairing belongs to a different extension.")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(body.verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    if not same_value(row.challenge, challenge):
        raise CaptureError(403, "Extension proof could not be verified.")
    # Unknown/incorrect proofs never acquire the shared capacity lock or mutate counters.
    s.rollback()
    repo.lock(s)
    row = _pair(s, auth, body.extension_id, body.challenge)
    if not same_value(row.challenge, challenge):
        raise CaptureError(403, "Extension proof could not be verified.")
    if row.session_digest is None:
        raise CaptureError(409, "Approve this connection in the signed-in Jobbr website first.")
    approving_session = _live_session(s, auth, row.session_digest)
    repo.purge(s, time.time())
    if repo.count(s, CaptureGrant) >= MAX_ROWS:
        raise CaptureError(429, "Extension authorizations are temporarily full.")
    raw = secrets.token_urlsafe(32)
    grant_id = secrets.token_urlsafe(32)
    expiry = min(time.time() + GRANT_TTL, approving_session.expires_at)
    grant = CaptureGrant(
        token_digest=digest(raw),
        grant_id=grant_id,
        extension_id=row.extension_id,
        session_digest=row.session_digest,
        scope_hash=auth.scope,
        ai_provider=row.ai_provider or "",
        ai_model=row.ai_model or "",
        llm_enabled=bool(row.llm_enabled),
        expires_at=expiry,
    )
    row.consumed = True  # Retained tombstone rejects replay and double approval for this challenge.
    s.add(row)
    s.add(grant)
    s.commit()
    return {
        "access_token": raw,
        "grant_id": grant_id,
        "token_type": "Bearer",
        "scope": "jobs:capture",
        "expires_at": timestamp(expiry),
    }


def _grant(
    s: Session, auth: AuthService, raw: str, extension_id: str, origin: str, *, locked: bool = True
) -> CaptureGrant:
    destination(auth)
    extension_origin(origin, extension_id)
    row = repo.grant(s, digest(raw))
    if (
        row is None
        or row.scope_hash != auth.scope
        or row.extension_id != extension_id
        or row.revoked
        or row.expires_at <= time.time()
    ):
        raise CaptureError(401, "Extension authorization ended. Connect again in Jobbr.")
    _live_session(s, auth, row.session_digest, locked=locked)
    return row


def capture(
    s: Session,
    auth: AuthService,
    raw: str,
    extension_id: str,
    origin: str,
    request_id: str,
    body: CaptureIn,
    selected: tuple[str | None, str | None, str | None],
) -> dict[str, int]:
    _grant(s, auth, raw, extension_id, origin, locked=False)
    s.rollback()
    repo.lock(s)
    grant = _grant(s, auth, raw, extension_id, origin)
    settings = get_settings().model_copy(deep=True)
    approved = (grant.ai_provider, grant.ai_model, "true" if grant.llm_enabled else "false")
    current = policy(settings)
    if selected != approved or (current[0], current[1], str(current[2]).lower()) != approved:
        raise CaptureError(409, "AI settings changed. Review and connect again before capturing.")
    input_hash = digest(
        json.dumps(body.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    )
    key = digest(request_id)
    previous = repo.receipt(s, grant.token_digest, key)
    if previous is not None:
        if previous.input_digest != input_hash:
            raise CaptureError(409, "This capture key belongs to a different preview.")
        if previous.status == "complete" and previous.job_id is not None:
            return {"id": previous.job_id}
        raise CaptureError(
            409, "This capture is pending or failed. Check Jobbr before another attempt."
        )
    if grant.busy:
        raise CaptureError(409, "One capture is already running for this authorization.")
    if grant.captures_remaining <= 0:
        raise CaptureError(401, "This authorization has used its five captures. Connect again.")
    token_hash = grant.token_digest
    grant.busy = True
    grant.captures_remaining -= 1
    s.add(grant)
    s.add(CaptureReceipt(token_digest=token_hash, request_digest=key, input_digest=input_hash))
    s.commit()  # Paid extraction starts only after durable duplicate reservation.
    try:
        job = services.ingest(s, body, settings=settings)
        job_id = pk(job)
    except BaseException:
        try:
            _finish(s, token_hash, key, None)
        except Exception:
            s.rollback()  # Pending receipt prevents retries; grant expires if cleanup fails.
        raise
    _finish(s, token_hash, key, job_id)
    return {"id": job_id}


def _finish(s: Session, token_hash: str, request_key: str, job_id: int | None) -> None:
    s.rollback()
    repo.lock(s)
    grant = repo.grant(s, token_hash)
    receipt = repo.receipt(s, token_hash, request_key)
    if grant is not None:
        grant.busy = False
        s.add(grant)
    if receipt is not None:
        receipt.status = "complete" if job_id is not None else "failed"
        receipt.job_id = job_id
        s.add(receipt)
    s.commit()


def grants(s: Session, auth: AuthService) -> list[dict[str, Any]]:
    base = destination(auth)
    return [
        {
            "grant_id": row.grant_id,
            "extension_id": row.extension_id,
            "destination": base,
            "expires_at": timestamp(row.expires_at),
            "captures_remaining": row.captures_remaining,
            "busy": row.busy,
            "revoked": row.revoked,
        }
        for row in repo.owner_grants(s, auth.scope, time.time())
    ]


def revoke(s: Session, auth: AuthService, grant_id: str) -> None:
    repo.lock(s)
    row = repo.public_grant(s, grant_id, auth.scope)
    if row is None:
        raise CaptureError(404, "Extension authorization was not found.")
    row.revoked = True
    s.add(row)
    s.commit()


def disconnect(s: Session, auth: AuthService, raw: str, extension_id: str, origin: str) -> None:
    _grant(s, auth, raw, extension_id, origin, locked=False)
    s.rollback()
    repo.lock(s)
    row = _grant(s, auth, raw, extension_id, origin)
    row.revoked = True
    s.add(row)
    s.commit()
