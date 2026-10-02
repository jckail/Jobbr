"""Add private, opt-in saved career drafts without changing existing records."""

from alembic import op

from migrations.drafts_baseline import saved_draft

revision = "0002_saved_drafts"
down_revision = "0001_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    saved_draft.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    raise RuntimeError("Saved draft downgrade is disabled to preserve private drafts.")
