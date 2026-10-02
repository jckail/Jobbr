"""Alembic entry point shared by the CLI and application startup."""

from alembic import context
from sqlmodel import SQLModel

from jobbr import models  # noqa: F401
from jobbr.db import get_engine

config = context.config


def run_migrations() -> None:
    supplied_connection = config.attributes.get("connection")
    if context.is_offline_mode():
        context.configure(
            url=config.attributes.get("offline_url", get_engine().url),
            target_metadata=SQLModel.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    elif supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=SQLModel.metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        with get_engine().connect() as connection:
            context.configure(connection=connection, target_metadata=SQLModel.metadata)
            with context.begin_transaction():
                context.run_migrations()


run_migrations()
