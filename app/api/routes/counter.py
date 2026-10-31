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
from app.services.websocket import manager

router = APIRouter(prefix="/api/counter", tags=["counter"])


# =====================================================
# LIST ORDERS FOR COUNTER
# =====================================================
@router.get("/orders")
async def list_counter_orders(db: AsyncSession = Depends(get_db)):
    """
    Counter sees:
    - ACCEPTED cash orders with CASH_PENDING (collection needed)
    - READY orders (ready to handover / assign rider)
    - OUT_FOR_DELIVERY orders (in transit — awaiting confirmation)
    """
    try:
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
        orders = result.scalars().all()

        return [
            {
                "id": str(order.id),
                "daily_order_number": order.daily_order_number,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "customer_phone": order.customer.phone_number if order.customer else None,
                "status": order.status.value,
                "total_amount": float(order.total_amount),
                "special_notes": order.special_notes,
                "created_at": order.created_at.isoformat(),
                "order_type": order.order_type or "pickup",
                "delivery_address": order.delivery_address,
                "delivery_landmark": order.delivery_landmark,
                "delivery_lat": float(order.delivery_lat) if order.delivery_lat else None,
                "delivery_lng": float(order.delivery_lng) if order.delivery_lng else None,
                "delivery_fee": float(order.delivery_fee or 0),
                "rider_id": str(order.rider_id) if order.rider_id else None,
                "rider_name": order.rider_name,
                "rider_phone": order.rider_phone,
                "payment_method": order.payment_method.value if order.payment_method else "cash",
                "payment_status": order.payment_status.value if order.payment_status else "pending",
                "items": [
                    {
                        "id": str(item.id),
                        "item_name": item.item_name,
                        "variant_name": item.variant_name,
                        "quantity": item.quantity,
                        "item_price": float(item.item_price),
                        "subtotal": float(item.subtotal),
                    }
                    for item in order.items
                ],
            }
            for order in orders
        ]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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