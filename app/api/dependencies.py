from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.customer import Customer
from app.models.admin import Admin

bearer_scheme = HTTPBearer()


# ---------- Customer auth ----------
async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> Customer:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        customer_id: str = payload.get("sub")
        if customer_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise credentials_exception
    return customer


# ---------- Admin auth ----------
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> Admin:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        admin_id: str = payload.get("sub")
        role: str = payload.get("role")
        if admin_id is None or role != "admin":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise credentials_exception
    return admin