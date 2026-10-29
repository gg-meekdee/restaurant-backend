from pydantic import BaseModel, Field, field_validator
from app.schemas.customer import validate_ghana_phone


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


class RiderProfile(BaseModel):
    id: str
    name: str
    phone: str
    rider_type: str
    is_active: bool

    model_config = {"from_attributes": True}


def rider_to_profile(rider) -> RiderProfile:
    return RiderProfile(
        id=str(rider.id),
        name=rider.name,
        phone=rider.phone,
        rider_type=rider.rider_type.value,
        is_active=rider.is_active,
    )


class RefreshRequest(BaseModel):
    refresh_token: str
