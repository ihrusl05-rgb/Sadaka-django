from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class NamazServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class NamazLocation:
    city: str
    region: str
    country: str
    country_code: str
    lat: float
    lon: float
    label: str
    description: str


HIJRI_MONTHS_RU = {
    1: "Мухаррам",
    2: "Сафар",
    3: "Раби аль-авваль",
    4: "Раби ас-сани",
    5: "Джумада аль-уля",
    6: "Джумада ас-сания",
    7: "Раджаб",
    8: "Шаабан",
    9: "Рамадан",
    10: "Шавваль",
    11: "Зуль-каада",
    12: "Зуль-хиджа",
}

GREGORIAN_MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

GREGORIAN_MONTHS_NOMINATIVE_RU = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

WEEKDAYS_RU_SHORT = {
    0: "пн",
    1: "вт",
    2: "ср",
    3: "чт",
    4: "пт",
    5: "сб",
    6: "вс",
}

NOTABLE_DATES = (
    {"month": 1, "day": 1, "title": "Новый год по хиджре", "note": "Начало месяца Мухаррам"},
    {"month": 1, "day": 10, "title": "День Ашура", "note": "10-й день месяца Мухаррам"},
    {"month": 3, "day": 12, "title": "Маулид ан-Наби", "note": "Рождение Пророка Мухаммада"},
    {"month": 7, "day": 27, "title": "Исра и Мирадж", "note": "Ночь вознесения Пророка"},
    {"month": 8, "day": 15, "title": "Ночь Бараат", "note": "Середина месяца Шаабан"},
    {"month": 9, "day": 1, "title": "Начало Рамадана", "note": "Первый день обязательного поста"},
    {"month": 9, "day": 27, "title": "Ляйлятуль-Кадр", "note": "Ночь могущества"},
    {"month": 10, "day": 1, "title": "Ураза-байрам", "note": "Праздник разговения"},
    {"month": 12, "day": 9, "title": "День Арафа", "note": "Особый день дуа и поклонения"},
    {"month": 12, "day": 10, "title": "Курбан-байрам", "note": "Праздник жертвоприношения"},
)

MAKKAH_COORDS = {"latitude": 21.4225, "longitude": 39.8262}


def _user_agent() -> str:
    app_url = (getattr(settings, "APP_BASE_URL", "") or "").strip() or "http://localhost"
    return f"SadakaJariya/1.0 (+{app_url})"


