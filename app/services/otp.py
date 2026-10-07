import random
import string
from datetime import datetime, timedelta, timezone
import httpx
from app.core.config import settings

otp_store = {}


def generate_otp(phone_number: str) -> str:
    otp = "".join(random.choices(string.digits, k=6))
    otp_store[phone_number] = {
        "otp": otp,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return otp


def verify_otp(phone_number: str, otp: str) -> bool:
    record = otp_store.get(phone_number)
    if not record:
        return False
    if record["expires"] < datetime.now(timezone.utc):
        del otp_store[phone_number]
        return False
    if record["otp"] != otp:
        return False
    del otp_store[phone_number]
    return True


async def send_sms(phone_number: str, otp: str) -> None:
    """
    Sends OTP via Hubtel if credentials look real.
    Otherwise, prints to console. Never crashes.
    """
    client_id = (settings.HUBTEL_CLIENT_ID or "").strip()
    client_secret = (settings.HUBTEL_CLIENT_SECRET or "").strip()

    placeholders = {"", "your_client_id", "your_client_secret", "changeme"}
    if client_id in placeholders or client_secret in placeholders:
        print(f"[DEV] SMS to {phone_number}: Your OTP is {otp}")
        return

    try:
        url = f"{settings.HUBTEL_API_BASE_URL}/v1/messages"
        payload = {
            "from": settings.HUBTEL_SMS_SENDER_ID or "Restaurant",
            "to": phone_number,
            "content": f"Your OTP is {otp}",
        }
        headers = {
            "Authorization": f"Basic {client_id}:{client_secret}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                print(f"[HUBTEL] SMS sent to {phone_number}")
            else:
                print(f"[HUBTEL ERROR] {response.status_code}: {response.text}")
                print(f"[FALLBACK] SMS to {phone_number}: Your OTP is {otp}")
    except Exception as e:
        print(f"[SMS ERROR] {e}")
        print(f"[FALLBACK] SMS to {phone_number}: Your OTP is {otp}")