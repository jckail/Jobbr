"""Durable auth store with atomic consumption and shared capacity limits."""

import base64
import hashlib
import hmac
import json
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Connection, Engine, Table, delete, func, insert, select, text
from sqlalchemy.exc import SQLAlchemyError

from .auth_models import AuthSession, AuthStoreGuard, AuthTransaction

TRANSACTIONS = AuthTransaction.__table__  # type: ignore[attr-defined]
SESSIONS = AuthSession.__table__  # type: ignore[attr-defined]
GUARDS = AuthStoreGuard.__table__  # type: ignore[attr-defined]
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


@dataclass(frozen=True)
class Transaction:
    state: str
    verifier: str
    nonce: str
    expires_at: float


@dataclass(frozen=True)
class SessionRecord:
    issuer: str
    client_id: str
    subject: str
    name: str | None
    email: str | None
    csrf_token: str
    expires_at: float

    def user(self) -> dict[str, str | None]:
        return {"subject": self.subject, "name": self.name, "email": self.email}


class StoreUnavailable(Exception):
    """Credential-free persistence or encryption error."""


class StoreFull(Exception):
    """Expired rows were pruned but the shared capacity limit is reached."""


class AuthStore(Protocol):
    def check(self) -> None: ...
    def scope(self, configuration: str) -> str: ...
    def csrf(self, cookie: str) -> str: ...
    def create_transaction(
        self, cookie: str, old_cookie: str, tx: Transaction, scope: str, redirect_uri: str
    ) -> None: ...
    def consume_transaction(
        self, cookie: str, scope: str, redirect_uri: str
    ) -> Transaction | None: ...
    def rotate_session(
        self, old_cookie: str, new_cookie: str, record: SessionRecord, scope: str
    ) -> None: ...
    def get_session(self, cookie: str, scope: str) -> SessionRecord | None: ...
    def revoke_session(self, cookie: str, scope: str) -> None: ...


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cookie_digest(cookie: str) -> str | None:
    return digest(cookie) if TOKEN_PATTERN.fullmatch(cookie) else None


