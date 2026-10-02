"""Additive external identity and bounded transient capture coordination metadata."""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class JobExternalIdentity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("provider", "board", "posting_id"),)
    id: int | None = Field(default=None, primary_key=True)
    provider: str
    board: str
    posting_id: str
    job_id: int = Field(foreign_key="job.id", index=True)


class CaptureLease(SQLModel, table=True):
    resource_key: str = Field(primary_key=True)
    nonce: str
    expires_at: float = Field(index=True)
    job_id: int | None = Field(default=None, foreign_key="job.id", index=True)
    job_baseline: str | None = None
