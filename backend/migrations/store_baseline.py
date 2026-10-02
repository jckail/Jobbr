"""Frozen complete schema at 0003_auth_store for historical backup validation."""

import sqlalchemy as sa

from migrations.auth_baseline import metadata as auth
from migrations.drafts_baseline import metadata as drafts

metadata = sa.MetaData()
for original in (drafts, auth):
    for table in original.sorted_tables:
        table.to_metadata(metadata)
