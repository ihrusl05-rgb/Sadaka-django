from apps.platform.namaz import get_namaz_payload


def test_get_namaz_payload_builds_calendar_and_next_prayer(monkeypatch):
    def fake_load_json(*, url, params=None, timeout=10):
        if "timings" in url:
            return {
                "data": {
                    "timings": {
                        "Fajr": "02:30 (MSK)",
                        "Sunrise": "04:45 (MSK)",
                        "Dhuhr": "12:25 (MSK)",
                        "Asr": "16:20 (MSK)",
                        "Maghrib": "20:05 (MSK)",
                        "Isha": "22:10 (MSK)",
                    },
                    "date": {
                        "gregorian": {
                            "day": "19",
                            "year": "2026",
                            "month": {"number": 5},
                        },
                        "hijri": {
                            "day": "1",
                            "year": "1447",
                            "month": {"number": 12},
                        },
                    },
                    "meta": {
                        "timezone": "Europe/Moscow",
                    },
                }
            }
        if "calendar" in url:
            return {
                "data": [
                    {
                        "timings": {
                            "Fajr": "02:30 (MSK)",
                            "Sunrise": "04:45 (MSK)",
                            "Dhuhr": "12:25 (MSK)",
                            "Asr": "16:20 (MSK)",
                            "Maghrib": "20:05 (MSK)",
                            "Isha": "22:10 (MSK)",
                        },
                        "date": {
                            "gregorian": {
                                "day": "19",
                                "year": "2026",
                                "month": {"number": 5},
                            },
                            "hijri": {
                                "day": "1",
                                "year": "1447",
                                "month": {"number": 12},
                            },
                        },
                    }
                ]
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("apps.platform.namaz._load_json", fake_load_json)
    monkeypatch.setattr(
        "apps.platform.namaz.get_notable_dates",
        lambda gregorian_year: [
            {
                "title": "Курбан-байрам",
                "note": "Праздник жертвоприношения",
                "gregorian": "27 мая 2026",
                "hijri": "10 Зуль-хиджа 1447",
            }
        ],
    )

    payload = get_namaz_payload(
        lat=55.7946,
        lon=49.1115,
        city="Казань",
        region="Татарстан",
        country="Россия",
        country_code="RU",
    )

    assert payload["location"]["label"] == "Казань, Татарстан"
    assert payload["timezone"] == "Europe/Moscow"
    assert payload["timings"]["Maghrib"] == "20:05 (MSK)"
    assert payload["gregorian_date"] == "19 мая 2026"
    assert payload["hijri_date"] == "1 Зуль-хиджа 1447"
    assert payload["next_prayer"]["key"] in {"Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"}
    assert payload["next_prayer"]["label"]
    assert payload["next_prayer"]["time"]
    assert payload["calendar"][0]["title"] == "Курбан-байрам"
    assert payload["month_schedule"]["month"] == "Май"
    assert payload["month_schedule"]["rows"][0]["day"] == 19
    assert payload["month_schedule"]["rows"][0]["maghrib"] == "20:05"
