"""Extension metadata queries and shared transactional capacity serialization."""

from sqlalchemy import delete, func, or_, update
from sqlmodel import Session, col, select

from .auth_models import AuthSession
from .capture_models import CaptureGrant, CapturePairing, CaptureReceipt, CaptureThrottle


def lock(s: Session) -> CaptureThrottle:
    s.execute(update(CaptureThrottle).where(col(CaptureThrottle.id) == 1).values(id=1))
    row = s.get(CaptureThrottle, 1)
    if row is None:
        raise RuntimeError("Extension authorization migration is required.")
    s.refresh(row)
    return row


def purge(s: Session, now: float) -> None:
    # Allow bounded in-flight completion after expiry; dead workers cannot retain rows forever.
    condition = (col(CaptureGrant.expires_at) <= now) & or_(
        col(CaptureGrant.busy).is_(False), col(CaptureGrant.expires_at) <= now - 600
    )
    expired = select(CaptureGrant.token_digest).where(condition)
    s.execute(delete(CaptureReceipt).where(col(CaptureReceipt.token_digest).in_(expired)))
    s.execute(delete(CaptureGrant).where(condition))
    s.execute(delete(CapturePairing).where(col(CapturePairing.expires_at) <= now))


def pairing(s: Session, key: str) -> CapturePairing | None:
    row = s.get(CapturePairing, key)
    if row is not None:
        s.refresh(row)
    return row


def grant(s: Session, key: str) -> CaptureGrant | None:
    row = s.get(CaptureGrant, key)
    if row is not None:
        s.refresh(row)
    return row


def session(s: Session, key: str, *, locked: bool = True) -> AuthSession | None:
    # Logout deletion cannot finish before a concurrently validated reservation commits.
    query = select(AuthSession).where(AuthSession.token_digest == key)
    if locked:
        query = query.with_for_update()
    return s.exec(query.execution_options(populate_existing=True)).first()


def count(s: Session, model: type[CapturePairing] | type[CaptureGrant]) -> int:
    return s.exec(select(func.count()).select_from(model)).one()


def receipt(s: Session, key: str, request_key: str) -> CaptureReceipt | None:
    row = s.get(CaptureReceipt, (key, request_key))
    if row is not None:
        s.refresh(row)
    return row


def owner_grants(s: Session, scope: str, now: float) -> list[CaptureGrant]:
    return list(
        s.exec(
            select(CaptureGrant)
            .where(CaptureGrant.scope_hash == scope, CaptureGrant.expires_at > now)
            .order_by(col(CaptureGrant.expires_at).desc())
        ).all()
    )


def public_grant(s: Session, grant_id: str, scope: str) -> CaptureGrant | None:
    return s.exec(
        select(CaptureGrant).where(
            CaptureGrant.grant_id == grant_id, CaptureGrant.scope_hash == scope
        )
    ).first()
