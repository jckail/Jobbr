"""Owner-approved, bounded capture-only extension capabilities."""

from alembic import op

from migrations.capture_baseline import grant_table, pairing_table, receipt_table, throttle_table

revision = "0006_extension_capture"
down_revision = "0005_tailoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (pairing_table, grant_table, receipt_table, throttle_table):
        table.create(bind)
    bind.execute(throttle_table.insert().values(id=1, window_start=0, count=0))


def downgrade() -> None:
    raise RuntimeError("Extension authorization downgrade is disabled to preserve audit metadata.")
