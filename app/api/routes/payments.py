from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.models.order import Order, OrderStatus, PaymentStatus, PaymentMethod
from app.services.settings import is_auto_accept_enabled
from app.services.websocket import manager

router = APIRouter(prefix="/api/payments", tags=["payments"])

class PaymentCallback(BaseModel):
    payment_reference: str
    status: str  # "success" or "failed"

@router.post("/momo/callback")
async def momo_callback(payload: PaymentCallback, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.payment_reference == payload.payment_reference))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for reference")

    if payload.status == "success":
        order.payment_status = PaymentStatus.PAID
        auto_accept = await is_auto_accept_enabled()
        order.status = OrderStatus.ACCEPTED if auto_accept else OrderStatus.PENDING_ACCEPTANCE
    else:
        order.payment_status = PaymentStatus.FAILED
        order.status = OrderStatus.CANCELLED

    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Payment status updated"}

class SimulatePayment(BaseModel):
    order_id: UUID

@router.post("/momo/simulate")
async def simulate_payment(payload: SimulatePayment, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == payload.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.payment_method != PaymentMethod.MOMO:
        raise HTTPException(status_code=400, detail="Order is not a MoMo order")

    order.payment_status = PaymentStatus.PAID
    auto_accept = await is_auto_accept_enabled()
    order.status = OrderStatus.ACCEPTED if auto_accept else OrderStatus.PENDING_ACCEPTANCE

    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Payment simulated successfully"}