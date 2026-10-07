from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_next_daily_order_number(db: AsyncSession, order_date: date) -> int:
    """
    Atomically increments and returns the next daily order number for the given date.
    Uses PostgreSQL's INSERT ... ON CONFLICT ... RETURNING for race-free operation.
    """
    result = await db.execute(
        text("""
            INSERT INTO daily_counters (date, last_number)
            VALUES (:date, 1)
            ON CONFLICT (date)
            DO UPDATE SET last_number = daily_counters.last_number + 1
            RETURNING last_number
        """),
        {"date": order_date},
    )
    return result.scalar_one()