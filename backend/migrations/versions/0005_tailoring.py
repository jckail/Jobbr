"""Private reviewed tailoring drafts and bounded metadata-only generation receipts."""

from alembic import op

from migrations.tailoring_baseline import draft_table, receipt_table

revision = "0005_tailoring"
down_revision = "0004_profile_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (receipt_table, draft_table):
        table.create(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Tailoring downgrade is disabled to preserve reviewed private drafts.")
