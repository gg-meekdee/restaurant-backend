import uuid
from sqlalchemy import Column, String, Numeric, Boolean, Integer, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class MenuItemExtra(Base):
    __tablename__ = "menu_item_extras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    is_available = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    menu_item = relationship("MenuItem")
