from pydantic import BaseModel, ConfigDict, field_serializer
from uuid import UUID
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional
from app.models.order import OrderStatus


class CounterOrderItemResponse(BaseModel):
    id: UUID
    item_name: str
    variant_name: Optional[str] = None
    quantity: int
    item_price: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class CounterOrderResponse(BaseModel):
    id: UUID
    daily_order_number: int
    order_date: Optional[date] = None
    customer_phone: Optional[str] = None
    status: OrderStatus
    total_amount: Decimal
    special_notes: Optional[str] = None
    created_at: datetime
    order_type: str = "pickup"
    delivery_address: Optional[str] = None
    delivery_landmark: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None
    delivery_fee: Decimal = Decimal("0")
    rider_id: Optional[UUID] = None
    rider_name: Optional[str] = None
    rider_phone: Optional[str] = None
    payment_method: str
    payment_status: str
    items: List[CounterOrderItemResponse]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_serializer('order_date')
    def serialize_order_date(self, order_date: Optional[date], _info):
        return order_date.isoformat() if order_date else None

    @field_serializer('delivery_lat', 'delivery_lng')
    def serialize_floats(self, value: Optional[Decimal], _info):
        return float(value) if value is not None else None