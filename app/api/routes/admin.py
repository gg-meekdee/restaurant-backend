from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import date as date_type

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.admin import Admin
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.menu_item_variant import MenuItemVariant
from app.models.order import Order, OrderItem, OrderStatus
from app.models.setting import Setting
from app.schemas.admin import AdminLogin
from app.schemas.order import OrderResponse
from app.api.dependencies import get_current_admin
from app.services.settings import is_auto_accept_enabled
from app.services.websocket import manager
import os
import uuid as uuid_lib
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- Login ----------
@router.post("/login")
async def login(payload: AdminLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.username == payload.username))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(data={"sub": str(admin.id), "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


# ---------- Order Management ----------
@router.get("/orders", response_model=List[OrderResponse])
async def list_all_orders(
    order_date: Optional[date_type] = None,
    status: Optional[OrderStatus] = None,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    query = (
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .order_by(Order.daily_order_number.desc())
    )
    if order_date:
        query = query.where(Order.order_date == order_date)
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query)
    orders = result.scalars().all()
    return orders


@router.get("/orders/summary")
async def get_daily_summary(
    order_date: Optional[date_type] = None,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    if order_date is None:
        order_date = date_type.today()

    result = await db.execute(
        select(Order).where(Order.order_date == order_date)
    )
    orders = result.scalars().all()

    total_orders = len(orders)
    total_revenue = sum(
        float(o.total_amount) for o in orders
        if o.status != OrderStatus.CANCELLED
    )
    completed = sum(1 for o in orders if o.status == OrderStatus.COMPLETED)
    cancelled = sum(1 for o in orders if o.status == OrderStatus.CANCELLED)
    active = total_orders - completed - cancelled

    return {
        "order_date": str(order_date),
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "completed_orders": completed,
        "cancelled_orders": cancelled,
        "active_orders": active,
    }


@router.post("/orders/{order_id}/accept")
async def accept_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PENDING_ACCEPTANCE:
        raise HTTPException(status_code=400, detail="Order is not pending acceptance")
    order.status = OrderStatus.ACCEPTED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order accepted"}


@router.post("/orders/{order_id}/complete")
async def complete_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot complete a cancelled order")
    order.status = OrderStatus.COMPLETED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order marked as completed"}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == OrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot cancel a completed order")
    order.status = OrderStatus.CANCELLED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order cancelled"}


# ---------- Category Schemas ----------
class CategoryCreate(BaseModel):
    name: str
    sort_order: int = 0
    image_url: Optional[str] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    image_url: Optional[str] = None


# ---------- Category CRUD ----------
@router.get("/menu/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.menu_items).selectinload(MenuItem.variants))
        .order_by(Category.sort_order)
    )
    categories = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "sort_order": c.sort_order,
                                     "items": [
                {
                    "id": str(i.id),
                    "name": i.name,
                    "description": i.description,
                    "price": float(i.price),
                    "discount_price": float(i.discount_price) if i.discount_price else None,
                    "is_available": i.is_available,
                    "image_url": i.image_url,
                    "sort_order": i.sort_order,
                    "variants": [
                        {
                            "id": str(v.id),
                            "name": v.name,
                            "description": v.description,
                            "price": float(v.price),
                            "discount_price": float(v.discount_price) if v.discount_price else None,
                            "image_url": v.image_url,
                            "is_available": v.is_available,
                            "sort_order": v.sort_order,
                        }
                        for v in sorted(i.variants, key=lambda x: x.sort_order or 0)
                    ],
                }
                for i in sorted(c.menu_items, key=lambda x: x.sort_order or 0)
            ],
        }
        for c in categories
    ]


