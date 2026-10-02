"""Immutable profile history, preserving active profile IDs and content."""

import hashlib
import json
from datetime import UTC, datetime

from alembic import context, op

from migrations.revisions_baseline import head_table, metadata, revision_table

revision = "0004_profile_revisions"
down_revision = "0003_auth_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Frozen definitions; create only the two new tables, with complete FK/index metadata.
    bind = op.get_bind()
    for table in (revision_table, head_table):
        table.create(bind)
    if context.is_offline_mode():
        return  # Offline SQL emits DDL; historical content backfill requires online upgrade.
    profile = metadata.tables["profile"]
    for row in bind.execute(profile.select()).mappings():
        snapshot = {key: value for key, value in row.items() if key not in ("id", "updated_at")}
        fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        # This is the time history was first recorded, not an invented original save date.
        result = bind.execute(
            revision_table.insert().values(
                profile_id=row["id"],
                snapshot=snapshot,
                fingerprint=fingerprint,
                source="legacy",
                saved_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        bind.execute(
            head_table.insert().values(
                profile_id=row["id"],
                active_revision_id=result.inserted_primary_key[0],
                version=0,
            )
        )


def downgrade() -> None:
    raise RuntimeError("Profile history downgrade is disabled to preserve private resumes.")
