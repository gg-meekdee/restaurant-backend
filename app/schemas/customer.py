from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Optional
import re


GHANA_PHONE_REGEX = re.compile(
    r"^(\+233|0)(20|50|23|24|54|55|59|26|56|27|57|28)[0-9]{7}$"
)


def validate_ghana_phone(value: str) -> str:
    """Strip spaces/dashes and validate Ghana phone number."""
    cleaned = re.sub(r"[\s\-]", "", value)
    if not GHANA_PHONE_REGEX.match(cleaned):
        raise ValueError("Enter a valid Ghana phone number (e.g., 0244859930)")
    return cleaned


class OTPRequest(BaseModel):
    phone_number: str = Field(
        ...,
        description="Ghana phone number",
        min_length=10,
        max_length=13,
    )

    @field_validator("phone_number")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return validate_ghana_phone(v)


class OTPVerify(BaseModel):
    phone_number: str = Field(
        ...,
        description="The same Ghana phone number used to request the OTP",
    )
    otp: str = Field(
        ...,
        description="The 6-digit code sent via SMS",
        min_length=6,
        max_length=6,
    )

    @field_validator("phone_number")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return validate_ghana_phone(v)


class CustomerProfile(BaseModel):
    id: UUID
    phone_number: str
    name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    marketing_opt_in: bool = False
    profile_complete: bool = False

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Customer's display name",
        min_length=1,
        max_length=100,
    )
    whatsapp_number: Optional[str] = Field(
        None,
        description="WhatsApp number for receiving deals",
    )
    marketing_opt_in: Optional[bool] = Field(
        None,
        description="True if customer wants to receive deals",
    )

    @field_validator("whatsapp_number")
    @classmethod
    def check_whatsapp(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return validate_ghana_phone(v)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="The refresh token issued at login")


def customer_to_profile(customer) -> CustomerProfile:
    return CustomerProfile(
        id=customer.id,
        phone_number=customer.phone_number,
        name=customer.name,
        whatsapp_number=customer.whatsapp_number,
        marketing_opt_in=customer.marketing_opt_in or False,
        profile_complete=bool(customer.name),
    )