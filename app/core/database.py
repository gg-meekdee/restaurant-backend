from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.models.base import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,              # set to True only when debugging
    pool_size=10,            # max steady connections
    max_overflow=20,         # extra connections when busy
    pool_pre_ping=True,      # detect dead connections
    pool_recycle=1800,       # recycle connections after 30 min
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session