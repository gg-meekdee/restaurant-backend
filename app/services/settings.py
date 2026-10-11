import json
from sqlalchemy import select
from app.core.database import async_session
from app.models.setting import Setting


async def get_setting(key: str, default: str | None = None) -> str | None:
    async with async_session() as session:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        return default


async def set_setting(key: str, value: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            session.add(setting)
        await session.commit()


async def is_auto_accept_enabled() -> bool:
    value = await get_setting("auto_accept_orders", "true")
    return value != "false"


# ---------- Restaurant Location ----------

async def get_restaurant_location() -> tuple[float, float] | None:
    lat_str = await get_setting("restaurant_lat")
    lng_str = await get_setting("restaurant_lng")
    if lat_str and lng_str:
        try:
            return float(lat_str), float(lng_str)
        except (ValueError, TypeError):
            return None
    return None


async def set_restaurant_location(lat: float, lng: float) -> None:
    await set_setting("restaurant_lat", str(lat))
    await set_setting("restaurant_lng", str(lng))


# ---------- Delivery Zones ----------

DEFAULT_ZONES = [
    {"max_km": 2.0, "fee": 20.0},
    {"max_km": 5.0, "fee": 25.0},
    {"max_km": 999.0, "fee": 30.0},
]


async def get_delivery_zones() -> list[dict]:
    raw = await get_setting("delivery_zones")
    if not raw:
        return DEFAULT_ZONES
    try:
        zones = json.loads(raw)
        if isinstance(zones, list) and len(zones) > 0:
            return zones
    except (json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_ZONES


async def set_delivery_zones(zones: list[dict]) -> None:
    await set_setting("delivery_zones", json.dumps(zones))