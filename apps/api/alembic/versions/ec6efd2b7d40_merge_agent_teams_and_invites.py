"""merge_agent_teams_and_invites

Revision ID: ec6efd2b7d40
Revises: e3f4a5b6c7d8, 18065f96ebf2
Create Date: 2026-05-27 13:25:36.535016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec6efd2b7d40'
down_revision: Union[str, None] = ('e3f4a5b6c7d8', '18065f96ebf2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
