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
from app.models.customer import Customer
from app.models.menu_item_variant import MenuItemVariant
from app.api.dependencies import get_current_customer
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse
from app.services.payment import payment_service
from app.services.settings import is_auto_accept_enabled
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

    order_items_data = []
    total_amount = 0

    for item_data in payload.items:
        # Fetch the menu item
        result = await db.execute(select(MenuItem).where(MenuItem.id == item_data.menu_item_id))
        menu_item = result.scalar_one_or_none()
        if not menu_item:
            raise HTTPException(
                status_code=404,
                detail=f"Menu item {item_data.menu_item_id} not found",
            )
        if not menu_item.is_available:
            raise HTTPException(
                status_code=400,
                detail=f"Menu item '{menu_item.name}' is not available",
            )

        # Determine price and variant name
        if item_data.variant_id:
            variant_result = await db.execute(
                select(MenuItemVariant).where(
                    MenuItemVariant.id == item_data.variant_id,
                    MenuItemVariant.menu_item_id == menu_item.id,
                )
            )
            variant = variant_result.scalar_one_or_none()
            if not variant:
                raise HTTPException(status_code=404, detail="Variant not found")
            if not variant.is_available:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variant '{variant.name}' is not available",
                )
            item_price = variant.effective_price
            variant_name = variant.name
        else:
            # Legacy: no variant chosen. Use base item price.
            item_price = menu_item.effective_price
            variant_name = None

        quantity = item_data.quantity
        subtotal = item_price * quantity
        total_amount += subtotal

        order_items_data.append({
            "menu_item_id": menu_item.id,
            "item_name": menu_item.name,
            "variant_name": variant_name,
            "item_price": item_price,
            "quantity": quantity,
            "subtotal": subtotal,
        })

    if payload.payment_method == PaymentMethod.CASH:
        order_status = OrderStatus.AWAITING_PAYMENT_AT_COUNTER
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
        order_type="pickup",
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