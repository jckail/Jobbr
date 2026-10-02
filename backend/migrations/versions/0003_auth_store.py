"""Persistent shared OIDC transactions and first-party sessions."""

import sqlalchemy as sa
from alembic import op

from migrations.auth_baseline import metadata

revision = "0003_auth_store"
down_revision = "0002_saved_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Definitions remain frozen so later live model changes cannot alter historical revisions.
    for table in metadata.sorted_tables:
        columns = [column._copy() for column in table.columns]
        op.create_table(table.name, *columns)
        for index in table.indexes:
            op.create_index(
                index.name,
                table.name,
                [column.name for column in index.columns],
                unique=index.unique,
            )
    guard = sa.table("authstoreguard", sa.column("id", sa.Integer()))
    op.bulk_insert(guard, [{"id": 1}])


def downgrade() -> None:
    raise RuntimeError("Auth store downgrade is disabled to preserve active sign-in state.")
