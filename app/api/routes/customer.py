from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.customer import Customer
from app.models.refresh_token import RefreshToken
from app.services.otp import send_otp, verify_otp
from app.schemas.customer import (
    OTPRequest,
    OTPVerify,
    CustomerProfile,
    ProfileUpdate,
    RefreshRequest,
    customer_to_profile,
)
from app.api.dependencies import get_current_customer

router = APIRouter(prefix="/api/customer", tags=["customer"])


@router.post("/otp/request")
async def request_otp(payload: OTPRequest):
    phone = payload.phone_number
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

    result = await db.execute(select(Customer).where(Customer.phone_number == phone))
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(phone_number=phone)
        db.add(customer)
        await db.commit()
        await db.refresh(customer)

    access_token = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    refresh_token_value = create_refresh_token(data={"sub": str(customer.id), "role": "customer"})

    expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    rt = RefreshToken(
        customer_id=customer.id,
        token=refresh_token_value,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
        "customer": customer_to_profile(customer).model_dump(mode="json"),
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

    customer_result = await db.execute(select(Customer).where(Customer.id == rt.customer_id))
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=401, detail="Customer not found")

    new_access = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "customer": customer_to_profile(customer).model_dump(mode="json"),
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
    return {"message": "Logged out"}


@router.get("/profile", response_model=CustomerProfile)
async def get_profile(current_customer: Customer = Depends(get_current_customer)):
    return customer_to_profile(current_customer)


@router.put("/profile", response_model=CustomerProfile)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    if payload.name is not None:
        current_customer.name = payload.name
    if payload.whatsapp_number is not None:
        current_customer.whatsapp_number = payload.whatsapp_number
    if payload.marketing_opt_in is not None:
        current_customer.marketing_opt_in = payload.marketing_opt_in
    await db.commit()
    await db.refresh(current_customer)
    return customer_to_profile(current_customer)