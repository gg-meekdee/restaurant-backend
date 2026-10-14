from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models.order import (
    Order,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
)
from app.models.rider import Rider
from app.schemas.counter import CounterOrderResponse
from app.services.websocket import manager

router = APIRouter(prefix="/api/counter", tags=["counter"])


# =====================================================
# LIST ORDERS FOR COUNTER
# =====================================================
@router.get("/orders", response_model=list[CounterOrderResponse])
async def list_counter_orders(db: AsyncSession = Depends(get_db)):
    """
    Counter sees:
    - ACCEPTED cash orders with CASH_PENDING (collection needed)
    - READY orders (ready to handover / assign rider)
    - OUT_FOR_DELIVERY orders (in transit — awaiting confirmation)
    """
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(
            or_(
                and_(
                    Order.status == OrderStatus.ACCEPTED,
                    Order.payment_method == PaymentMethod.CASH,
                    Order.payment_status == PaymentStatus.CASH_PENDING,
                ),
                Order.status == OrderStatus.READY,
                Order.status == OrderStatus.OUT_FOR_DELIVERY,
            )
        )
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


# =====================================================
# ACTIVE RIDERS FOR COUNTER
# =====================================================
@router.get("/riders")
async def list_active_riders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Rider)
        .where(Rider.is_active == True)
        .order_by(Rider.rider_type, Rider.name)
    )
    riders = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "phone": r.phone,
            "rider_type": r.rider_type.value,
        }
        for r in riders
    ]


# =====================================================
# ASSIGN RIDER
# =====================================================
class AssignRiderIn(BaseModel):
    rider_id: UUID


@router.post("/orders/{order_id}/assign-rider")
async def assign_rider(
    order_id: UUID,
    payload: AssignRiderIn,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.order_type != "delivery":
        raise HTTPException(status_code=400, detail="Not a delivery order")
    if order.status not in (OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY):
        raise HTTPException(status_code=400, detail="Order is not ready for assignment")

    rider_result = await db.execute(select(Rider).where(Rider.id == payload.rider_id))
    rider = rider_result.scalar_one_or_none()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found")
    if not rider.is_active:
        raise HTTPException(status_code=400, detail="Rider is not active")

    order.rider_id = rider.id
    order.rider_name = rider.name
    order.rider_phone = rider.phone
    await db.commit()
    await db.refresh(order)
    await manager.broadcast({"type": "refresh"})
    return {"message": "Rider assigned"}


# =====================================================
# OUT FOR DELIVERY
# =====================================================
@router.post("/orders/{order_id}/out-for-delivery")
async def mark_out_for_delivery(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.order_type != "delivery":
        raise HTTPException(status_code=400, detail="Not a delivery order")
    if order.status != OrderStatus.READY:
        raise HTTPException(status_code=400, detail="Order must be READY first")
    if not order.rider_id:
        raise HTTPException(status_code=400, detail="Assign a rider first")

    order.status = OrderStatus.OUT_FOR_DELIVERY
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order is out for delivery"}


# =====================================================
# MARK DELIVERED
# =====================================================
@router.post("/orders/{order_id}/delivered")
async def mark_delivered(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.OUT_FOR_DELIVERY:
        raise HTTPException(status_code=400, detail="Order is not out for delivery")

    order.status = OrderStatus.DELIVERED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order delivered"}


# =====================================================
# MARK CASH RECEIVED
# =====================================================
@router.post("/orders/{order_id}/cash-received")
async def mark_cash_received(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_method.value != "cash":
        raise HTTPException(status_code=400, detail="Not a cash order")
    if order.status not in (OrderStatus.DELIVERED, OrderStatus.READY, OrderStatus.COMPLETED):
        raise HTTPException(status_code=400, detail="Order is not ready for cash confirmation")

    order.payment_status = PaymentStatus.CASH_RECEIVED
    if order.status == OrderStatus.DELIVERED:
        order.status = OrderStatus.COMPLETED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Cash received"}


# =====================================================
# PICKUP HANDOVER
# =====================================================
@router.post("/orders/{order_id}/handover")
async def handover_pickup(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.order_type == "delivery":
        raise HTTPException(status_code=400, detail="Use delivery endpoints for delivery orders")
    if order.status != OrderStatus.READY:
        raise HTTPException(status_code=400, detail="Order is not ready")

    order.status = OrderStatus.COMPLETED
    if order.payment_method.value == "cash":
        order.payment_status = PaymentStatus.CASH_RECEIVED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order handed over"}