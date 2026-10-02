"""Anonymous login starts must not be able to lock the owner out of signing in."""

import secrets
import time

import pytest

from jobbr.auth import SessionRecord
from jobbr.auth_store import DatabaseAuthStore, StoreFull, Transaction
from tests.test_auth_store import stores  # noqa: F401 - fixture (sqlite and, when set, postgres)
from tests.test_postgres import postgres  # noqa: F401 - fixture used by `stores`


def pending(minutes):
    return Transaction(
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(64),
        secrets.token_urlsafe(32),
        time.time() + minutes * 60,
    )


def test_anonymous_login_flood_cannot_lock_out_the_owner(stores):  # noqa: F811
    first, _second, key = stores
    store = DatabaseAuthStore(first.engine, key, capacity=3)
    scope = store.scope("configuration")
    cookies = []
    for minutes in range(1, 6):  # five starts against a capacity of three
        cookie = secrets.token_urlsafe(32)
        cookies.append(cookie)
        store.create_transaction(cookie, "", pending(minutes), scope, "https://example/callback")
    survivors = [
        store.consume_transaction(c, scope, "https://example/callback") is not None for c in cookies
    ]
    assert survivors == [False, False, True, True, True]  # oldest evicted, newest still valid


def test_session_capacity_still_fails_closed(stores):  # noqa: F811
    first, _second, key = stores
    store = DatabaseAuthStore(first.engine, key, capacity=1)
    scope = store.scope("configuration")

    def session(cookie):
        return SessionRecord(
            "https://auth.openai.com",
            "client",
            "owner",
            None,
            None,
            store.csrf(cookie),
            time.time() + 60,
        )

    one, two = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    store.rotate_session("", one, session(one), scope)
    with pytest.raises(StoreFull):
        store.rotate_session("", two, session(two), scope)
