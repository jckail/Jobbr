"""Frozen complete schema at 0007_canonical_capture, including additive metadata tables."""

import sqlalchemy as sa

from migrations.capture_baseline import metadata as original

metadata = sa.MetaData()
for table in original.sorted_tables:
    table.to_metadata(metadata)

identity_table = sa.Table(
    "jobexternalidentity",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
    sa.Column("provider", sa.String(), nullable=False),
    sa.Column("board", sa.String(), nullable=False),
    sa.Column("posting_id", sa.String(), nullable=False),
    sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), nullable=False),
    sa.UniqueConstraint("provider", "board", "posting_id"),
)
sa.Index("ix_jobexternalidentity_job_id", identity_table.c.job_id)

lease_table = sa.Table(
    "capturelease",
    metadata,
    sa.Column("resource_key", sa.String(), primary_key=True, nullable=False),
    sa.Column("nonce", sa.String(), nullable=False),
    sa.Column("expires_at", sa.Float(), nullable=False),
    sa.Column("job_id", sa.Integer(), sa.ForeignKey("job.id"), nullable=True),
    sa.Column("job_baseline", sa.String(), nullable=True),
)
sa.Index("ix_capturelease_expires_at", lease_table.c.expires_at)
sa.Index("ix_capturelease_job_id", lease_table.c.job_id)
