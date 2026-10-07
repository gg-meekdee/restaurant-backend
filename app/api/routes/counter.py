from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.database import get_db
from app.models.order import Order, OrderStatus, PaymentStatus
from app.schemas.kds import KDSOrderResponse
from app.services.websocket import manager

router = APIRouter(prefix="/api/counter", tags=["counter"])


@router.get("/orders", response_model=list[KDSOrderResponse])
async def list_counter_orders(db: AsyncSession = Depends(get_db)):
    statuses = [OrderStatus.AWAITING_PAYMENT_AT_COUNTER, OrderStatus.READY]
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.status.in_(statuses))
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.post("/orders/{order_id}/confirm-cash", response_model=KDSOrderResponse)
async def confirm_cash(order_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.AWAITING_PAYMENT_AT_COUNTER:
        raise HTTPException(status_code=400, detail="Order is not awaiting cash payment")

    order.status = OrderStatus.ACCEPTED
    order.payment_status = PaymentStatus.CASH_RECEIVED
    await db.commit()
    await db.refresh(order)
    await manager.broadcast({"type": "refresh"})
    return order


@router.post("/orders/{order_id}/handover", response_model=KDSOrderResponse)
async def hand_over(order_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.READY:
        raise HTTPException(status_code=400, detail="Order is not ready for handover")

    order.status = OrderStatus.COMPLETED
    await db.commit()
    await db.refresh(order)
    await manager.broadcast({"type": "refresh"})
    return order