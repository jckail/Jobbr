"""Metadata-only extension authorizations; raw capabilities never enter the database."""

from sqlmodel import Field, SQLModel


class CapturePairing(SQLModel, table=True):
    pairing_digest: str = Field(primary_key=True)
    extension_id: str
    challenge: str
    comparison_code: str
    scope_hash: str
    expires_at: float = Field(index=True)
    session_digest: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    llm_enabled: bool | None = None
    consumed: bool = False


class CaptureGrant(SQLModel, table=True):
    token_digest: str = Field(primary_key=True)
    grant_id: str = Field(index=True, unique=True)
    extension_id: str
    session_digest: str
    scope_hash: str
    ai_provider: str
    ai_model: str
    llm_enabled: bool
    expires_at: float = Field(index=True)
    captures_remaining: int = 5
    busy: bool = False
    revoked: bool = False


class CaptureReceipt(SQLModel, table=True):
    token_digest: str = Field(foreign_key="capturegrant.token_digest", primary_key=True)
    request_digest: str = Field(primary_key=True)
    input_digest: str
    status: str = "pending"
    job_id: int | None = None


class CaptureThrottle(SQLModel, table=True):
    id: int = Field(primary_key=True)
    window_start: float = 0
    count: int = 0
