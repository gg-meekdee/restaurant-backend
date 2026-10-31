"""add_missing_order_status_enum_values

Revision ID: 462994cecf2b
Revises: e24c894fd89b
Create Date: 2026-10-31 04:14:51.591722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '462994cecf2b'
down_revision: Union[str, Sequence[str], None] = 'e24c894fd89b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing enum values to orderstatus
    # PostgreSQL doesn't support IF NOT EXISTS for ALTER TYPE, so we use a DO block
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'AWAITING_PAYMENT_AT_COUNTER' AND enumtypid = 'orderstatus'::regtype) THEN
                ALTER TYPE orderstatus ADD VALUE 'AWAITING_PAYMENT_AT_COUNTER';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'OUT_FOR_DELIVERY' AND enumtypid = 'orderstatus'::regtype) THEN
                ALTER TYPE orderstatus ADD VALUE 'OUT_FOR_DELIVERY';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'DELIVERED' AND enumtypid = 'orderstatus'::regtype) THEN
                ALTER TYPE orderstatus ADD VALUE 'DELIVERED';
            END IF;
        END $$;
    """)

    # Add missing enum values to paymentstatus
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'PENDING_REFUND' AND enumtypid = 'paymentstatus'::regtype) THEN
                ALTER TYPE paymentstatus ADD VALUE 'PENDING_REFUND';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'REFUNDED' AND enumtypid = 'paymentstatus'::regtype) THEN
                ALTER TYPE paymentstatus ADD VALUE 'REFUNDED';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL doesn't support removing enum values directly
    # Would need to create a new type and migrate, but for simplicity we'll leave them
    pass
