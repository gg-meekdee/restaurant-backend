import re
import httpx
from app.core.config import settings


def normalize_ghana_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s\-]", "", phone)
    if cleaned.startswith("+233"):
        return cleaned[1:]
    if cleaned.startswith("233"):
        return cleaned
    if cleaned.startswith("0"):
        return "233" + cleaned[1:]
    return cleaned


async def send_otp(phone_number: str) -> bool:
    api_key = (settings.ARKESEL_API_KEY or "").strip()
    number = normalize_ghana_phone(phone_number)

    if settings.DEV_MODE:
        print(f"[DEV MODE] OTP for {phone_number}: {settings.DEV_OTP_CODE}")
        return True

    if not api_key:
        print(f"[DEV] OTP requested for {phone_number}. Configure ARKESEL_API_KEY to send real SMS.")
        return True

    url = f"{settings.ARKESEL_BASE_URL}/generate"
    payload = {
        "expiry": settings.ARKESEL_OTP_EXPIRY_MINUTES,
        "length": settings.ARKESEL_OTP_LENGTH,
        "medium": "sms",
        "message": "Your %otp_code% is your verification code.",
        "number": number,
        "sender_id": settings.ARKESEL_SENDER_ID,
        "type": "numeric",
    }
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    print(f"[ARKESEL REQUEST] POST {url} | number={number} | sender={settings.ARKESEL_SENDER_ID}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        print(f"[ARKESEL RESPONSE] status={response.status_code}")
        print(f"[ARKESEL RESPONSE] body={response.text!r}")
        print(f"[ARKESEL RESPONSE] headers={dict(response.headers)}")

        try:
            data = response.json()
        except Exception as parse_err:
            print(f"[ARKESEL PARSE ERROR] {type(parse_err).__name__}: {parse_err}")
            return False

        if response.status_code in (200, 201) and str(data.get("code")) in ("2000", "1000"):
            print(f"[ARKESEL] OTP sent to {number}")
            return True

        print(f"[ARKESEL REJECTED] {data}")
        return False

    except Exception as e:
        print(f"[SMS ERROR] type={type(e).__name__} repr={e!r} str={e}")
        return False


async def verify_otp(phone_number: str, code: str) -> bool:
    api_key = (settings.ARKESEL_API_KEY or "").strip()
    number = normalize_ghana_phone(phone_number)

    if settings.DEV_MODE:
        if code == settings.DEV_OTP_CODE:
            print(f"[DEV MODE] OTP verified for {phone_number}")
            return True
        else:
            print(f"[DEV MODE] Invalid OTP for {phone_number}: expected {settings.DEV_OTP_CODE}, got {code}")
            return False

    if not api_key:
        print(f"[DEV] OTP verify for {phone_number} with code {code}.")
        return True

    url = f"{settings.ARKESEL_BASE_URL}/verify"
    payload = {"code": code, "number": number}
    headers = {"api-key": api_key, "Content-Type": "application/json"}

    print(f"[ARKESEL REQUEST] POST {url} | number={number}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        print(f"[ARKESEL RESPONSE] status={response.status_code}")
        print(f"[ARKESEL RESPONSE] body={response.text!r}")

        try:
            data = response.json()
        except Exception as parse_err:
            print(f"[ARKESEL PARSE ERROR] {type(parse_err).__name__}: {parse_err}")
            return False

        if response.status_code in (200, 201) and str(data.get("code")) in ("1100", "1000"):
            print(f"[ARKESEL] OTP verified for {number}")
            return True

        print(f"[ARKESEL VERIFY REJECTED] {data}")
        return False

    except Exception as e:
        print(f"[VERIFY ERROR] type={type(e).__name__} repr={e!r} str={e}")
        return False