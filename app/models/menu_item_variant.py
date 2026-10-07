import uuid
from sqlalchemy import Column, String, Text, Numeric, Boolean, Integer, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class MenuItemVariant(Base):
    __tablename__ = "menu_item_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    discount_price = Column(Numeric(10, 2), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    menu_item = relationship("MenuItem", back_populates="variants")

    @property
    def effective_price(self):
        if self.discount_price is not None and self.discount_price > 0:
            return self.discount_price
        return self.price