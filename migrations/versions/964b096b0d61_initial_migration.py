"""initial migration

Revision ID: 964b096b0d61
Revises: 386299cdc2e8
Create Date: 2024-05-04 11:03:32.536907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel 




# revision identifiers, used by Alembic.
revision: str = '964b096b0d61'
down_revision: Union[str, None] = '386299cdc2e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stg_role', sa.Column('offers_401k', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('stg_role', 'offers_401k')
    # ### end Alembic commands ###
