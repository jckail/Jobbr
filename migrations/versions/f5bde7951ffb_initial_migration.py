"""initial migration

Revision ID: f5bde7951ffb
Revises: 526e61e998b6
Create Date: 2024-05-03 17:06:29.436102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel 




# revision identifiers, used by Alembic.
revision: str = 'f5bde7951ffb'
down_revision: Union[str, None] = '526e61e998b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('app_ai_event', sa.Column('event_type', sa.Enum('CREATE', 'CHAT', 'FUNCTION', 'KILL', 'CONTEXT', name='aieventtype'), nullable=False))
    op.add_column('app_ai_event', sa.Column('event', sa.Enum('CREATE_AI', 'PARSE_ROLE_HTML', 'LOAD_CONTEXT', 'GENERATE_PROMPT', name='aievent'), nullable=False))
    op.add_column('app_ai_event', sa.Column('event_status', sa.Enum('STARTED', 'RUNNING', 'FAILED', 'COMPLETED', name='aieventstatus'), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('app_ai_event', 'event_status')
    op.drop_column('app_ai_event', 'event')
    op.drop_column('app_ai_event', 'event_type')
    # ### end Alembic commands ###