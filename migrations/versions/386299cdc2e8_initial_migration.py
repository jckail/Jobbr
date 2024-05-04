"""initial migration

Revision ID: 386299cdc2e8
Revises: d6eaa38b93be
Create Date: 2024-05-04 10:53:27.047826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel 




# revision identifiers, used by Alembic.
revision: str = '386299cdc2e8'
down_revision: Union[str, None] = 'd6eaa38b93be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stg_role', sa.Column('job_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('stg_role', 'job_id')
    # ### end Alembic commands ###
