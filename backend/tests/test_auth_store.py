"""Shared-store persistence, atomic consumption, encryption and capacity contracts."""

import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, insert, select, update

from jobbr import db
from jobbr.auth_store import (
    GUARDS,
    SESSIONS,
    TRANSACTIONS,
    DatabaseAuthStore,
    SessionRecord,
    StoreFull,
    StoreUnavailable,
    Transaction,
    cookie_digest,
    digest,
)
from tests.test_postgres import postgres  # noqa: F401 - registers the isolated pytest fixture


@pytest.fixture(params=["sqlite", "postgres"])
def stores(request, tmp_path):
    if request.param == "postgres":
        # Reuse the dedicated jobbr_test safety check and uniquely owned schema teardown.
        # The imported fixture skips explicitly when JOBBR_TEST_POSTGRES_URL is absent.
        request.getfixturevalue("postgres")
        first_engine = db.get_engine()
        second_engine = create_engine(
            first_engine.url, connect_args={"connect_timeout": 5}, pool_timeout=5
        )
    else:
        url = f"sqlite:///{tmp_path}/store.db"
        first_engine = create_engine(url, connect_args={"check_same_thread": False})
        second_engine = create_engine(url, connect_args={"check_same_thread": False})
    for table in (TRANSACTIONS, SESSIONS, GUARDS):
        table.create(first_engine)
    with first_engine.begin() as connection:
        connection.execute(insert(GUARDS).values(id=1))
    key = Fernet.generate_key().decode()
    first = DatabaseAuthStore(first_engine, key)
    second = DatabaseAuthStore(second_engine, key)
    yield first, second, key
    first_engine.dispose()
    second_engine.dispose()


def transaction():
    return Transaction(
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(64),
        secrets.token_urlsafe(32),
        time.time() + 600,
    )


def record(store, cookie):
    return SessionRecord(
        "https://auth.openai.com",
        "client",
        "owner",
        "Owner",
        None,
        store.csrf(cookie),
        time.time() + 28800,
    )


def test_cross_instance_transaction_is_encrypted_hash_only_and_single_use(stores):
    first, second, key = stores
    cookie = secrets.token_urlsafe(32)
    tx = transaction()
    scope = first.scope("configuration")
    first.create_transaction(cookie, "", tx, scope, "https://example/callback")
    with first.engine.connect() as connection:
        row = connection.execute(select(TRANSACTIONS)).mappings().one()
    serialized = json.dumps(dict(row))
    for secret in (cookie, tx.state, tx.verifier, tx.nonce):
        assert secret not in serialized
    assert row["token_digest"] == digest(cookie)
    payload = json.loads(Fernet(key.encode()).decrypt(row["encrypted_payload"].encode()))
    assert payload["verifier"] == tx.verifier
    consumed = second.consume_transaction(cookie, scope, "https://example/callback")
    assert consumed is not None
    assert consumed.state == digest(tx.state)
    assert consumed.verifier == tx.verifier
    assert first.consume_transaction(cookie, scope, "https://example/callback") is None


def test_concurrent_callback_has_one_winner(stores):
    first, second, _key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("configuration")
    first.create_transaction(cookie, "", transaction(), scope, "https://example/callback")
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(store.consume_transaction, cookie, scope, "https://example/callback")
            for store in (first, second)
        ]
        results = [future.result(timeout=10) for future in pending]
    assert sum(result is not None for result in results) == 1


def test_sessions_survive_instance_restart_and_logout_is_shared(stores):
    first, second, key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("configuration")
    original = record(first, cookie)
    first.rotate_session("", cookie, original, scope)
    assert second.get_session(cookie, scope) == original
    restarted = DatabaseAuthStore(second.engine, key)
    assert restarted.get_session(cookie, scope) == original
    with first.engine.connect() as connection:
        row = dict(connection.execute(select(SESSIONS)).mappings().one())
    assert cookie not in json.dumps(row)
    assert original.csrf_token not in json.dumps(row)
    second.revoke_session(cookie, scope)
    assert first.get_session(cookie, scope) is None


def test_key_and_configuration_changes_invalidate_sessions(stores):
    first, second, _key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("owner/client/callback")
    first.rotate_session("", cookie, record(first, cookie), scope)
    assert second.get_session(cookie, second.scope("different owner")) is None
    changed = DatabaseAuthStore(second.engine, Fernet.generate_key().decode())
    assert changed.scope("owner/client/callback") != scope
    assert changed.get_session(cookie, changed.scope("owner/client/callback")) is None
    assert changed.csrf(cookie) != first.csrf(cookie)


