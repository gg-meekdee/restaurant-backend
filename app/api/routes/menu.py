from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.category import Category
from app.models.menu_item import MenuItem

router = APIRouter(prefix="/api", tags=["menu"])


@router.get("/menu")
async def get_menu(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.menu_items).selectinload(MenuItem.variants))
        .order_by(Category.sort_order)
    )
    categories = result.scalars().unique().all()

    response = []
    for cat in categories:
        available_items = [i for i in cat.menu_items if i.is_available]
        if not available_items:
            continue
        response.append({
            "id": str(cat.id),
            "name": cat.name,
            "sort_order": cat.sort_order,
            "items": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "description": item.description,
                    "price": float(item.price),
                    "discount_price": float(item.discount_price) if item.discount_price else None,
                    "image_url": item.image_url,
                    "variants": [
                        {
                            "id": str(v.id),
                            "name": v.name,
                            "description": v.description,
                            "price": float(v.price),
                            "discount_price": float(v.discount_price) if v.discount_price else None,
                            "image_url": v.image_url,
                            "is_available": v.is_available,
                        }
                        for v in sorted(
                            [vv for vv in item.variants if vv.is_available],
                            key=lambda x: x.sort_order or 0,
                        )
                    ],
                }
                for item in available_items
            ],
        })
    return response