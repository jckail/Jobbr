"""Frozen auth-store schema introduced at revision 0003; never import live models."""

import sqlalchemy as sa

metadata = sa.MetaData()
sa.Table(
    "authtransaction",
    metadata,
    sa.Column("token_digest", sa.String(64), primary_key=True),
    sa.Column("state_digest", sa.String(64), nullable=False),
    sa.Column("scope_hash", sa.String(64), nullable=False),
    sa.Column("encrypted_payload", sa.Text(), nullable=False),
    sa.Column("expires_at", sa.Float(), nullable=False),
    sa.Index("ix_authtransaction_expires_at", "expires_at"),
)
sa.Table(
    "authsession",
    metadata,
    sa.Column("token_digest", sa.String(64), primary_key=True),
    sa.Column("scope_hash", sa.String(64), nullable=False),
    sa.Column("issuer", sa.String(200), nullable=False),
    sa.Column("client_id", sa.String(300), nullable=False),
    sa.Column("subject", sa.String(300), nullable=False),
    sa.Column("name", sa.String(300), nullable=True),
    sa.Column("email", sa.String(320), nullable=True),
    sa.Column("expires_at", sa.Float(), nullable=False),
    sa.Index("ix_authsession_expires_at", "expires_at"),
)
sa.Table("authstoreguard", metadata, sa.Column("id", sa.Integer(), primary_key=True))
