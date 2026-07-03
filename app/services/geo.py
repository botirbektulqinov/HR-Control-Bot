import math

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ikki nuqta orasidagi masofa (metr)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


if __name__ == "__main__":
    # Toshkent ichida ~ tekshiruv: Amir Temur hiyoboni -> Chorsu ~ 3 km
    d = haversine_m(41.3111, 69.2797, 41.3264, 69.2350)
    assert 3500 < d < 4500, d
    assert haversine_m(41.0, 69.0, 41.0, 69.0) == 0.0
    print("geo ok:", round(d), "m")
