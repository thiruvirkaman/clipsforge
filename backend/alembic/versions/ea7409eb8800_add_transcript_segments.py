"""add transcript_segments to projects

Revision ID: ea7409eb8800
Revises: f6dc98201806
Create Date: 2026-08-29 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea7409eb8800"
down_revision: Union[str, Sequence[str], None] = "f6dc98201806"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("projects", sa.Column("transcript_segments", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("projects", "transcript_segments")
