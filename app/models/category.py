import uuid
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0)
    image_url = Column(String(500), nullable=True)   # <-- ensure this exists
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    menu_items = relationship("MenuItem", back_populates="category")