class DatabaseAuthStore:
    """SQLite for local persistence; PostgreSQL for shared deployments."""

    def __init__(self, engine: Engine, key: str, *, capacity: int = 1024) -> None:
        try:
            self._cipher = Fernet(key.encode("ascii"))
            raw_key = base64.urlsafe_b64decode(key.encode("ascii"))
        except (ValueError, UnicodeError) as exc:
            raise StoreUnavailable("Invalid auth store key") from exc
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise StoreUnavailable("Unsupported auth database")
        if capacity < 1 or capacity > 1024:
            raise ValueError("Auth store capacity must be between 1 and 1024")
        self.engine = engine
        self.capacity = capacity
        self._csrf_key = hmac.digest(raw_key, b"jobbr-csrf-v1", "sha256")
        self._generation = hmac.digest(raw_key, b"jobbr-store-generation-v1", "sha256").hex()

    def scope(self, configuration: str) -> str:
        return digest(configuration + "\n" + self._generation)

    def csrf(self, cookie: str) -> str:
        if not cookie_digest(cookie):
            raise StoreUnavailable("Invalid session identifier")
        return (
            base64.urlsafe_b64encode(
                hmac.digest(self._csrf_key, b"jobbr-csrf-v1\0" + cookie.encode(), "sha256")
            )
            .rstrip(b"=")
            .decode()
        )

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[Connection]:
        try:
            with self.engine.connect() as connection:
                if connection.dialect.name == "sqlite":
                    connection.exec_driver_sql("PRAGMA busy_timeout=2000")
                    if write:
                        connection.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    connection.execute(text("SET LOCAL statement_timeout = '5s'"))
                    connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                yield connection
                connection.commit()
        except SQLAlchemyError as exc:
            raise StoreUnavailable("Auth store unavailable") from exc

    def check(self) -> None:
        with self._connection() as connection:
            connection.execute(select(TRANSACTIONS).limit(0))
            connection.execute(select(SESSIONS).limit(0))
            if connection.scalar(select(GUARDS.c.id).where(GUARDS.c.id == 1)) != 1:
                raise StoreUnavailable("Auth store migration incomplete")

    def _reserve(self, connection: Connection, table: Table, old_cookie: str, scope: str) -> None:
        # BEGIN IMMEDIATE serializes SQLite writers; PostgreSQL locks the shared guard row.
        guard = connection.scalar(select(GUARDS.c.id).where(GUARDS.c.id == 1).with_for_update())
        if guard != 1:
            raise StoreUnavailable("Auth store migration incomplete")
        now = time.time()
        for expired in (TRANSACTIONS, SESSIONS):
            connection.execute(delete(expired).where(expired.c.expires_at <= now))
        connection.execute(
            delete(table).where(
                table.c.token_digest == cookie_digest(old_cookie), table.c.scope_hash == scope
            )
        )
        count = connection.scalar(select(func.count()).select_from(table))
        if count is not None and count < self.capacity:
            return
        if table is TRANSACTIONS:
            # Anonymous callers create these, so refusing when full would let anyone lock the
            # owner out of signing in. Drop the oldest pending logins instead (10 minute lifetime).
            surplus = (count or 0) - self.capacity + 1
            oldest = (
                select(table.c.token_digest)
                .order_by(table.c.expires_at, table.c.token_digest)
                .limit(surplus)
            )
            connection.execute(delete(table).where(table.c.token_digest.in_(oldest)))
            return
        raise StoreFull("Auth store is full")

    def create_transaction(
        self, cookie: str, old_cookie: str, tx: Transaction, scope: str, redirect_uri: str
    ) -> None:
        token_digest = cookie_digest(cookie)
        if token_digest is None:
            raise StoreUnavailable("Invalid transaction identifier")
        payload = self._cipher.encrypt(
            json.dumps(
                {
                    "verifier": tx.verifier,
                    "nonce": tx.nonce,
                    "redirect_uri": redirect_uri,
                    "scope": scope,
                    "token_digest": token_digest,
                    "state_digest": digest(tx.state),
                    "expires_at": tx.expires_at,
                }
            ).encode()
        ).decode()
        with self._connection(write=True) as connection:
            self._reserve(connection, TRANSACTIONS, old_cookie, scope)
            connection.execute(
                insert(TRANSACTIONS).values(
                    token_digest=token_digest,
                    state_digest=digest(tx.state),
                    scope_hash=scope,
                    encrypted_payload=payload,
                    expires_at=tx.expires_at,
                )
            )

    def consume_transaction(self, cookie: str, scope: str, redirect_uri: str) -> Transaction | None:
        token_digest = cookie_digest(cookie)
        if token_digest is None:
            return None
        # Atomic DELETE/RETURNING commits before decrypting or making any provider request.
        with self._connection(write=True) as connection:
            row = (
                connection.execute(
                    delete(TRANSACTIONS)
                    .where(
                        TRANSACTIONS.c.token_digest == token_digest,
                        TRANSACTIONS.c.scope_hash == scope,
                    )
                    .returning(TRANSACTIONS)
                )
                .mappings()
                .first()
            )
        if row is None or row["expires_at"] <= time.time():
            return None
        try:
            payload = json.loads(self._cipher.decrypt(row["encrypted_payload"].encode()))
            if (
                payload["scope"] != scope
                or payload["token_digest"] != token_digest
                or payload["state_digest"] != row["state_digest"]
                or payload["expires_at"] != row["expires_at"]
                or payload["redirect_uri"] != redirect_uri
                or not isinstance(payload["verifier"], str)
                or not isinstance(payload["nonce"], str)
            ):
                raise StoreUnavailable("Invalid auth transaction")
            # The original random state is represented only by its digest on consumption.
            return Transaction(
                row["state_digest"], payload["verifier"], payload["nonce"], row["expires_at"]
            )
        except (InvalidToken, ValueError, TypeError, KeyError) as exc:
            raise StoreUnavailable("Invalid auth transaction") from exc

    def rotate_session(
        self, old_cookie: str, new_cookie: str, record: SessionRecord, scope: str
    ) -> None:
        token_digest = cookie_digest(new_cookie)
        if token_digest is None:
            raise StoreUnavailable("Invalid session identifier")
        with self._connection(write=True) as connection:
            self._reserve(connection, SESSIONS, old_cookie, scope)
            connection.execute(
                insert(SESSIONS).values(
                    token_digest=token_digest,
                    scope_hash=scope,
                    issuer=record.issuer,
                    client_id=record.client_id,
                    subject=record.subject,
                    name=record.name,
                    email=record.email,
                    expires_at=record.expires_at,
                )
            )

    def get_session(self, cookie: str, scope: str) -> SessionRecord | None:
        token_digest = cookie_digest(cookie)
        if token_digest is None:
            return None
        with self._connection() as connection:
            row = (
                connection.execute(
                    select(SESSIONS).where(
                        SESSIONS.c.token_digest == token_digest,
                        SESSIONS.c.scope_hash == scope,
                        SESSIONS.c.expires_at > time.time(),
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return SessionRecord(
            row["issuer"],
            row["client_id"],
            row["subject"],
            row["name"],
            row["email"],
            self.csrf(cookie),
            row["expires_at"],
        )

    def revoke_session(self, cookie: str, scope: str) -> None:
        token_digest = cookie_digest(cookie)
        if token_digest is None:
            return
        with self._connection(write=True) as connection:
            connection.execute(
                delete(SESSIONS).where(
                    SESSIONS.c.token_digest == token_digest, SESSIONS.c.scope_hash == scope
                )
            )
