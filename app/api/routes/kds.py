from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.database import get_db
from app.models.order import Order, OrderStatus
from app.schemas.kds import KDSOrderResponse
from app.services.websocket import manager

router = APIRouter(prefix="/api/kds", tags=["kds"])


async def get_order_with_items(order_id: UUID, db: AsyncSession) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/orders", response_model=list[KDSOrderResponse])
async def list_active_orders(db: AsyncSession = Depends(get_db)):
    active_statuses = [OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY]
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.status.in_(active_statuses))
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return orders


@router.post("/orders/{order_id}/prepare", response_model=KDSOrderResponse)
async def mark_preparing(order_id: UUID, db: AsyncSession = Depends(get_db)):
    order = await get_order_with_items(order_id, db)
    if order.status != OrderStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="Order cannot be moved to preparing from its current status")
    order.status = OrderStatus.PREPARING
    await db.commit()
    await db.refresh(order)
    await manager.broadcast({"type": "refresh"})
    return order


@router.post("/orders/{order_id}/ready", response_model=KDSOrderResponse)
async def mark_ready(order_id: UUID, db: AsyncSession = Depends(get_db)):
    order = await get_order_with_items(order_id, db)
    if order.status != OrderStatus.PREPARING:
        raise HTTPException(status_code=400, detail="Order must be in preparing status to be marked ready")
    order.status = OrderStatus.READY
    await db.commit()
    await db.refresh(order)
    await manager.broadcast({"type": "refresh"})
    return order