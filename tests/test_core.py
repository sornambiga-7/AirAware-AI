"""Automated unit tests for AirAware AI core logic, API integrity, and transparent calculations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.air_quality import (
    AirQualityServiceError,
    GeoLocation,
    fetch_air_quality,
    format_display_timestamp,
    search_cities,
    summarize_forecast_windows,
)
from src.config import classify_european_aqi, classify_us_aqi, get_gemini_api_key
from src.gemini_assistant import (
    FamilyProfile,
    build_live_context_block,
    generate_personalized_briefing,
)
from src.impact_calculator import (
    compute_household_impact,
    evaluate_eco_travel_options,
)


def test_us_aqi_classification_boundaries():
    assert classify_us_aqi(None) is None
    assert classify_us_aqi(0).name == "Good"
    assert classify_us_aqi(50).name == "Good"
    assert classify_us_aqi(51).name == "Moderate"
    assert classify_us_aqi(125).name == "Unhealthy for Sensitive Groups"
    assert classify_us_aqi(175).name == "Unhealthy"
    assert classify_us_aqi(250).name == "Very Unhealthy"
    assert classify_us_aqi(350).name == "Hazardous"


def test_european_aqi_classification():
    assert classify_european_aqi(None)[0] == "Unavailable"
    assert classify_european_aqi(15)[0] == "Good"
    assert classify_european_aqi(55)[0] == "Moderate"
    assert classify_european_aqi(110)[0] == "Extremely Poor"


def test_search_cities_rejects_short_input():
    with pytest.raises(AirQualityServiceError) as exc_info:
        search_cities("a")
    assert exc_info.value.category == "invalid_input"


@patch("src.air_quality.requests.get")
def test_search_cities_parses_results(mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "results": [
            {
                "name": "New Delhi",
                "admin1": "Delhi",
                "country": "India",
                "country_code": "IN",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "timezone": "Asia/Kolkata",
                "population": 16787941,
            }
        ]
    }
    mock_get.return_value = mock_resp

    locations = search_cities("New Delhi")
    assert len(locations) == 1
    assert locations[0].display_name == "New Delhi, Delhi, India"
    assert locations[0].latitude == pytest.approx(28.6139)


@patch("src.air_quality.requests.get")
def test_fetch_air_quality_preserves_unavailable_pollutants(mock_get):
    """Critical integrity check: missing/null pollutants MUST remain None and available=False."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "current_units": {"pm2_5": "μg/m³", "pm10": "μg/m³", "carbon_monoxide": "μg/m³"},
        "current": {
            "time": "2026-11-18T12:00",
            "us_aqi": 215,
            "european_aqi": 95,
            "pm2_5": 165.4,
            "pm10": 240.2,
            "carbon_monoxide": 1200.0,
            "nitrogen_dioxide": None,  # Explicitly null
            # sulphur_dioxide omitted completely
            "ozone": 38.5,
        },
        "hourly": {
            "time": [
                "2026-11-18T12:00",
                "2026-11-18T13:00",
                "2026-11-18T14:00",
                "2026-11-18T15:00",
            ],
            "us_aqi": [215, 180, 155, 195],
            "european_aqi": [95, 80, 72, 88],
            "pm2_5": [165.4, 130.0, 105.0, 145.0],
            "pm10": [240.2, 200.0, 175.0, 210.0],
            "nitrogen_dioxide": [None, None, None, None],
            "carbon_monoxide": [1200.0, 900.0, 800.0, 1100.0],
            "ozone": [38.5, 45.0, 50.0, 42.0],
        },
    }
    mock_get.return_value = mock_resp

    loc = GeoLocation(name="New Delhi", latitude=28.6139, longitude=77.209, country="India")
    snap = fetch_air_quality(loc)

    assert snap.us_aqi == 215.0
    assert snap.us_aqi_category.name == "Very Unhealthy"
    assert snap.pollutants["pm2_5"].available is True
    assert snap.pollutants["pm2_5"].value == 165.4
    assert snap.pollutants["nitrogen_dioxide"].available is False
    assert snap.pollutants["nitrogen_dioxide"].value is None
    assert snap.pollutants["sulphur_dioxide"].available is False
    assert snap.pollutants["sulphur_dioxide"].value is None
    assert snap.forecast_summary.available is True
    assert snap.forecast_summary.best_window_avg_aqi == pytest.approx(167.5)
    assert snap.forecast_summary.worst_window_aqi == pytest.approx(215.0)


def test_forecast_summary_handles_empty_df():
    summary = summarize_forecast_windows(pd.DataFrame())
    assert summary.available is False


def test_format_display_timestamp():
    txt, tz = format_display_timestamp("2026-11-18T14:00", "IST", "Asia/Kolkata")
    assert "Nov 18, 2026" in txt
    assert "IST" in tz
    missing_txt, _ = format_display_timestamp(None)
    assert "unavailable" in missing_txt.lower()


def test_eco_travel_smog_safety_ranking():
    # Under severe smog (AQI 230), enclosed transit/carpool should rank ahead of unmasked cycling/walking
    options = evaluate_eco_travel_options(
        current_mode_key="petrol_car",
        one_way_km=6.0,
        days_per_week=5,
        live_us_aqi=230.0,
    )
    top_option = options[0]
    assert top_option.mode.is_active_exposed is False
    assert top_option.annual_co2_saved_kg > 0
    assert "kg CO₂e/yr" in top_option.formula


def test_household_impact_transparent_math():
    report = compute_household_impact(
        commute_from_key="petrol_car",
        commute_to_key="metro_rail",
        commute_km_per_week=100.0,
        idling_mins_avoided_per_week=60.0,
        electricity_kwh_saved_per_week=10.0,
        grid_preset_label="India Grid Average (0.71 kg CO₂e/kWh)",
        biomass_kg_composted_per_month=10.0,
        weeks_per_year=48,
    )
    # Commute: 100 * 48 * (0.171 - 0.035) = 652.8 kg
    # Idling: 1 hr * 52 * 1.85 = 96.2 kg
    # Electricity: 10 * 52 * 0.71 = 369.2 kg
    # Biomass: 10 * 12 * 1.45 = 174.0 kg; PM2.5 = 120 * 19 = 2280 g
    assert len(report.items) == 4
    assert report.total_annual_co2_kg == pytest.approx(652.8 + 96.2 + 369.2 + 174.0, abs=0.2)
    assert report.total_annual_pm25_g >= 2280.0
    assert report.community_1000_households_co2_tonnes == pytest.approx(report.total_annual_co2_kg, abs=0.2)


def test_gemini_fallback_when_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert get_gemini_api_key() is None

    # Build minimal valid snapshot
    with patch("src.air_quality.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "timezone": "UTC",
            "timezone_abbreviation": "UTC",
            "current": {"time": "2026-11-18T12:00", "us_aqi": 162, "pm2_5": 78.0},
            "hourly": {"time": [], "us_aqi": []},
        }
        mock_get.return_value = mock_resp
        snap = fetch_air_quality(GeoLocation(name="Test City", latitude=10.0, longitude=20.0))

    ctx = build_live_context_block(snap)
    assert "Unavailable (not reported by API)" in ctx
    assert "78.0" in ctx

    res = generate_personalized_briefing(snap, FamilyProfile(household_groups=["Children"]))
    assert res.is_ai_generated is False
    assert "Test City" in res.content
    assert "GEMINI_API_KEY" in (res.error_message or "")
