from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from uuid import UUID
from pydantic import BaseModel
from datetime import date

from app.core.database import get_db
from app.models.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    PaymentMethod,
)
from app.models.menu_item import MenuItem
from app.models.menu_item_variant import MenuItemVariant
from app.models.customer import Customer
from app.models.rider import Rider
from app.schemas.order import CounterOrderCreate
from app.services.daily_counter import get_next_daily_order_number
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
                "customer_phone": order.walkin_customer_phone or (order.customer.phone_number if order.customer else None),
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
# CREATE WALK-IN ORDER
# =====================================================
@router.post("/orders")
async def create_walkin_order(
    payload: CounterOrderCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an order for a walk-in customer at the counter.
    Payment is confirmed immediately (cash or MoMo received at counter).
    Order goes straight to KDS with ACCEPTED status.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items in order")

    # Validate items and calculate totals
    order_items_data = []
    total_amount = 0
    for item_data in payload.items:
        result = await db.execute(select(MenuItem).where(MenuItem.id == item_data.menu_item_id))
        menu_item = result.scalar_one_or_none()
        if not menu_item:
            raise HTTPException(status_code=404, detail=f"Menu item {item_data.menu_item_id} not found")
        if not menu_item.is_available:
            raise HTTPException(status_code=400, detail=f"Menu item '{menu_item.name}' is not available")

        # Determine price + variant name
        if item_data.variant_id:
            v_result = await db.execute(
                select(MenuItemVariant).where(
                    MenuItemVariant.id == item_data.variant_id,
                    MenuItemVariant.menu_item_id == menu_item.id,
                )
            )
            variant = v_result.scalar_one_or_none()
            if not variant:
                raise HTTPException(status_code=404, detail="Variant not found")
            if not variant.is_available:
                raise HTTPException(status_code=400, detail=f"Variant '{variant.name}' is not available")
            item_price = variant.effective_price
            variant_name = variant.name
        else:
            item_price = menu_item.effective_price
            variant_name = None

        subtotal = item_price * item_data.quantity
        total_amount += subtotal

        order_items_data.append({
            "menu_item_id": menu_item.id,
            "item_name": menu_item.name,
            "variant_name": variant_name,
            "item_price": item_price,
            "quantity": item_data.quantity,
            "subtotal": subtotal,
        })

    # Walk-in orders don't have delivery (pickup only for now)
    if payload.order_type == "delivery":
        raise HTTPException(status_code=400, detail="Delivery not supported for walk-in orders yet")

    # For walk-in orders, we don't need a customer account
    # customer_id can be null
    order_date = date.today()
    daily_number = await get_next_daily_order_number(db, order_date)

    # Payment is confirmed at counter
    order_status = OrderStatus.ACCEPTED
    payment_status = PaymentStatus.PAID if payload.payment_method == PaymentMethod.MOMO else PaymentStatus.CASH_RECEIVED

    order = Order(
        customer_id=None,  # Walk-in order, no customer account
        daily_order_number=daily_number,
        order_date=order_date,
        status=order_status,
        order_type=payload.order_type or "pickup",
        payment_method=payload.payment_method,
        payment_status=payment_status,
        total_amount=total_amount,
        special_notes=payload.special_notes,
        walkin_customer_name=payload.customer_name,
        walkin_customer_phone=payload.customer_phone,
    )
    db.add(order)
    await db.flush()

    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=item_data["menu_item_id"],
            item_name=item_data["item_name"],
            variant_name=item_data["variant_name"],
            item_price=item_data["item_price"],
            quantity=item_data["quantity"],
            subtotal=item_data["subtotal"],
        )
        db.add(order_item)

    await db.commit()
    await db.refresh(order)

    await manager.broadcast({"type": "refresh"})

    return {
        "id": str(order.id),
        "daily_order_number": order.daily_order_number,
        "status": order.status.value,
        "payment_status": order.payment_status.value,
        "payment_method": order.payment_method.value,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at.isoformat(),
    }


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