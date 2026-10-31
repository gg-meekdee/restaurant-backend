"""add_walkin_customer_fields_to_orders

Revision ID: 0706bb68997f
Revises: 462994cecf2b
Create Date: 2026-10-31 04:47:05.688052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0706bb68997f'
down_revision: Union[str, Sequence[str], None] = '462994cecf2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add walk-in customer fields
    op.add_column('orders', sa.Column('walkin_customer_name', sa.String(100), nullable=True))
    op.add_column('orders', sa.Column('walkin_customer_phone', sa.String(20), nullable=True))

    # Make customer_id nullable for walk-in orders
    op.alter_column('orders', 'customer_id', nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'walkin_customer_phone')
    op.drop_column('orders', 'walkin_customer_name')
    op.alter_column('orders', 'customer_id', nullable=False)
