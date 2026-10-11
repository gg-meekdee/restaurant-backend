from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.settings import get_restaurant_location, get_delivery_zones
from app.services.delivery import calculate_delivery_fee


router = APIRouter(prefix="/api/delivery", tags=["delivery"])


class QuoteRequest(BaseModel):
    lat: float
    lng: float


@router.post("/quote")
async def delivery_quote(payload: QuoteRequest):
    """
    Public endpoint. Customer's app sends their coordinates.
    Returns fee, distance, and whether delivery is available.
    """
    restaurant_loc = await get_restaurant_location()
    if not restaurant_loc:
        raise HTTPException(
            status_code=400,
            detail="Restaurant location not configured. Delivery unavailable.",
        )

    restaurant_lat, restaurant_lng = restaurant_loc
    zones = await get_delivery_zones()

    result = calculate_delivery_fee(
        customer_lat=payload.lat,
        customer_lng=payload.lng,
        restaurant_lat=restaurant_lat,
        restaurant_lng=restaurant_lng,
        zones=zones,
    )

    return {
        "available": True,
        "fee": result["fee"],
        "distance_km": result["distance_km"],
        "zone_index": result["zone_index"],
    }