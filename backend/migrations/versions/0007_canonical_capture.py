"""Add empty canonical posting identity and fenced capture reservation tables."""

from alembic import op

from migrations.canonical_baseline import identity_table, lease_table

revision = "0007_canonical_capture"
down_revision = "0006_extension_capture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (identity_table, lease_table):
        table.create(bind)


def downgrade() -> None:
    raise RuntimeError("Canonical capture downgrade is disabled to preserve identity metadata.")
