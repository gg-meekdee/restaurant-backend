"""add delivery coordinates to orders

Revision ID: 03b17a6bbfa2
Revises: 02a06f5aaea1
Create Date: 2026-10-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03b17a6bbfa2'
down_revision: Union[str, Sequence[str], None] = '02a06f5aaea1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'orders',
        sa.Column('delivery_lat', sa.Numeric(precision=10, scale=7), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_lng', sa.Numeric(precision=10, scale=7), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'delivery_lng')
    op.drop_column('orders', 'delivery_lat')