@pytest.mark.parametrize("tamper", ["ciphertext", "expiry", "binding"])
def test_tampered_transaction_is_burned_and_fails_closed(stores, tamper):
    first, second, _key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("configuration")
    tx = transaction()
    first.create_transaction(cookie, "", tx, scope, "https://example/callback")
    if tamper == "ciphertext":
        change = {"encrypted_payload": "corrupted"}
    elif tamper == "expiry":
        change = {"expires_at": tx.expires_at + 600}
    else:
        change = {"state_digest": digest("different state")}
    with first.engine.begin() as connection:
        connection.execute(update(TRANSACTIONS).values(**change))
    with pytest.raises(StoreUnavailable):
        second.consume_transaction(cookie, scope, "https://example/callback")
    assert first.consume_transaction(cookie, scope, "https://example/callback") is None


def test_exact_callback_binding_is_enforced_after_consumption(stores):
    first, second, _key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("configuration")
    first.create_transaction(cookie, "", transaction(), scope, "https://example/callback")
    with pytest.raises(StoreUnavailable):
        second.consume_transaction(cookie, scope, "https://example/different")
    assert first.consume_transaction(cookie, scope, "https://example/callback") is None


def test_expiry_and_cleanup(stores):
    first, second, _key = stores
    cookie = secrets.token_urlsafe(32)
    scope = first.scope("configuration")
    first.create_transaction(cookie, "", transaction(), scope, "https://example/callback")
    first.rotate_session("", cookie, record(first, cookie), scope)
    with first.engine.begin() as connection:
        connection.execute(update(TRANSACTIONS).values(expires_at=0))
        connection.execute(update(SESSIONS).values(expires_at=0))
    assert second.get_session(cookie, scope) is None
    assert second.consume_transaction(cookie, scope, "https://example/callback") is None
    second.create_transaction(
        secrets.token_urlsafe(32), "", transaction(), scope, "https://example/callback"
    )
    with first.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(SESSIONS)) == 0
        assert connection.scalar(select(func.count()).select_from(TRANSACTIONS)) == 1


def test_shared_capacity_and_atomic_session_rotation(stores):
    first, second, key = stores
    first = DatabaseAuthStore(first.engine, key, capacity=1)
    second = DatabaseAuthStore(second.engine, key, capacity=1)
    scope = first.scope("configuration")
    old = secrets.token_urlsafe(32)
    first.rotate_session("", old, record(first, old), scope)
    other = secrets.token_urlsafe(32)
    with pytest.raises(StoreFull):
        second.rotate_session("", other, record(second, other), scope)
    assert second.get_session(old, scope) is not None
    second.rotate_session(old, other, record(second, other), scope)
    assert first.get_session(old, scope) is None
    assert first.get_session(other, scope) is not None


def test_concurrent_creates_cannot_exceed_capacity(stores):
    first, second, key = stores
    first = DatabaseAuthStore(first.engine, key, capacity=1)
    second = DatabaseAuthStore(second.engine, key, capacity=1)
    scope = first.scope("configuration")
    callback = "https://example/callback"
    cookies = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]

    def create(store, cookie):
        store.create_transaction(cookie, "", transaction(), scope, callback)

    # Anonymous logins evict the oldest pending one instead of failing, so a flood cannot lock
    # the owner out; the shared bound still holds, so exactly one pending login survives.
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [
            pool.submit(create, store, c) for store, c in zip((first, second), cookies, strict=True)
        ]
        for future in pending:
            future.result(timeout=10)
    with first.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(TRANSACTIONS)) == 1
    assert sum(first.consume_transaction(c, scope, callback) is not None for c in cookies) == 1


def test_malformed_cookie_never_reaches_database(stores):
    first, _second, _key = stores
    for cookie in ("", "é" * 43, "a" * 42, "a" * 10000, "/" * 43):
        assert cookie_digest(cookie) is None
        assert first.get_session(cookie, "scope") is None
        assert first.consume_transaction(cookie, "scope", "callback") is None


def test_missing_guard_and_tables_fail_readiness_without_writes(stores, tmp_path):
    first, _second, key = stores
    with first.engine.begin() as connection:
        connection.execute(GUARDS.delete())
    with pytest.raises(StoreUnavailable):
        first.check()
    engine = create_engine(f"sqlite:///{tmp_path}/unmigrated.db")
    with pytest.raises(StoreUnavailable):
        DatabaseAuthStore(engine, key).check()
    engine.dispose()
