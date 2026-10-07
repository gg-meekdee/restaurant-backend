from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from decimal import Decimal

class MenuItemResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    price: Decimal
    image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)

class CategoryWithItems(BaseModel):
    id: UUID
    name: str
    sort_order: int
    items: list[MenuItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)