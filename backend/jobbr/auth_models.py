"""Shared auth persistence; bearer cookies are never stored in their raw form."""

from sqlalchemy import Column, String, Text
from sqlmodel import Field, SQLModel


class AuthTransaction(SQLModel, table=True):
    token_digest: str = Field(sa_column=Column(String(64), primary_key=True))
    state_digest: str = Field(sa_column=Column(String(64), nullable=False))
    scope_hash: str = Field(sa_column=Column(String(64), nullable=False))
    encrypted_payload: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: float = Field(index=True)


class AuthSession(SQLModel, table=True):
    token_digest: str = Field(sa_column=Column(String(64), primary_key=True))
    scope_hash: str = Field(sa_column=Column(String(64), nullable=False))
    issuer: str = Field(sa_column=Column(String(200), nullable=False))
    client_id: str = Field(sa_column=Column(String(300), nullable=False))
    subject: str = Field(sa_column=Column(String(300), nullable=False))
    name: str | None = Field(default=None, sa_column=Column(String(300), nullable=True))
    email: str | None = Field(default=None, sa_column=Column(String(320), nullable=True))
    expires_at: float = Field(index=True)


class AuthStoreGuard(SQLModel, table=True):
    # Migration inserts the single guard; all instances lock this same row for capacity checks.
    id: int = Field(primary_key=True)
