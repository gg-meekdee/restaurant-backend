import uuid
from sqlalchemy import Column, String, Boolean, DateTime, func, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import enum


class RiderType(str, enum.Enum):
    PERMANENT = "permanent"
    ON_DEMAND = "on_demand"


class Rider(Base):
    __tablename__ = "riders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    rider_type = Column(SAEnum(RiderType), nullable=False, default=RiderType.ON_DEMAND)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())