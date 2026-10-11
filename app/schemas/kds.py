from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from app.models.order import OrderStatus


class KDSOrderItemResponse(BaseModel):
    item_name: str
    variant_name: Optional[str] = None
    quantity: int
    item_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class KDSOrderResponse(BaseModel):
    id: UUID
    daily_order_number: int
    customer_phone: Optional[str] = None
    status: OrderStatus
    total_amount: Decimal
    special_notes: Optional[str] = None
    created_at: datetime
    order_type: str = "pickup"
    delivery_address: Optional[str] = None
    delivery_landmark: Optional[str] = None
    items: List[KDSOrderItemResponse]

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
            "customer_phone": customer_phone,
            "status": data.status,
            "total_amount": data.total_amount,
            "special_notes": data.special_notes,
            "created_at": data.created_at,
            "order_type": data.order_type or "pickup",
            "delivery_address": data.delivery_address,
            "delivery_landmark": data.delivery_landmark,
            "items": data.items,
        }