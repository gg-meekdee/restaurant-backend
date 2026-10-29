from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.rider import Rider
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.refresh_token import RefreshToken
from app.services.otp import send_otp, verify_otp
from app.schemas.rider import (
    OTPRequest,
    OTPVerify,
    RiderProfile,
    RefreshRequest,
    rider_to_profile,
)
from app.api.dependencies import get_current_rider
from app.services.websocket import manager

router = APIRouter(prefix="/api/rider", tags=["rider"])


@router.get("/test")
async def test_endpoint():
    print("[DEBUG] Test endpoint called")
    return {"status": "ok", "message": "Rider router is working"}


@router.post("/otp/request")
async def request_otp(payload: OTPRequest):
    phone = payload.phone_number
    print(f"[DEBUG] DEV_MODE={settings.DEV_MODE}, DEV_OTP_CODE={settings.DEV_OTP_CODE}")
    sent = await send_otp(phone)
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Could not send OTP. Please try again.",
        )
    return {"message": "OTP sent successfully"}


@router.post("/otp/verify")
async def verify_otp_endpoint(payload: OTPVerify, db: AsyncSession = Depends(get_db)):
    phone = payload.phone_number
    is_valid = await verify_otp(phone, payload.otp)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    result = await db.execute(select(Rider).where(Rider.phone == phone))
    rider = result.scalar_one_or_none()
    if not rider:
        raise HTTPException(status_code=404, detail="Rider not found. Please contact admin.")
    if not rider.is_active:
        raise HTTPException(status_code=403, detail="Rider account is inactive")

    access_token = create_access_token(data={"sub": str(rider.id), "role": "rider"})
    refresh_token_value = create_refresh_token(data={"sub": str(rider.id), "role": "rider"})

    expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    rt = RefreshToken(
        rider_id=rider.id,
        token=refresh_token_value,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
        "rider": rider_to_profile(rider).model_dump(mode="json"),
    }


@router.post("/token/refresh")
async def refresh_token_endpoint(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        decode_refresh_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == payload.refresh_token)
    )
    rt = result.scalar_one_or_none()
    if not rt or rt.revoked or rt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    rider_result = await db.execute(select(Rider).where(Rider.id == rt.rider_id))
    rider = rider_result.scalar_one_or_none()
    if not rider:
        raise HTTPException(status_code=401, detail="Rider not found")

    new_access = create_access_token(data={"sub": str(rider.id), "role": "rider"})
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "rider": rider_to_profile(rider).model_dump(mode="json"),
    }


@router.post("/logout")
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == payload.refresh_token)
    )
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
        await db.commit()


@router.get("/orders")
async def get_rider_orders(
    current_rider: Rider = Depends(get_current_rider),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(
            and_(
                Order.rider_id == current_rider.id,
                Order.status.in_([OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]),
            )
        )
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


@router.post("/orders/{order_id}/delivered")
async def mark_delivered(
    order_id: str,
    current_rider: Rider = Depends(get_current_rider),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.rider_id != current_rider.id:
        raise HTTPException(status_code=403, detail="Order not assigned to this rider")
    if order.status != OrderStatus.OUT_FOR_DELIVERY:
        raise HTTPException(status_code=400, detail="Order is not out for delivery")

    order.status = OrderStatus.DELIVERED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Order marked as delivered"}


@router.post("/orders/{order_id}/confirm-cash")
async def confirm_cash(
    order_id: str,
    current_rider: Rider = Depends(get_current_rider),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.customer))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.rider_id != current_rider.id:
        raise HTTPException(status_code=403, detail="Order not assigned to this rider")
    if order.payment_method.value != "cash":
        raise HTTPException(status_code=400, detail="Not a cash order")
    if order.status not in (OrderStatus.DELIVERED, OrderStatus.READY):
        raise HTTPException(status_code=400, detail="Order is not ready for cash confirmation")

    order.payment_status = PaymentStatus.CASH_RECEIVED
    if order.status == OrderStatus.DELIVERED:
        order.status = OrderStatus.COMPLETED
    await db.commit()
    await manager.broadcast({"type": "refresh"})
    return {"message": "Cash confirmed"}
