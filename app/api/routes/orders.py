from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List
from datetime import date

from app.core.database import get_db
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus, PaymentMethod
from app.models.menu_item import MenuItem
from app.models.menu_item_variant import MenuItemVariant
from app.models.customer import Customer
from app.models.rider import Rider
from app.api.dependencies import get_current_customer
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse
from app.services.payment import payment_service
from app.services.settings import (
    is_auto_accept_enabled,
    get_restaurant_location,
    get_delivery_zones,
)
from app.services.delivery import calculate_delivery_fee
from app.services.daily_counter import get_next_daily_order_number
from app.services.websocket import manager

router = APIRouter(prefix="/api", tags=["orders"])


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
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

    # Handle delivery fee
    is_delivery = payload.order_type == "delivery"
    delivery_fee = 0
    if is_delivery:
        if not payload.delivery_address:
            raise HTTPException(status_code=400, detail="Delivery address is required")
        if payload.delivery_lat is None or payload.delivery_lng is None:
            raise HTTPException(status_code=400, detail="Delivery location coordinates are required")

        restaurant_loc = await get_restaurant_location()
        if not restaurant_loc:
            raise HTTPException(status_code=400, detail="Restaurant location not configured")
        restaurant_lat, restaurant_lng = restaurant_loc

        zones = await get_delivery_zones()
        quote = calculate_delivery_fee(
            customer_lat=payload.delivery_lat,
            customer_lng=payload.delivery_lng,
            restaurant_lat=restaurant_lat,
            restaurant_lng=restaurant_lng,
            zones=zones,
        )
        delivery_fee = quote["fee"]
        total_amount += delivery_fee

    # Determine statuses
    if payload.payment_method == PaymentMethod.CASH:
        # Cash orders start cooking immediately. Cash collected on arrival.
        order_status = OrderStatus.ACCEPTED
        payment_status = PaymentStatus.CASH_PENDING
    elif payload.payment_method == PaymentMethod.MOMO:
        order_status = OrderStatus.PENDING_PAYMENT
        payment_status = PaymentStatus.PENDING
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    order_date = date.today()
    daily_number = await get_next_daily_order_number(db, order_date)

    order = Order(
        customer_id=current_customer.id,
        daily_order_number=daily_number,
        order_date=order_date,
        status=order_status,
        order_type=payload.order_type,
        delivery_address=payload.delivery_address,
        delivery_landmark=payload.delivery_landmark,
        delivery_lat=payload.delivery_lat,     # NEW
        delivery_lng=payload.delivery_lng,     # NEW
        delivery_fee=delivery_fee,
        payment_method=payload.payment_method,
        payment_status=payment_status,
        total_amount=total_amount,
        special_notes=payload.special_notes,
    )
    db.add(order)
    await db.flush()

    if payload.payment_method == PaymentMethod.MOMO:
        payment_ref = payment_service.initiate_momo_payment(order, current_customer.phone_number)
        order.payment_reference = payment_ref

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

    result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order_items = result.scalars().all()

    return OrderResponse(
        id=order.id,
        daily_order_number=order.daily_order_number,
        order_date=order.order_date,
        customer_phone=current_customer.phone_number,
        status=order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        order_type=order.order_type or "pickup",
        delivery_address=order.delivery_address,
        delivery_landmark=order.delivery_landmark,
        delivery_lat=float(order.delivery_lat) if order.delivery_lat is not None else None,
        delivery_lng=float(order.delivery_lng) if order.delivery_lng is not None else None,
        delivery_fee=order.delivery_fee,
        rider_id=order.rider_id,
        rider_name=order.rider_name,
        rider_phone=order.rider_phone,
        total_amount=order.total_amount,
        special_notes=order.special_notes,
        created_at=order.created_at,
        items=order_items,
    )


@router.get("/orders", response_model=List[OrderResponse])
async def list_my_orders(
    db: AsyncSession = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.customer_id == current_customer.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return orders


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id, Order.customer_id == current_customer.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order