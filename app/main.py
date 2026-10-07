import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import async_session
from app.core.security import hash_password
from app.models.admin import Admin
from sqlalchemy import select

from app.api.routes.customer import router as customer_router
from app.api.routes.menu import router as menu_router
from app.api.routes.admin import router as admin_router
from app.api.routes.orders import router as orders_router
from app.api.routes.payments import router as payments_router
from app.api.routes.kds import router as kds_router
from app.api.routes.websocket import router as websocket_router
from app.api.routes.counter import router as counter_router


# Ensure uploads folder exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


app = FastAPI(title="Restaurant Delivery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include all routers
app.include_router(customer_router)
app.include_router(menu_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(kds_router)
app.include_router(websocket_router)
app.include_router(counter_router)


@app.on_event("startup")
async def create_default_admin():
    async with async_session() as session:
        result = await session.execute(select(Admin).where(Admin.username == settings.ADMIN_USERNAME))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = Admin(
                username=settings.ADMIN_USERNAME,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
            )
            session.add(admin)
            await session.commit()


@app.get("/health")
async def health_check():
    return {"status": "ok"}