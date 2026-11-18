"""Configuration, constants, AQI standards, WHO guidelines, and transparent emission factors."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Resolve .env explicitly from project root so it loads regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)

APP_NAME = "AirAware AI"
APP_TAGLINE = "Urban Air Quality Assistant for Winter Smog & Healthy Communities"
CHALLENGE_BADGE = "Hack2Skill PromptWars · Challenge 6"

# Open-Meteo free, open-access endpoints (no API key required)
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

REQUEST_TIMEOUT_SECONDS = 12

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "New Delhi").strip() or "New Delhi"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
GEMINI_FALLBACK_MODELS: List[str] = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

# Curated quick-select cities (mix of winter smog hotspots and global benchmarks)
FEATURED_CITIES: List[str] = [
    "New Delhi",
    "Lahore",
    "Beijing",
    "Mumbai",
    "Kolkata",
    "Bengaluru",
    "London",
    "New York",
    "Tokyo",
    "Zurich",
]


def get_gemini_api_key() -> Optional[str]:
    """Read GEMINI_API_KEY strictly from environment variables (or Streamlit secrets).

    Returns None if unset or still holding the placeholder value from .env.example.
    Never exposes or logs the key value.
    """
    raw = os.getenv("GEMINI_API_KEY", "").strip().strip("'\"")
    if not raw:
        try:
            import streamlit as st

            if "GEMINI_API_KEY" in st.secrets:
                raw = str(st.secrets["GEMINI_API_KEY"]).strip().strip("'\"")
        except Exception:
            raw = ""

    if not raw or raw.lower() in {"your_google_gemini_api_key_here", "your_api_key_here", "none", "null"}:
        return None
    return raw


@dataclass(frozen=True)
class AQICategory:
    """US EPA Air Quality Index category metadata."""

    name: str
    short_label: str
    min_val: int
    max_val: Optional[int]
    color: str
    bg_tint: str
    emoji: str
    health_summary: str
    outdoor_guidance: str
    ventilation_advice: str
    mask_advice: str


US_AQI_CATEGORIES: List[AQICategory] = [
    AQICategory(
        name="Good",
        short_label="Good",
        min_val=0,
        max_val=50,
        color="#10B981",
        bg_tint="rgba(16, 185, 129, 0.14)",
        emoji="🟢",
        health_summary="Air quality is satisfactory, and air pollution poses little or no risk.",
        outdoor_guidance="Great time for outdoor walks, cycling, school play, and open-air exercise.",
        ventilation_advice="Open windows for cross-ventilation to refresh indoor air naturally.",
        mask_advice="No respiratory mask needed for general outdoor activity.",
    ),
    AQICategory(
        name="Moderate",
        short_label="Moderate",
        min_val=51,
        max_val=100,
        color="#FACC15",
        bg_tint="rgba(250, 204, 21, 0.14)",
        emoji="🟡",
        health_summary="Air quality is acceptable; however, unusually sensitive people may experience mild irritation.",
        outdoor_guidance="Most people can enjoy outdoor activities; sensitive groups should monitor symptoms during prolonged exertion.",
        ventilation_advice="Ventilate during the cleanest daylight hours; close windows near busy traffic corridors.",
        mask_advice="Optional for people with severe asthma or high sensitivity near heavy traffic.",
    ),
    AQICategory(
        name="Unhealthy for Sensitive Groups",
        short_label="USG",
        min_val=101,
        max_val=150,
        color="#F97316",
        bg_tint="rgba(249, 115, 22, 0.15)",
        emoji="🟠",
        health_summary="Children, older adults, pregnant individuals, and people with asthma/heart/lung disease may experience health effects.",
        outdoor_guidance="Sensitive groups should reduce prolonged or heavy outdoor exertion and move workouts indoors.",
        ventilation_advice="Keep windows mostly closed; only briefly air out rooms during the lowest-AQI afternoon window.",
        mask_advice="Sensitive groups should wear a well-fitted N95/KN95 mask outdoors.",
    ),
    AQICategory(
        name="Unhealthy",
        short_label="Unhealthy",
        min_val=151,
        max_val=200,
        color="#EF4444",
        bg_tint="rgba(239, 68, 68, 0.16)",
        emoji="🔴",
        health_summary="Everyone may begin to experience health effects; sensitive groups may experience more serious respiratory symptoms.",
        outdoor_guidance="Avoid strenuous outdoor exercise; shift walks, school sports, and commutes indoors or to cleaner windows.",
        ventilation_advice="Keep windows and doors tightly sealed; run HEPA or DIY MERV-13 filtration on continuous mode.",
        mask_advice="Wear a properly sealed N95/KN95/FFP2 respirator whenever stepping outdoors.",
    ),
    AQICategory(
        name="Very Unhealthy",
        short_label="Very Unhealthy",
        min_val=201,
        max_val=300,
        color="#A855F7",
        bg_tint="rgba(168, 85, 247, 0.16)",
        emoji="🟣",
        health_summary="Health alert: the risk of respiratory and cardiovascular effects is significantly elevated for everyone.",
        outdoor_guidance="Avoid all unnecessary outdoor exertion; keep children and elderly indoors with filtered air.",
        ventilation_advice="Do NOT open windows for ventilation. Seal door gaps and create a dedicated clean-air bedroom.",
        mask_advice="Strongly recommended: snug-fitting N95/KN95/FFP2 mask for any essential outdoor exposure.",
    ),
    AQICategory(
        name="Hazardous",
        short_label="Hazardous",
        min_val=301,
        max_val=None,
        color="#E11D48",
        bg_tint="rgba(225, 29, 72, 0.18)",
        emoji="🚨",
        health_summary="Health warning of emergency conditions: the entire population is likely to be affected.",
        outdoor_guidance="Remain indoors, suspend outdoor activities, and follow local public health advisories immediately.",
        ventilation_advice="Seal the home completely, avoid all indoor combustion (candles, incense, frying), and run air purifiers at max.",
        mask_advice="Mandatory N95/KN95/FFP2 respirator if stepping outside is strictly unavoidable.",
    ),
]


def classify_us_aqi(aqi: Optional[float]) -> Optional[AQICategory]:
    """Classify a numeric US AQI reading into its official US EPA category."""
    if aqi is None:
        return None
    val = max(0, round(aqi))
    for cat in US_AQI_CATEGORIES:
        if cat.max_val is None or val <= cat.max_val:
            return cat
    return US_AQI_CATEGORIES[-1]


def classify_european_aqi(eaqi: Optional[float]) -> Tuple[str, str]:
    """Return (category_name, color_hex) for European AQI (EEA standard)."""
    if eaqi is None:
        return ("Unavailable", "#64748B")
    if eaqi <= 20:
        return ("Good", "#10B981")
    if eaqi <= 40:
        return ("Fair", "#34D399")
    if eaqi <= 60:
        return ("Moderate", "#FACC15")
    if eaqi <= 80:
        return ("Poor", "#F97316")
    if eaqi <= 100:
        return ("Very Poor", "#EF4444")
    return ("Extremely Poor", "#A855F7")


@dataclass(frozen=True)
class PollutantMeta:
    """Metadata and WHO 2021 AQG reference values for each tracked pollutant."""

    key: str
    name: str
    formula: str
    default_unit: str
    who_guideline: Optional[float]  # 24-hr or peak guideline in same unit as API
    who_basis: str
    health_note: str
    primary_sources: str


POLLUTANT_CATALOG: Dict[str, PollutantMeta] = {
    "pm2_5": PollutantMeta(
        key="pm2_5",
        name="Fine Particulate Matter",
        formula="PM2.5",
        default_unit="μg/m³",
        who_guideline=15.0,
        who_basis="WHO 2021 24-hr guideline (15 μg/m³)",
        health_note="Microscopic particles (<2.5 μm) penetrate deep into alveoli and bloodstream; key driver of winter smog.",
        primary_sources="Vehicle exhaust, crop/biomass burning, coal/wood heating, secondary winter aerosols",
    ),
    "pm10": PollutantMeta(
        key="pm10",
        name="Coarse Particulate Matter",
        formula="PM10",
        default_unit="μg/m³",
        who_guideline=45.0,
        who_basis="WHO 2021 24-hr guideline (45 μg/m³)",
        health_note="Inhalable particles (<10 μm) irritating airways, eyes, and aggravating asthma/bronchitis.",
        primary_sources="Road dust, construction, unpaved streets, windblown soil, industrial grinding",
    ),
    "nitrogen_dioxide": PollutantMeta(
        key="nitrogen_dioxide",
        name="Nitrogen Dioxide",
        formula="NO₂",
        default_unit="μg/m³",
        who_guideline=25.0,
        who_basis="WHO 2021 24-hr guideline (25 μg/m³)",
        health_note="Inflames airways, increases asthma attacks in children, and forms secondary winter smog.",
        primary_sources="Diesel & petrol traffic, gas stoves, power plants, urban congestion",
    ),
    "carbon_monoxide": PollutantMeta(
        key="carbon_monoxide",
        name="Carbon Monoxide",
        formula="CO",
        default_unit="μg/m³",
        who_guideline=4000.0,
        who_basis="WHO 2021 24-hr guideline (4,000 μg/m³)",
        health_note="Reduces oxygen delivery to organs; spikes during traffic idling and indoor biomass/heater use.",
        primary_sources="Incomplete fuel combustion, idling vehicles, unvented heaters, biomass burning",
    ),
    "ozone": PollutantMeta(
        key="ozone",
        name="Ground-Level Ozone",
        formula="O₃",
        default_unit="μg/m³",
        who_guideline=100.0,
        who_basis="WHO 2021 8-hr guideline (100 μg/m³)",
        health_note="Triggers chest tightness, coughing, and reduced lung function during outdoor exertion.",
        primary_sources="Sunlight reacting with traffic NOx and volatile organic compounds (VOCs)",
    ),
    "sulphur_dioxide": PollutantMeta(
        key="sulphur_dioxide",
        name="Sulphur Dioxide",
        formula="SO₂",
        default_unit="μg/m³",
        who_guideline=40.0,
        who_basis="WHO 2021 24-hr guideline (40 μg/m³)",
        health_note="Can cause rapid bronchoconstriction, especially in people with asthma.",
        primary_sources="Coal/heavy oil combustion, brick kilns, industrial boilers, high-sulphur fuel",
    ),
    "dust": PollutantMeta(
        key="dust",
        name="Mineral Dust",
        formula="Dust",
        default_unit="μg/m³",
        who_guideline=None,
        who_basis="No standalone WHO threshold (contributes to PM10)",
        health_note="Airborne desert or construction mineral dust that reduces visibility and irritates eyes/throat.",
        primary_sources="Regional dust transport, dry winter winds, exposed soil & construction",
    ),
    "aerosol_optical_depth": PollutantMeta(
        key="aerosol_optical_depth",
        name="Aerosol Optical Depth",
        formula="AOD",
        default_unit="index",
        who_guideline=None,
        who_basis="Atmospheric column haze indicator (>0.5 indicates hazy/smoggy air)",
        health_note="Measures sunlight attenuation by suspended aerosols across the entire atmospheric column.",
        primary_sources="Dense regional smog plumes, smoke haze, winter inversion trapping",
    ),
}
