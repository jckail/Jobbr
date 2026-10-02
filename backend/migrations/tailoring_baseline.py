"""Frozen complete schema at0005_tailoring; receipt metadata never contains source prose."""

import sqlalchemy as sa

from migrations.revisions_baseline import metadata as original

metadata = sa.MetaData()
for table in original.sorted_tables:
    table.to_metadata(metadata)
receipt_table = sa.Table(
    "tailoringreceipt",
    metadata,
    sa.Column("id", sa.String(), primary_key=True, nullable=False),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
    sa.Column("job_id", sa.Integer(), nullable=False),
    sa.Column("source_revision_id", sa.Integer(), nullable=False),
    sa.Column("provenance", sa.JSON(), nullable=False),
    sa.Column("original_hash", sa.String(), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.Column("expires_at", sa.DateTime(), nullable=False),
)
sa.Index("ix_tailoringreceipt_profile_id", receipt_table.c.profile_id)
sa.Index("ix_tailoringreceipt_expires_at", receipt_table.c.expires_at)
draft_table = sa.Table(
    "savedtailoringdraft",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
    sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), nullable=False),
    sa.Column(
        "source_revision_id", sa.Integer(), sa.ForeignKey("profilerevision.id"), nullable=False
    ),
    sa.Column("receipt_id", sa.String(), nullable=False),
    sa.Column("provenance", sa.JSON(), nullable=False),
    sa.Column("draft", sa.JSON(), nullable=False),
    sa.Column("user_edited", sa.Boolean(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sqlite_autoincrement=True,
)
for column in ("profile_id", "job_id", "source_revision_id"):
    sa.Index(f"ix_savedtailoringdraft_{column}", draft_table.c[column])
