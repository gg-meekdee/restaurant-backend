from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID
from decimal import Decimal
from typing import List, Optional
from datetime import datetime, date
from app.models.order import OrderStatus, PaymentStatus, PaymentMethod


class OrderItemCreate(BaseModel):
    menu_item_id: UUID
    quantity: int
    variant_id: Optional[UUID] = None


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    special_notes: Optional[str] = None
    payment_method: PaymentMethod
    order_type: str = "pickup"                   # "pickup" or "delivery"
    delivery_address: Optional[str] = None
    delivery_landmark: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None


class OrderItemResponse(BaseModel):
    id: UUID
    item_name: str
    variant_name: Optional[str] = None
    quantity: int
    item_price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: UUID
    daily_order_number: int
    order_date: date
    customer_phone: Optional[str] = None
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: PaymentMethod
    order_type: str = "pickup"
    delivery_address: Optional[str] = None
    delivery_landmark: Optional[str] = None
    delivery_lat: Optional[float] = None       # NEW
    delivery_lng: Optional[float] = None       # NEW
    delivery_fee: Decimal = Decimal("0")
    rider_id: Optional[UUID] = None
    rider_name: Optional[str] = None
    rider_phone: Optional[str] = None
    total_amount: Decimal
    special_notes: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def from_orm_with_customer_phone(cls, data):
        if isinstance(data, dict):
            return data
        customer_phone = None
        if hasattr(data, "customer") and data.customer is not None:
            customer_phone = data.customer.phone_number
        return {
            "id": data.id,
            "daily_order_number": data.daily_order_number,
            "order_date": data.order_date,
            "customer_phone": customer_phone,
            "status": data.status,
            "payment_status": data.payment_status,
            "payment_method": data.payment_method,
            "order_type": data.order_type or "pickup",
            "delivery_address": data.delivery_address,
            "delivery_landmark": data.delivery_landmark,
            "delivery_lat": float(data.delivery_lat) if data.delivery_lat is not None else None,
            "delivery_lng": float(data.delivery_lng) if data.delivery_lng is not None else None,
            "delivery_fee": data.delivery_fee or Decimal("0"),
            "rider_id": data.rider_id,
            "rider_name": data.rider_name,
            "rider_phone": data.rider_phone,
            "total_amount": data.total_amount,
            "special_notes": data.special_notes,
            "created_at": data.created_at,
            "items": data.items,
        }