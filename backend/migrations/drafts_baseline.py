"""Frozen schema at revision 0002_saved_drafts, for migration and backup validation."""

import sqlalchemy as sa

from migrations.baseline import metadata as original

metadata = sa.MetaData()
for table in original.sorted_tables:
    table.to_metadata(metadata)

saved_draft = sa.Table(
    "savedcareerdraft",
    metadata,
    sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
    sa.Column("job_id", sa.Integer(), nullable=False),
    sa.Column("profile_id", sa.Integer(), nullable=False),
    sa.Column("result", sa.JSON(), nullable=False),
    sa.Column("source_fingerprint", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(["job_id"], ["job.id"]),
    sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
)
sa.Index("ix_savedcareerdraft_job_id", saved_draft.c.job_id)
sa.Index("ix_savedcareerdraft_profile_id", saved_draft.c.profile_id)
