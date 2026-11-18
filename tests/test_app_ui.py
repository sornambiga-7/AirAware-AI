"""Streamlit AppTest end-to-end UI rendering tests across all 6 AirAware AI modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

MOCK_GEOCODE_PAYLOAD = {
    "results": [
        {
            "name": "New Delhi",
            "admin1": "Delhi",
            "country": "India",
            "country_code": "IN",
            "latitude": 28.6139,
            "longitude": 77.209,
            "timezone": "Asia/Kolkata",
            "population": 16787941,
        }
    ]
}

MOCK_AQ_PAYLOAD = {
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "IST",
    "current_units": {
        "pm2_5": "μg/m³",
        "pm10": "μg/m³",
        "carbon_monoxide": "μg/m³",
        "nitrogen_dioxide": "μg/m³",
        "sulphur_dioxide": "μg/m³",
        "ozone": "μg/m³",
    },
    "current": {
        "time": "2026-11-18T12:00",
        "us_aqi": 188,
        "european_aqi": 84,
        "pm2_5": 112.5,
        "pm10": 185.0,
        "carbon_monoxide": 980.0,
        "nitrogen_dioxide": 54.2,
        "sulphur_dioxide": None,
        "ozone": 41.0,
        "dust": 32.0,
        "aerosol_optical_depth": 0.92,
        "uv_index": 3.4,
    },
    "hourly": {
        "time": [
            "2026-11-18T12:00",
            "2026-11-18T13:00",
            "2026-11-18T14:00",
            "2026-11-18T15:00",
            "2026-11-18T16:00",
            "2026-11-18T17:00",
        ],
        "us_aqi": [188, 165, 148, 152, 174, 205],
        "european_aqi": [84, 74, 66, 68, 78, 92],
        "pm2_5": [112.5, 92.0, 74.0, 79.0, 98.0, 128.0],
        "pm10": [185.0, 150.0, 130.0, 140.0, 165.0, 210.0],
        "nitrogen_dioxide": [54.2, 42.0, 36.0, 41.0, 58.0, 72.0],
        "carbon_monoxide": [980.0, 820.0, 760.0, 800.0, 950.0, 1180.0],
        "ozone": [41.0, 48.0, 52.0, 47.0, 39.0, 31.0],
    },
}


def _mock_requests_get(url: str, *args, **kwargs):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    if "geocoding-api" in url:
        resp.json.return_value = MOCK_GEOCODE_PAYLOAD
    else:
        resp.json.return_value = MOCK_AQ_PAYLOAD
    return resp


@patch("src.air_quality.requests.get", side_effect=_mock_requests_get)
def test_all_six_pages_render_without_exceptions(_mock_get):
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    assert not at.exception, f"Dashboard exception: {at.exception}"

    pages = [
        "AI Smart Assistant",
        "Smart Daily Routine",
        "Indoor Air Hacks",
        "Eco-Friendly Travel",
        "Pollution Impact Tracker",
        "Air Quality Dashboard",
    ]
    for page in pages:
        at.sidebar.radio(key="nav_section").set_value(page).run()
        assert not at.exception, f"Exception on page '{page}': {at.exception}"


@patch("src.air_quality.requests.get", side_effect=_mock_requests_get)
def test_ai_briefing_button_works_in_fallback_mode(_mock_get, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file(APP_PATH, default_timeout=20)
    at.run()
    at.sidebar.radio(key="nav_section").set_value("AI Smart Assistant").run()
    assert not at.exception
    # Click "Generate Personalized Briefing"
    gen_btn = next(b for b in at.button if "Generate Personalized Briefing" in b.label)
    gen_btn.click().run()
    assert not at.exception
    combined_md = "\n".join(m.value for m in at.markdown)
    assert "New Delhi" in combined_md
