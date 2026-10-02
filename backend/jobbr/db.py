from collections.abc import Iterator
from functools import lru_cache
from importlib.resources import files
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, event, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from . import auth_models, models  # noqa: F401  (registers tables on SQLModel.metadata)
from .config import get_settings
from .schema import verify_schema


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql"):
        options = make_url(url).query.get("options", "")
        if not isinstance(options, str):
            raise ValueError("PostgreSQL options must be a single string.")
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_timeout=5,
            connect_args={
                "connect_timeout": 5,
                "options": f"{options} -c statement_timeout=5000 -c lock_timeout=2000".strip(),
            },
        )
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


def reset_engine() -> None:
    get_engine.cache_clear()


def init_db() -> None:
    configuration = Config()
    configuration.set_main_option("script_location", str(files("migrations")))
    with get_engine().begin() as connection:
        if connection.dialect.name == "postgresql":
            # One migration transaction per database; timeout remains bounded by connection options.
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4A4F424252})
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "head")
        verify_schema(connection, SQLModel.metadata)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
