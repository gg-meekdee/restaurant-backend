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


class OrderItemResponse(BaseModel):
    id: UUID
    item_name: str
    quantity: int
    variant_name: Optional[str] = None
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
            "total_amount": data.total_amount,
            "special_notes": data.special_notes,
            "created_at": data.created_at,
            "items": data.items,
        }