import uuid
from sqlalchemy import Column, String, Text, Numeric, Boolean, Integer, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    discount_price = Column(Numeric(10, 2), nullable=True)   # NEW
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("Category", back_populates="menu_items")
    variants = relationship(
        "MenuItemVariant",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        order_by="MenuItemVariant.sort_order",
    )

    @property
    def effective_price(self):
        """Return discount price if set and valid, else full price."""
        if self.discount_price is not None and self.discount_price > 0:
            return self.discount_price
        return self.price