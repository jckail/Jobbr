"""Frozen additive extension metadata tables introduced at0006_extension_capture."""

import sqlalchemy as sa

from migrations.tailoring_baseline import metadata as original

metadata = sa.MetaData()
for table in original.sorted_tables:
    table.to_metadata(metadata)

pairing_table = sa.Table(
    "capturepairing",
    metadata,
    sa.Column("pairing_digest", sa.String(), primary_key=True, nullable=False),
    sa.Column("extension_id", sa.String(), nullable=False),
    sa.Column("challenge", sa.String(), nullable=False),
    sa.Column("comparison_code", sa.String(), nullable=False),
    sa.Column("scope_hash", sa.String(), nullable=False),
    sa.Column("expires_at", sa.Float(), nullable=False),
    sa.Column("session_digest", sa.String(), nullable=True),
    sa.Column("ai_provider", sa.String(), nullable=True),
    sa.Column("ai_model", sa.String(), nullable=True),
    sa.Column("llm_enabled", sa.Boolean(), nullable=True),
    sa.Column("consumed", sa.Boolean(), nullable=False),
)
sa.Index("ix_capturepairing_expires_at", pairing_table.c.expires_at)
grant_table = sa.Table(
    "capturegrant",
    metadata,
    sa.Column("token_digest", sa.String(), primary_key=True, nullable=False),
    sa.Column("grant_id", sa.String(), nullable=False),
    sa.Column("extension_id", sa.String(), nullable=False),
    sa.Column("session_digest", sa.String(), nullable=False),
    sa.Column("scope_hash", sa.String(), nullable=False),
    sa.Column("ai_provider", sa.String(), nullable=False),
    sa.Column("ai_model", sa.String(), nullable=False),
    sa.Column("llm_enabled", sa.Boolean(), nullable=False),
    sa.Column("expires_at", sa.Float(), nullable=False),
    sa.Column("captures_remaining", sa.Integer(), nullable=False),
    sa.Column("busy", sa.Boolean(), nullable=False),
    sa.Column("revoked", sa.Boolean(), nullable=False),
)
sa.Index("ix_capturegrant_grant_id", grant_table.c.grant_id, unique=True)
sa.Index("ix_capturegrant_expires_at", grant_table.c.expires_at)
receipt_table = sa.Table(
    "capturereceipt",
    metadata,
    sa.Column(
        "token_digest",
        sa.String(),
        sa.ForeignKey("capturegrant.token_digest"),
        primary_key=True,
        nullable=False,
    ),
    sa.Column("request_digest", sa.String(), primary_key=True, nullable=False),
    sa.Column("input_digest", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("job_id", sa.Integer(), nullable=True),
)
throttle_table = sa.Table(
    "capturethrottle",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
    sa.Column("window_start", sa.Float(), nullable=False),
    sa.Column("count", sa.Integer(), nullable=False),
)
