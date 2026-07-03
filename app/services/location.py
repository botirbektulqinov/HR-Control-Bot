"""Joylashuvni tekshirish + anti-spoofing.

HALOL CHEKLOV: Telegram orqali root/emulyator qilingan qurilmadagi fake-GPS'ni
100% aniqlab bo'lmaydi — Telegram "haqiqiy GPS"ni belgilab bermaydi. Quyidagilar
amaliy himoya qatlamlari: geofence + eskirgan/forward joylashuvni rad etish +
aniqlik (accuracy) tekshiruvi + live-location'ni afzal ko'rish. Strictlik darajasi
soxta punktni qiyinlashtiradi, lekin mukammal kafolat bermaydi. Kuchliroq kerak
bo'lsa: selfie tasdiq, IP-geolokatsiya, admin tasdiq oqimi.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from aiogram.types import Message

from app.services.geo import haversine_m


@dataclass
class LocationCheck:
    ok: bool
    distance_m: float
    lat: float
    lon: float
    accuracy: float | None
    reason: str | None = None  # rad etilsa sabab kaliti
    warnings: list[str] = field(default_factory=list)


def validate_location(
    message: Message,
    branch_lat: float,
    branch_lon: float,
    radius_m: int,
    *,
    strictness: str = "medium",
    max_age_seconds: int = 120,
) -> LocationCheck:
    loc = message.location
    if loc is None:
        return LocationCheck(False, 0, 0, 0, None, reason="no_location")

    lat, lon = loc.latitude, loc.longitude
    accuracy = loc.horizontal_accuracy
    distance = haversine_m(lat, lon, branch_lat, branch_lon)
    warnings: list[str] = []

    # Forward qilingan joylashuv — boshqa birovnikini ulashgan
    if getattr(message, "forward_origin", None) or getattr(message, "forward_date", None):
        return LocationCheck(False, distance, lat, lon, accuracy,
                             reason="forwarded", warnings=["forwarded"])

    # Eskirgan joylashuv (screenshot/qayta yuborish)
    now = dt.datetime.now(dt.timezone.utc)
    age = (now - message.date).total_seconds()
    if age > max_age_seconds:
        warnings.append(f"stale:{int(age)}s")
        if strictness in ("strict", "medium"):
            return LocationCheck(False, distance, lat, lon, accuracy,
                                 reason="stale", warnings=warnings)

    # Live-location afzal (uzluksiz — bir martalik soxta pinni qiyinlashtiradi)
    is_live = bool(getattr(loc, "live_period", None))
    if not is_live:
        warnings.append("not_live")
        if strictness == "strict":
            return LocationCheck(False, distance, lat, lon, accuracy,
                                 reason="need_live", warnings=warnings)

    # Aniqlik juda past bo'lsa (spoof yoki zaif signal)
    if accuracy is not None and accuracy > 200:
        warnings.append(f"low_accuracy:{int(accuracy)}m")

    if distance > radius_m:
        return LocationCheck(False, distance, lat, lon, accuracy,
                             reason="outside_radius", warnings=warnings)

    return LocationCheck(True, distance, lat, lon, accuracy, warnings=warnings)
