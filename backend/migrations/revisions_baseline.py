"""Frozen profile history tables introduced at 0004_profile_revisions."""

import sqlalchemy as sa

from migrations.store_baseline import metadata as original

metadata = sa.MetaData()
for table in original.sorted_tables:
    table.to_metadata(metadata)
revision_table = sa.Table(
    "profilerevision",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
    sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profile.id"), nullable=False),
    sa.Column("snapshot", sa.JSON(), nullable=False),
    sa.Column("fingerprint", sa.String(), nullable=False),
    sa.Column("source", sa.String(), nullable=False),
    sa.Column("saved_at", sa.DateTime(), nullable=False),
    sqlite_autoincrement=True,
)
sa.Index("ix_profilerevision_profile_id", revision_table.c.profile_id)
head_table = sa.Table(
    "profilerevisionhead",
    metadata,
    sa.Column(
        "profile_id", sa.Integer(), sa.ForeignKey("profile.id"), primary_key=True, nullable=False
    ),
    sa.Column(
        "active_revision_id", sa.Integer(), sa.ForeignKey("profilerevision.id"), nullable=False
    ),
    sa.Column("version", sa.Integer(), nullable=False),
)
