"""Fail-closed checks for migration adoption and startup schema drift."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Enum, MetaData, inspect


class SchemaMismatchError(RuntimeError):
    """A database cannot safely be used by this version of Jobbr."""


def verify_schema(connection: Connection, expected: MetaData) -> None:
    inspector = inspect(connection)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected_tables = set(expected.tables)
    if actual_tables != expected_tables:
        raise SchemaMismatchError(
            "Database schema mismatch: "
            f"missing tables {sorted(expected_tables - actual_tables)}; "
            f"unexpected tables {sorted(actual_tables - expected_tables)}. "
            "Back up the database and select a compatible v2 database before retrying."
        )
    differences = compare_metadata(
        MigrationContext.configure(connection, opts={"compare_server_default": True}), expected
    )
    # Alembic autogeneration does not detect primary-key changes.
    for table in expected.sorted_tables:
        actual_pk = inspector.get_pk_constraint(table.name).get("constrained_columns") or []
        expected_pk = [column.name for column in table.primary_key.columns]
        if actual_pk != expected_pk:
            differences.append(("primary_key", table.name, actual_pk, expected_pk))
        if connection.dialect.name == "postgresql":
            actual_columns = {
                column["name"]: column for column in inspector.get_columns(table.name)
            }
            for column in table.columns:
                if isinstance(column.type, Enum) and column.name in actual_columns:
                    actual_type = actual_columns[column.name]["type"]
                    if getattr(actual_type, "enums", None) != column.type.enums:
                        differences.append(("enum_values", table.name, column.name))
    if differences:
        raise SchemaMismatchError(
            "Database schema mismatch: columns, types, constraints or indexes differ "
            f"from the expected Jobbr schema ({len(differences)} differences). "
            "Back up the database and repair it or select a compatible v2 database; "
            "the database was not adopted."
        )