@router.post("/menu/categories")
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    category = Category(
        name=payload.name,
        sort_order=payload.sort_order,
        image_url=payload.image_url,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return {
        "id": str(category.id),
        "name": category.name,
        "sort_order": category.sort_order,
        "image_url": category.image_url,
        "items": [],
    }


@router.put("/menu/categories/{category_id}")
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if payload.name is not None:
        category.name = payload.name
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.image_url is not None:
        category.image_url = payload.image_url
    await db.commit()
    await db.refresh(category)
    return {"message": "Category updated"}


@router.delete("/menu/categories/{category_id}")
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.menu_items))
        .where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for item in category.menu_items:
        await db.execute(
            update(OrderItem)
            .where(OrderItem.menu_item_id == item.id)
            .values(menu_item_id=None)
        )
        await db.delete(item)

    await db.delete(category)
    await db.commit()
    return {"message": "Category and its items deleted"}


# ---------- Menu Item Schemas ----------
class VariantIn(BaseModel):
    id: Optional[UUID] = None  # present for existing variants, null for new ones
    name: str
    description: Optional[str] = None
    price: float
    discount_price: Optional[float] = None
    image_url: Optional[str] = None
    is_available: bool = True
    sort_order: int = 0


class MenuItemCreate(BaseModel):
    category_id: UUID
    name: str
    description: Optional[str] = None
    price: float
    discount_price: Optional[float] = None
    image_url: Optional[str] = None
    is_available: bool = True
    sort_order: int = 0
    variants: List[VariantIn] = []


class MenuItemUpdate(BaseModel):
    category_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    sort_order: Optional[int] = None
    variants: Optional[List[VariantIn]] = None  # if provided, replaces all variants


# ---------- Menu Item CRUD ----------
@router.post("/menu/items")
async def create_menu_item(
    payload: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    item = MenuItem(
        category_id=payload.category_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        discount_price=payload.discount_price,
        image_url=payload.image_url,
        is_available=payload.is_available,
        sort_order=payload.sort_order,
    )
    db.add(item)
    await db.flush()

    for v in payload.variants:
        db.add(MenuItemVariant(
            menu_item_id=item.id,
            name=v.name,
            description=v.description,
            price=v.price,
            discount_price=v.discount_price,
            image_url=v.image_url,
            is_available=v.is_available,
            sort_order=v.sort_order,
        ))

    await db.commit()
    await db.refresh(item)
    return {"message": "Item created", "id": str(item.id)}


@router.put("/menu/items/{item_id}")
async def update_menu_item(
    item_id: UUID,
    payload: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(
        select(MenuItem)
        .options(selectinload(MenuItem.variants))
        .where(MenuItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    update_data = payload.model_dump(exclude_unset=True, exclude={"variants"})
    for field, value in update_data.items():
        if field == "discount_price":
            item.discount_price = value
        elif value is not None:
            setattr(item, field, value)

    # Replace variants if provided
    if payload.variants is not None:
        # Delete existing variants (safe because orders snapshot variant_name)
        for v in list(item.variants):
            await db.delete(v)
        await db.flush()

        for v in payload.variants:
            db.add(MenuItemVariant(
                menu_item_id=item.id,
                name=v.name,
                description=v.description,
                price=v.price,
                discount_price=v.discount_price,
                image_url=v.image_url,
                is_available=v.is_available,
                sort_order=v.sort_order,
            ))

    await db.commit()
    await db.refresh(item)
    return {"message": "Item updated"}


@router.delete("/menu/items/{item_id}")
async def delete_menu_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    result = await db.execute(
        select(MenuItem)
        .options(selectinload(MenuItem.variants))
        .where(MenuItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Detach from any past orders
    await db.execute(
        update(OrderItem)
        .where(OrderItem.menu_item_id == item_id)
        .values(menu_item_id=None)
    )

    # Delete variants (cascade should handle it, but be explicit)
    for v in list(item.variants):
        await db.delete(v)

    await db.delete(item)
    await db.commit()
    return {"message": "Item deleted"}

    # ---------- Image Upload ----------
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    _: Admin = Depends(get_current_admin),
):
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Generate a unique filename
    filename = f"{uuid_lib.uuid4().hex}{ext}"
    filepath = os.path.join("uploads", filename)

    # Save
    with open(filepath, "wb") as f:
        f.write(contents)

    # Return public URL
    return {
        "url": f"/uploads/{filename}",
        "filename": filename,
    }