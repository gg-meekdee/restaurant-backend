from sqlalchemy import select
from app.core.database import async_session
from app.models.setting import Setting

async def is_auto_accept_enabled() -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == "auto_accept_orders")
        )
        setting = result.scalar_one_or_none()
        if setting and setting.value == "false":
            return False
        return True  # default to auto-accept enabled