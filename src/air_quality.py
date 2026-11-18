"""Open-Meteo Geocoding & Air Quality API client with strict live-data integrity.

Rules enforced:
- Uses live Open-Meteo Geocoding and Air Quality APIs.
- Never invents or backfills missing AQI or pollutant readings.
- Clearly marks unavailable fields (`value=None`, `available=False`).
- Handles timeouts, HTTP errors, empty search results, and malformed payloads gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from src.config import (
    OPEN_METEO_AIR_QUALITY_URL,
    OPEN_METEO_GEOCODING_URL,
    POLLUTANT_CATALOG,
    REQUEST_TIMEOUT_SECONDS,
    AQICategory,
    classify_european_aqi,
    classify_us_aqi,
)


class AirQualityServiceError(Exception):
    """Structured error raised when geocoding or air quality fetches fail."""

    def __init__(self, message: str, category: str = "api_error", detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.category = category  # 'invalid_input' | 'not_found' | 'network' | 'api_error'
        self.detail = detail


@dataclass(frozen=True)
class GeoLocation:
    """Resolved city location from Open-Meteo Geocoding API."""

    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""
    country_code: str = ""
    timezone: str = "auto"
    population: Optional[int] = None

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1.lower() != self.name.lower():
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)

    @property
    def coordinates_label(self) -> str:
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.3f}°{lat_dir}, {abs(self.longitude):.3f}°{lon_dir}"


@dataclass(frozen=True)
class PollutantReading:
    """Single live pollutant measurement, transparently flagging unavailability."""

    key: str
    name: str
    formula: str
    value: Optional[float]
    unit: str
    available: bool
    who_guideline: Optional[float]
    who_basis: str
    health_note: str
    primary_sources: str

    @property
    def who_ratio(self) -> Optional[float]:
        """Multiple of WHO guideline if both live value and guideline exist."""
        if not self.available or self.value is None or not self.who_guideline:
            return None
        return self.value / self.who_guideline


@dataclass
class ForecastWindowSummary:
    """Summary of live hourly air quality forecast windows (never fabricated)."""

    available: bool
    hours_analyzed: int = 0
    best_window_label: Optional[str] = None
    best_window_avg_aqi: Optional[float] = None
    worst_window_label: Optional[str] = None
    worst_window_aqi: Optional[float] = None
    safe_ventilation_hours: List[str] = field(default_factory=list)
    note: str = ""


@dataclass
class AirQualitySnapshot:
    """Complete live air quality snapshot for a resolved location."""

    location: GeoLocation
    us_aqi: Optional[float]
    us_aqi_category: Optional[AQICategory]
    european_aqi: Optional[float]
    european_aqi_label: str
    european_aqi_color: str
    uv_index: Optional[float]
    pollutants: Dict[str, PollutantReading]
    data_timestamp: Optional[str]
    timezone_name: str
    timezone_abbr: str
    fetched_at_utc: str
    hourly_df: pd.DataFrame
    forecast_summary: ForecastWindowSummary
    source_name: str = "Open-Meteo Air Quality API (CAMS / Global Models)"

    @property
    def available_pollutant_count(self) -> int:
        return sum(1 for p in self.pollutants.values() if p.available)

    @property
    def dominant_pollutant(self) -> Optional[PollutantReading]:
        """Identify the live pollutant with the highest ratio vs WHO guideline."""
        candidates = [p for p in self.pollutants.values() if p.who_ratio is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.who_ratio or 0.0)


def _safe_float(val: Any) -> Optional[float]:
    """Convert numeric API values safely, preserving None for missing/invalid data."""
    if val is None or isinstance(val, bool):
        return None
    try:
        num = float(val)
        if pd.isna(num):
            return None
        return num
    except (TypeError, ValueError):
        return None


def search_cities(city_query: str, count: int = 8) -> List[GeoLocation]:
    """Resolve a city name via Open-Meteo Geocoding API."""
    cleaned = (city_query or "").strip()
    if len(cleaned) < 2:
        raise AirQualityServiceError(
            "Please enter at least 2 characters for a city name.",
            category="invalid_input",
        )

    params = {
        "name": cleaned,
        "count": max(1, min(count, 10)),
        "language": "en",
        "format": "json",
    }

    try:
        resp = requests.get(
            OPEN_METEO_GEOCODING_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": "AirAware-AI/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout as exc:
        raise AirQualityServiceError(
            "Location lookup timed out. Please check your internet connection and try again.",
            category="network",
            detail=str(exc),
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise AirQualityServiceError(
            "Unable to reach the Open-Meteo Geocoding API. Please verify network connectivity.",
            category="network",
            detail=str(exc),
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise AirQualityServiceError(
            f"Geocoding service returned HTTP {resp.status_code}. Please retry shortly.",
            category="api_error",
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise AirQualityServiceError(
            "Received an unexpected response format from the Geocoding API.",
            category="api_error",
            detail=str(exc),
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise AirQualityServiceError(
            "An unexpected network error occurred while looking up the city. Please try again.",
            category="network",
            detail=str(exc),
        ) from exc

    if not isinstance(payload, dict):
        raise AirQualityServiceError(
            "Received an unexpected response format from the Geocoding API.",
            category="api_error",
        )

    results = payload.get("results") or []
    if not results:
        raise AirQualityServiceError(
            f"No matching city found for '{cleaned}'. Try checking the spelling or adding a country name.",
            category="not_found",
        )

    locations: List[GeoLocation] = []
    for item in results:
        lat = _safe_float(item.get("latitude"))
        lon = _safe_float(item.get("longitude"))
        if lat is None or lon is None:
            continue
        pop_raw = item.get("population")
        pop = int(pop_raw) if isinstance(pop_raw, (int, float)) else None
        locations.append(
            GeoLocation(
                name=str(item.get("name", cleaned)),
                latitude=lat,
                longitude=lon,
                country=str(item.get("country", "")),
                admin1=str(item.get("admin1", "")),
                country_code=str(item.get("country_code", "")),
                timezone=str(item.get("timezone", "auto")),
                population=pop,
            )
        )

    if not locations:
        raise AirQualityServiceError(
            f"No valid coordinates were returned for '{cleaned}'.",
            category="not_found",
        )
    return locations


def _build_hourly_dataframe(hourly: Dict[str, Any], current_time_iso: Optional[str]) -> pd.DataFrame:
    """Parse Open-Meteo hourly arrays into a clean DataFrame without fabricating values."""
    times = hourly.get("time") or []
    if not times:
        return pd.DataFrame()

    cols = [
        "us_aqi",
        "european_aqi",
        "pm2_5",
        "pm10",
        "nitrogen_dioxide",
        "carbon_monoxide",
        "ozone",
    ]
    data: Dict[str, Any] = {"time": pd.to_datetime(times, errors="coerce")}
    n = len(times)
    for col in cols:
        series = hourly.get(col)
        if isinstance(series, list) and len(series) == n:
            data[col] = [_safe_float(v) for v in series]
        else:
            data[col] = [None] * n

    df = pd.DataFrame(data).dropna(subset=["time"]).reset_index(drop=True)
    if df.empty:
        return df

    # Anchor from the current local hour if current_time_iso is provided
    if current_time_iso:
        anchor = pd.to_datetime(current_time_iso, errors="coerce")
        if pd.notna(anchor):
            anchor_hour = anchor.floor("h")
            upcoming = df[df["time"] >= anchor_hour].copy()
            if not upcoming.empty:
                df = upcoming.reset_index(drop=True)

    return df.head(48)


def summarize_forecast_windows(hourly_df: pd.DataFrame, hours: int = 24) -> ForecastWindowSummary:
    """Identify the cleanest outdoor window and worst smog peak from live hourly forecast data."""
    if hourly_df.empty or "us_aqi" not in hourly_df.columns:
        return ForecastWindowSummary(
            available=False,
            note="Live hourly AQI forecast is currently unavailable for this location.",
        )

    window_df = hourly_df.head(hours).copy()
    valid = window_df.dropna(subset=["us_aqi"]).reset_index(drop=True)
    if valid.empty:
        return ForecastWindowSummary(
            available=False,
            note="No valid hourly US AQI values were returned for the next 24 hours.",
        )

    # Best 2-hour contiguous block (or best single hour if <2 valid hours)
    best_label: Optional[str] = None
    best_avg: Optional[float] = None

    if len(valid) >= 2:
        best_score = float("inf")
        best_idx = 0
        for idx in range(len(valid) - 1):
            t0 = valid.loc[idx, "time"]
            t1 = valid.loc[idx + 1, "time"]
            # Ensure contiguous hours
            if (t1 - t0).total_seconds() == 3600:
                avg_val = (float(valid.loc[idx, "us_aqi"]) + float(valid.loc[idx + 1, "us_aqi"])) / 2.0
                if avg_val < best_score:
                    best_score = avg_val
                    best_idx = idx
        if best_score < float("inf"):
            start_t = valid.loc[best_idx, "time"]
            end_t = valid.loc[best_idx + 1, "time"] + pd.Timedelta(hours=1)
            best_label = f"{start_t.strftime('%I:%M %p')} – {end_t.strftime('%I:%M %p')} ({start_t.strftime('%b %d')})"
            best_avg = round(best_score, 1)

    if best_label is None:
        min_idx = int(valid["us_aqi"].idxmin())
        min_t = valid.loc[min_idx, "time"]
        best_label = f"{min_t.strftime('%I:%M %p')} ({min_t.strftime('%b %d')})"
        best_avg = round(float(valid.loc[min_idx, "us_aqi"]), 1)

    max_idx = int(valid["us_aqi"].idxmax())
    worst_t = valid.loc[max_idx, "time"]
    worst_aqi = round(float(valid.loc[max_idx, "us_aqi"]), 1)
    worst_label = f"{worst_t.strftime('%I:%M %p')} ({worst_t.strftime('%b %d')})"

    safe_hours = [
        row["time"].strftime("%I:%M %p (%b %d)")
        for _, row in valid.iterrows()
        if float(row["us_aqi"]) <= 100.0
    ]

    if safe_hours:
        note = (
            f"Found {len(safe_hours)} hour(s) with Good/Moderate air (US AQI ≤ 100) in the next {len(valid)} hours."
        )
    else:
        note = (
            f"All {len(valid)} forecasted hours exceed US AQI 100. Prioritize indoor filtration and use the lowest-AQI window only for essential errands with N95 protection."
        )

    return ForecastWindowSummary(
        available=True,
        hours_analyzed=len(valid),
        best_window_label=best_label,
        best_window_avg_aqi=best_avg,
        worst_window_label=worst_label,
        worst_window_aqi=worst_aqi,
        safe_ventilation_hours=safe_hours,
        note=note,
    )


def fetch_air_quality(location: GeoLocation) -> AirQualitySnapshot:
    """Fetch live air quality metrics and 48-hour forecast from Open-Meteo Air Quality API."""
    current_vars = [
        "us_aqi",
        "european_aqi",
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "aerosol_optical_depth",
        "dust",
        "uv_index",
    ]
    hourly_vars = [
        "us_aqi",
        "european_aqi",
        "pm2_5",
        "pm10",
        "nitrogen_dioxide",
        "carbon_monoxide",
        "ozone",
    ]

    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "current": ",".join(current_vars),
        "hourly": ",".join(hourly_vars),
        "timezone": "auto",
        "forecast_days": 2,
    }

    try:
        resp = requests.get(
            OPEN_METEO_AIR_QUALITY_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": "AirAware-AI/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout as exc:
        raise AirQualityServiceError(
            "Air quality request timed out while contacting Open-Meteo. Please try again.",
            category="network",
            detail=str(exc),
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise AirQualityServiceError(
            "Could not connect to the Open-Meteo Air Quality API. Check your internet connection.",
            category="network",
            detail=str(exc),
        ) from exc
    except requests.exceptions.HTTPError as exc:
        raise AirQualityServiceError(
            f"Open-Meteo Air Quality API returned HTTP {resp.status_code}.",
            category="api_error",
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise AirQualityServiceError(
            "Malformed JSON received from Open-Meteo Air Quality API.",
            category="api_error",
            detail=str(exc),
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise AirQualityServiceError(
            "An unexpected network error occurred while fetching air quality data. Please try again.",
            category="network",
            detail=str(exc),
        ) from exc

    if not isinstance(payload, dict):
        raise AirQualityServiceError(
            "Malformed response payload received from Open-Meteo Air Quality API.",
            category="api_error",
        )

    if payload.get("error"):
        reason = payload.get("reason", "Unknown API error")
        raise AirQualityServiceError(
            f"Open-Meteo reported an error: {reason}",
            category="api_error",
            detail=str(reason),
        )

    current = payload.get("current") or {}
    current_units = payload.get("current_units") or {}
    hourly = payload.get("hourly") or {}

    us_aqi = _safe_float(current.get("us_aqi"))
    eaqi = _safe_float(current.get("european_aqi"))
    uv_index = _safe_float(current.get("uv_index"))
    eaqi_label, eaqi_color = classify_european_aqi(eaqi)

    pollutants: Dict[str, PollutantReading] = {}
    for key, meta in POLLUTANT_CATALOG.items():
        raw_val = _safe_float(current.get(key))
        api_unit = current_units.get(key)
        unit = str(api_unit) if api_unit else meta.default_unit
        pollutants[key] = PollutantReading(
            key=key,
            name=meta.name,
            formula=meta.formula,
            value=raw_val,
            unit=unit,
            available=(raw_val is not None),
            who_guideline=meta.who_guideline,
            who_basis=meta.who_basis,
            health_note=meta.health_note,
            primary_sources=meta.primary_sources,
        )

    data_ts = current.get("time")
    tz_name = str(payload.get("timezone", location.timezone or "UTC"))
    tz_abbr = str(payload.get("timezone_abbreviation", ""))
    fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    hourly_df = _build_hourly_dataframe(hourly, data_ts)
    forecast_summary = summarize_forecast_windows(hourly_df, hours=24)

    return AirQualitySnapshot(
        location=location,
        us_aqi=us_aqi,
        us_aqi_category=classify_us_aqi(us_aqi),
        european_aqi=eaqi,
        european_aqi_label=eaqi_label,
        european_aqi_color=eaqi_color,
        uv_index=uv_index,
        pollutants=pollutants,
        data_timestamp=str(data_ts) if data_ts else None,
        timezone_name=tz_name,
        timezone_abbr=tz_abbr,
        fetched_at_utc=fetched_utc,
        hourly_df=hourly_df,
        forecast_summary=forecast_summary,
    )


def format_display_timestamp(iso_ts: Optional[str], tz_abbr: str = "", tz_name: str = "") -> Tuple[str, str]:
    """Return human-readable local reading time and timezone descriptor."""
    if not iso_ts:
        return ("Timestamp unavailable", tz_name or "Unknown timezone")
    try:
        dt = datetime.fromisoformat(iso_ts)
        formatted = dt.strftime("%b %d, %Y · %I:%M %p")
        tz_label = f"{tz_abbr} ({tz_name})" if tz_abbr and tz_name and tz_abbr != tz_name else (tz_name or tz_abbr or "Local")
        return (formatted, tz_label)
    except ValueError:
        return (iso_ts, tz_name or tz_abbr or "Local")