def _load_json(*, url: str, params: dict[str, object] | None = None, timeout: int = 10):
    query = urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    target_url = f"{url}?{query}" if query else url
    request = Request(
        target_url,
        headers={
            "Accept": "application/json",
            "User-Agent": _user_agent(),
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        logger.exception("Unable to load namaz remote payload", extra={"url": url})
        raise NamazServiceError("Unable to load namaz remote payload.") from exc
    return payload


def _parse_location(item: dict) -> NamazLocation | None:
    address = item.get("address") or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or item.get("name")
        or ""
    ).strip()
    if not city:
        return None
    region = (address.get("state") or address.get("region") or address.get("county") or "").strip()
    country = (address.get("country") or "").strip()
    country_code = (address.get("country_code") or "").strip().upper()
    label_parts = [city]
    if region and region.lower() != city.lower():
        label_parts.append(region)
    label = ", ".join(label_parts)
    return NamazLocation(
        city=city,
        region=region,
        country=country,
        country_code=country_code,
        lat=float(item.get("lat") or 0),
        lon=float(item.get("lon") or 0),
        label=label,
        description=str(item.get("display_name") or label),
    )


def search_locations(*, query: str, limit: int = 6) -> list[dict]:
    normalized_query = (query or "").strip()
    if len(normalized_query) < 2:
        return []
    payload = _load_json(
        url="https://nominatim.openstreetmap.org/search",
        params={
            "q": normalized_query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": max(1, min(limit, 8)),
            "accept-language": "ru",
        },
    )
    results = payload if isinstance(payload, list) else []
    normalized_results: list[dict] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        location = _parse_location(item)
        if location is None:
            continue
        normalized_results.append(
            {
                "city": location.city,
                "region": location.region,
                "country": location.country,
                "country_code": location.country_code,
                "lat": location.lat,
                "lon": location.lon,
                "label": location.label,
                "description": location.description,
            }
        )
    return normalized_results


def reverse_location(*, lat: float, lon: float) -> dict:
    payload = _load_json(
        url="https://nominatim.openstreetmap.org/reverse",
        params={
            "format": "jsonv2",
            "addressdetails": 1,
            "lat": lat,
            "lon": lon,
            "accept-language": "ru",
        },
    )
    if not isinstance(payload, dict):
        raise NamazServiceError("Unexpected reverse geocoding payload.")
    location = _parse_location(payload)
    if location is None:
        raise NamazServiceError("Unable to resolve city from coordinates.")
    return {
        "city": location.city,
        "region": location.region,
        "country": location.country,
        "country_code": location.country_code,
        "lat": location.lat,
        "lon": location.lon,
        "label": location.label,
        "description": location.description,
    }


def _format_gregorian(day: dict) -> tuple[str, tuple[int, int, int]]:
    gregorian = (day.get("date") or {}).get("gregorian") or {}
    day_value = int(gregorian.get("day") or 0)
    month_value = int((gregorian.get("month") or {}).get("number") or 0)
    year_value = int(gregorian.get("year") or 0)
    return (
        f"{day_value} {GREGORIAN_MONTHS_RU.get(month_value, '')} {year_value}".strip(),
        (year_value, month_value, day_value),
    )


def _format_hijri(day: dict) -> str:
    hijri = (day.get("date") or {}).get("hijri") or {}
    day_value = int(hijri.get("day") or 0)
    month_value = int((hijri.get("month") or {}).get("number") or 0)
    year_value = hijri.get("year") or ""
    return f"{day_value} {HIJRI_MONTHS_RU.get(month_value, '')} {year_value}".strip()


def _normalize_timing(value: str) -> str:
    return str(value or "").split(" ")[0].strip()


def _build_month_schedule(*, lat: float, lon: float, year: int, month: int) -> dict:
    payload = _load_json(
        url=f"https://api.aladhan.com/v1/calendar/{year}/{month}",
        params={
            "latitude": lat,
            "longitude": lon,
            "method": 14,
            "school": 1,
        },
    )
    days = payload.get("data") or []
    if not isinstance(days, list):
        raise NamazServiceError("Unexpected monthly prayer calendar payload.")

    rows: list[dict] = []
    for item in days:
        if not isinstance(item, dict):
            continue
        timings = item.get("timings") or {}
        _, sort_key = _format_gregorian(item)
        try:
            weekday_label = WEEKDAYS_RU_SHORT[datetime(sort_key[0], sort_key[1], sort_key[2]).weekday()]
        except Exception:
            weekday_label = ""
        rows.append(
            {
                "day": sort_key[2],
                "weekday": weekday_label,
                "fajr": _normalize_timing(timings.get("Fajr", "")),
                "sunrise": _normalize_timing(timings.get("Sunrise", "")),
                "dhuhr": _normalize_timing(timings.get("Dhuhr", "")),
                "asr": _normalize_timing(timings.get("Asr", "")),
                "maghrib": _normalize_timing(timings.get("Maghrib", "")),
                "isha": _normalize_timing(timings.get("Isha", "")),
                "gregorian": _format_gregorian(item)[0],
                "hijri": _format_hijri(item),
            }
        )

    return {
        "month": GREGORIAN_MONTHS_NOMINATIVE_RU.get(month, ""),
        "year": year,
        "rows": rows,
    }


def _compute_next_prayer(*, timings: dict[str, str], timezone_name: str) -> dict | None:
    prayer_order = (
        ("Fajr", "Фаджр"),
        ("Sunrise", "Восход"),
        ("Dhuhr", "Зухр"),
        ("Asr", "Аср"),
        ("Maghrib", "Магриб"),
        ("Isha", "Иша"),
    )
    try:
        now = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        now = timezone.localtime()

    current_minutes = now.hour * 60 + now.minute
    fallback: dict | None = None
    for key, label in prayer_order:
        normalized = _normalize_timing(timings.get(key, ""))
        if fallback is None and normalized:
            fallback = {"key": key, "label": label, "time": normalized}
        try:
            hours, minutes = [int(part) for part in normalized.split(":", 1)]
        except (TypeError, ValueError):
            continue
        if hours * 60 + minutes > current_minutes:
            return {"key": key, "label": label, "time": normalized}
    return fallback


@lru_cache(maxsize=24)
def _calendar_month(year: int, month: int) -> tuple[dict, ...]:
    payload = _load_json(
        url=f"https://api.aladhan.com/v1/calendar/{year}/{month}",
        params={
            "latitude": MAKKAH_COORDS["latitude"],
            "longitude": MAKKAH_COORDS["longitude"],
            "method": 14,
            "school": 1,
        },
    )
    data = payload.get("data") or []
    return tuple(item for item in data if isinstance(item, dict))


@lru_cache(maxsize=8)
def get_notable_dates(*, gregorian_year: int) -> list[dict]:
    days: list[dict] = []
    for month in range(1, 13):
        days.extend(_calendar_month(gregorian_year, month))

    notable: list[dict] = []
    for event in NOTABLE_DATES:
        match = None
        for day in days:
            hijri = (day.get("date") or {}).get("hijri") or {}
            hijri_day = int(hijri.get("day") or 0)
            hijri_month = int((hijri.get("month") or {}).get("number") or 0)
            if hijri_day == event["day"] and hijri_month == event["month"]:
                match = day
                break
        if match is None:
            continue
        gregorian_label, sort_key = _format_gregorian(match)
        notable.append(
            {
                "title": event["title"],
                "note": event["note"],
                "gregorian": gregorian_label,
                "hijri": _format_hijri(match),
                "sort_key": sort_key,
            }
        )
    notable.sort(key=lambda item: item["sort_key"])
    return notable


def get_namaz_payload(
    *,
    lat: float,
    lon: float,
    city: str = "",
    region: str = "",
    country: str = "",
    country_code: str = "",
) -> dict:
    today = timezone.localdate()
    location: dict
    if city:
        normalized_region = (region or "").strip()
        label_parts = [city.strip()]
        if normalized_region and normalized_region.lower() != city.strip().lower():
            label_parts.append(normalized_region)
        location = {
            "city": city.strip(),
            "region": normalized_region,
            "country": (country or "").strip(),
            "country_code": (country_code or "").strip().upper(),
            "lat": lat,
            "lon": lon,
            "label": ", ".join(label_parts),
        }
    else:
        location = reverse_location(lat=lat, lon=lon)

    prayer_payload = _load_json(
        url="https://api.aladhan.com/v1/timings",
        params={
            "latitude": lat,
            "longitude": lon,
            "method": 14,
            "school": 1,
        },
    )
    data = prayer_payload.get("data") or {}
    if not isinstance(data, dict):
        raise NamazServiceError("Unexpected prayer timings payload.")
    date_payload = data.get("date") or {}
    hijri_payload = date_payload.get("hijri") or {}
    gregorian_payload = date_payload.get("gregorian") or {}
    gregorian_year = int(gregorian_payload.get("year") or timezone.localdate().year)
    try:
        calendar = get_notable_dates(gregorian_year=gregorian_year)
    except NamazServiceError:
        logger.exception("Unable to load notable namaz dates", extra={"gregorian_year": gregorian_year})
        calendar = []
    upcoming_calendar = [
        item for item in calendar if tuple(item.get("sort_key") or ()) >= (today.year, today.month, today.day)
    ]
    calendar = [
        {
            "title": item.get("title", ""),
            "note": item.get("note", ""),
            "gregorian": item.get("gregorian", ""),
            "hijri": item.get("hijri", ""),
        }
        for item in (upcoming_calendar or calendar)[:3]
    ]

    gregorian_month = int((gregorian_payload.get("month") or {}).get("number") or timezone.localdate().month)
    try:
        month_schedule = _build_month_schedule(
            lat=lat,
            lon=lon,
            year=gregorian_year,
            month=gregorian_month,
        )
    except NamazServiceError:
        logger.exception(
            "Unable to load monthly namaz schedule",
            extra={"lat": lat, "lon": lon, "gregorian_year": gregorian_year, "gregorian_month": gregorian_month},
        )
        month_schedule = {"month": GREGORIAN_MONTHS_NOMINATIVE_RU.get(gregorian_month, ""), "year": gregorian_year, "rows": []}

    timings = data.get("timings") or {}
    filtered_timings = {
        "Fajr": timings.get("Fajr", ""),
        "Sunrise": timings.get("Sunrise", ""),
        "Dhuhr": timings.get("Dhuhr", ""),
        "Asr": timings.get("Asr", ""),
        "Maghrib": timings.get("Maghrib", ""),
        "Isha": timings.get("Isha", ""),
    }
    timezone_name = ((data.get("meta") or {}).get("timezone") or "")
    return {
        "location": location,
        "timezone": timezone_name,
        "timings": filtered_timings,
        "gregorian_date": f"{gregorian_payload.get('day', '')} {GREGORIAN_MONTHS_RU.get(int((gregorian_payload.get('month') or {}).get('number') or 0), '')} {gregorian_payload.get('year', '')}".strip(),
        "hijri_date": f"{hijri_payload.get('day', '')} {HIJRI_MONTHS_RU.get(int((hijri_payload.get('month') or {}).get('number') or 0), '')} {hijri_payload.get('year', '')}".strip(),
        "hijri_year": int(hijri_payload.get("year") or 0) or None,
        "next_prayer": _compute_next_prayer(timings=filtered_timings, timezone_name=timezone_name),
        "calendar": calendar,
        "month_schedule": month_schedule,
    }
