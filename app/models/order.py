import uuid
from sqlalchemy import (
    Column, String, Text, Numeric, Integer, DateTime, func,
    ForeignKey, Enum as SAEnum, Date, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
import enum


class OrderStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    AWAITING_PAYMENT_AT_COUNTER = "awaiting_payment_at_counter"
    PENDING_ACCEPTANCE = "pending_acceptance"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CASH_PENDING = "cash_pending"
    CASH_RECEIVED = "cash_received"
    PENDING_REFUND = "pending_refund"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    MOMO = "momo"
    CASH = "cash"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    daily_order_number = Column(Integer, nullable=False)
    order_date = Column(Date, nullable=False)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING_PAYMENT, nullable=False)
    order_type = Column(String(20), default="pickup")
    payment_method = Column(SAEnum(PaymentMethod), nullable=False)
    payment_status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_reference = Column(String(100), nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    special_notes = Column(Text, nullable=True)

    # Delivery fields
    delivery_address = Column(Text, nullable=True)
    delivery_landmark = Column(String(255), nullable=True)
    delivery_lat = Column(Numeric(10, 7), nullable=True)   # NEW — GPS latitude
    delivery_lng = Column(Numeric(10, 7), nullable=True)   # NEW — GPS longitude
    delivery_fee = Column(Numeric(10, 2), default=0, server_default="0", nullable=False)
    rider_id = Column(UUID(as_uuid=True), ForeignKey("riders.id"), nullable=True)
    rider_name = Column(String(100), nullable=True)
    rider_phone = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    customer = relationship("Customer", backref="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("order_date", "daily_order_number", name="uq_order_date_number"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(UUID(as_uuid=True), ForeignKey("menu_items.id"), nullable=True)
    item_name = Column(String(150), nullable=False)
    variant_name = Column(String(100), nullable=True)
    item_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    menu_item = relationship("MenuItem")