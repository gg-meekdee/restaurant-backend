import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    whatsapp_number = Column(String(20), nullable=True)
    marketing_opt_in = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())