import math


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_delivery_fee(
    customer_lat: float,
    customer_lng: float,
    restaurant_lat: float,
    restaurant_lng: float,
    zones: list[dict],
) -> dict:
    """
    Returns { fee, distance_km, zone_index } based on customer's location.
    Zones are sorted by max_km ascending. First zone whose max_km >= distance wins.
    """
    distance = haversine_km(restaurant_lat, restaurant_lng, customer_lat, customer_lng)
    sorted_zones = sorted(zones, key=lambda z: float(z.get("max_km", 999)))

    for i, zone in enumerate(sorted_zones):
        if distance <= float(zone.get("max_km", 999)):
            return {
                "fee": float(zone.get("fee", 20)),
                "distance_km": round(distance, 2),
                "zone_index": i,
            }

    # Fallback to furthest zone
    last = sorted_zones[-1]
    return {
        "fee": float(last.get("fee", 30)),
        "distance_km": round(distance, 2),
        "zone_index": len(sorted_zones) - 1,
    }