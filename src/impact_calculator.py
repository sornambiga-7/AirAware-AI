"""Transparent, source-cited eco-travel & pollution impact calculations.

All environmental estimates strictly require explicit user inputs and show exact formulas
and published reference emission factors (UK DEFRA/DESNZ 2024, US EPA Mobile/AP-42, IEA).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TransportMode:
    """Published per-passenger-km emission factors for urban transport modes."""

    key: str
    label: str
    icon: str
    co2e_kg_per_pkm: float  # kg CO2e per passenger-km
    nox_g_per_pkm: float  # estimated tailpipe NOx g/passenger-km
    pm25_g_per_pkm: float  # estimated direct PM2.5 g/passenger-km
    is_active_exposed: bool  # True if rider breathes unfiltered ambient air during high exertion
    max_comfortable_km: float
    source: str
    notes: str


TRANSPORT_MODES: Dict[str, TransportMode] = {
    "petrol_car": TransportMode(
        key="petrol_car",
        label="Petrol Car (Solo)",
        icon="🚗",
        co2e_kg_per_pkm=0.171,
        nox_g_per_pkm=0.21,
        pm25_g_per_pkm=0.008,
        is_active_exposed=False,
        max_comfortable_km=100.0,
        source="UK DEFRA/DESNZ 2024 (avg petrol passenger car) & EEA Tier-2 tailpipe averages",
        notes="Single-occupancy petrol vehicle; major urban source of CO₂, NOx, and brake/tire PM.",
    ),
    "diesel_car": TransportMode(
        key="diesel_car",
        label="Diesel Car (Solo)",
        icon="🚙",
        co2e_kg_per_pkm=0.168,
        nox_g_per_pkm=0.56,
        pm25_g_per_pkm=0.022,
        is_active_exposed=False,
        max_comfortable_km=100.0,
        source="UK DEFRA/DESNZ 2024 (avg diesel car) & EEA real-world NOx/PM factors",
        notes="Higher urban NO₂ and fine particulate output, amplifying winter smog formation.",
    ),
    "motorcycle": TransportMode(
        key="motorcycle",
        label="Motorcycle / Petrol Scooter",
        icon="🛵",
        co2e_kg_per_pkm=0.113,
        nox_g_per_pkm=0.18,
        pm25_g_per_pkm=0.015,
        is_active_exposed=True,
        max_comfortable_km=40.0,
        source="UK DEFRA/DESNZ 2024 (average motorbike) & ICCT two-wheeler averages",
        notes="Lower CO₂ than a solo car, but emits urban particulates/CO and exposes rider directly to traffic smog.",
    ),
    "rideshare": TransportMode(
        key="rideshare",
        label="Taxi / Auto-Rickshaw / Solo Cab",
        icon="🚕",
        co2e_kg_per_pkm=0.149,
        nox_g_per_pkm=0.28,
        pm25_g_per_pkm=0.016,
        is_active_exposed=False,
        max_comfortable_km=60.0,
        source="UK DEFRA/DESNZ 2024 (regular taxi avg passenger-km)",
        notes="Includes deadheading/idling overhead between urban trips.",
    ),
    "carpool_3": TransportMode(
        key="carpool_3",
        label="Carpool (3 People Sharing)",
        icon="🚘",
        co2e_kg_per_pkm=0.057,
        nox_g_per_pkm=0.07,
        pm25_g_per_pkm=0.0027,
        is_active_exposed=False,
        max_comfortable_km=100.0,
        source="Calculated directly as Petrol Car (0.171 kg/km) ÷ 3 occupants",
        notes="Cuts per-person emissions and urban traffic congestion by 67% immediately; enclosed cabin protects during severe smog.",
    ),
    "city_bus": TransportMode(
        key="city_bus",
        label="Public Bus",
        icon="🚌",
        co2e_kg_per_pkm=0.089,
        nox_g_per_pkm=0.12,
        pm25_g_per_pkm=0.004,
        is_active_exposed=False,
        max_comfortable_km=60.0,
        source="UK DEFRA/DESNZ 2024 (average local bus per passenger-km)",
        notes="Replaces dozens of solo vehicles along high-density corridors; electric/CNG buses lower local PM even further.",
    ),
    "metro_rail": TransportMode(
        key="metro_rail",
        label="Metro / Urban Rail",
        icon="🚇",
        co2e_kg_per_pkm=0.035,
        nox_g_per_pkm=0.01,
        pm25_g_per_pkm=0.001,
        is_active_exposed=False,
        max_comfortable_km=80.0,
        source="UK DEFRA/DESNZ 2024 (national/light rail average per passenger-km)",
        notes="Zero street-level tailpipe exhaust and enclosed filtered cabins—ideal during winter smog episodes.",
    ),
    "cycling": TransportMode(
        key="cycling",
        label="Cycling",
        icon="🚲",
        co2e_kg_per_pkm=0.0,
        nox_g_per_pkm=0.0,
        pm25_g_per_pkm=0.0,
        is_active_exposed=True,
        max_comfortable_km=12.0,
        source="Zero direct tailpipe/operational emissions",
        notes="Zero emissions and great health benefits when AQI ≤ 100; avoid heavy cycling unmasked when AQI > 150.",
    ),
    "walking": TransportMode(
        key="walking",
        label="Walking",
        icon="🚶",
        co2e_kg_per_pkm=0.0,
        nox_g_per_pkm=0.0,
        pm25_g_per_pkm=0.0,
        is_active_exposed=True,
        max_comfortable_km=4.0,
        source="Zero direct tailpipe/operational emissions",
        notes="Best zero-emission choice for short trips (<3 km) when air quality permits; use N95 mask if AQI > 150.",
    ),
}

GRID_INTENSITY_PRESETS: Dict[str, Dict[str, object]] = {
    "India Grid Average (0.71 kg CO₂e/kWh)": {
        "factor": 0.71,
        "source": "IEA / CEA India Grid Emission Factor (~0.71 kg CO₂e/kWh)",
    },
    "Global Grid Average (0.44 kg CO₂e/kWh)": {
        "factor": 0.44,
        "source": "IEA Global Electricity Carbon Intensity (~0.44 kg CO₂e/kWh)",
    },
    "US Grid Average (0.38 kg CO₂e/kWh)": {
        "factor": 0.38,
        "source": "US EPA eGRID National Average (~0.38 kg CO₂e/kWh)",
    },
    "EU Grid Average (0.25 kg CO₂e/kWh)": {
        "factor": 0.25,
        "source": "EEA EU-27 Electricity Carbon Intensity (~0.25 kg CO₂e/kWh)",
    },
}

# Transparent constants for non-commute household actions
IDLING_CO2_KG_PER_HOUR = 1.85  # ~0.8 L petrol/hr * 2.31 kg CO2/L (US EPA / NRCan)
OPEN_BIOMASS_PM25_G_PER_KG = 19.0  # US EPA AP-42 open burning of leaves/yard waste (~19 g PM2.5 / kg dry matter)
OPEN_BIOMASS_CO2_KG_PER_KG = 1.45  # Approximate CO2 + CH4/N2O equivalent from incomplete open waste/leaf burning


@dataclass
class TravelOptionEvaluation:
    """Evaluated eco-travel option combining transparent emissions savings & live AQI safety."""

    mode: TransportMode
    weekly_co2_saved_kg: float
    annual_co2_saved_kg: float
    annual_nox_saved_g: float
    annual_pm25_saved_g: float
    aqi_safety_badge: str
    aqi_safety_color: str
    aqi_safety_note: str
    suitability_rank: int
    formula: str


def evaluate_eco_travel_options(
    current_mode_key: str,
    one_way_km: float,
    days_per_week: int,
    live_us_aqi: Optional[float],
    weeks_per_year: int = 48,
) -> List[TravelOptionEvaluation]:
    """Evaluate eco-friendly alternatives against user's current commute with AQI-aware safety."""
    current = TRANSPORT_MODES[current_mode_key]
    weekly_km = max(0.0, one_way_km) * 2.0 * max(0, days_per_week)
    annual_km = weekly_km * weeks_per_year

    candidate_keys = ["walking", "cycling", "metro_rail", "city_bus", "carpool_3"]
    evaluations: List[TravelOptionEvaluation] = []

    for key in candidate_keys:
        if key == current_mode_key:
            continue
        alt = TRANSPORT_MODES[key]
        delta_co2 = max(0.0, current.co2e_kg_per_pkm - alt.co2e_kg_per_pkm)
        delta_nox = max(0.0, current.nox_g_per_pkm - alt.nox_g_per_pkm)
        delta_pm25 = max(0.0, current.pm25_g_per_pkm - alt.pm25_g_per_pkm)

        weekly_co2 = round(weekly_km * delta_co2, 2)
        annual_co2 = round(annual_km * delta_co2, 1)
        annual_nox = round(annual_km * delta_nox, 1)
        annual_pm25 = round(annual_km * delta_pm25, 1)

        # Evaluate real-world distance + live AQI safety
        distance_ok = one_way_km <= alt.max_comfortable_km
        if not distance_ok:
            badge = "Long Distance"
            color = "#94A3B8"
            note = (
                f"One-way trip ({one_way_km:.1f} km) exceeds typical {alt.label.lower()} comfort range "
                f"(≤{alt.max_comfortable_km:.0f} km). Consider multimodal pairing with transit."
            )
            rank = 3
        elif alt.is_active_exposed:
            if live_us_aqi is None:
                badge = "Check Local AQI"
                color = "#FACC15"
                note = "Live AQI unavailable—verify local haze conditions before unmasked active travel."
                rank = 2
            elif live_us_aqi <= 100:
                badge = "AQI Safe & Zero-Emission"
                color = "#10B981"
                note = f"Live US AQI ({live_us_aqi:.0f}) is favorable for zero-emission {alt.label.lower()}."
                rank = 0
            elif live_us_aqi <= 150:
                badge = "Caution for Sensitive Groups"
                color = "#F97316"
                note = f"Live US AQI ({live_us_aqi:.0f}): take low-traffic side streets; sensitive groups should wear N95 or use transit."
                rank = 1
            else:
                badge = "Smog Advisory — Prefer Enclosed Transit"
                color = "#EF4444"
                note = (
                    f"Live US AQI ({live_us_aqi:.0f}) is elevated. Elevated breathing rates increase inhaled PM2.5—"
                    f"use enclosed Metro/Bus or Carpool today, or wear a sealed N95 for essential short walks."
                )
                rank = 2
        else:
            if live_us_aqi is not None and live_us_aqi > 150:
                badge = "Best Smog-Day Low-Emission Pick"
                color = "#10B981"
                note = (
                    f"Enclosed cabin reduces direct street-level PM2.5 inhalation during AQI {live_us_aqi:.0f} "
                    f"while cutting per-person emissions vs {current.label.lower()}."
                )
                rank = 0
            else:
                badge = "Recommended Low-Emission Option"
                color = "#34D399"
                note = f"Practical low-emission alternative for a {one_way_km:.1f} km commute."
                rank = 1

        formula = (
            f"({one_way_km:.1f} km × 2 trips × {days_per_week} days/wk × {weeks_per_year} wks) × "
            f"({current.co2e_kg_per_pkm:.3f} − {alt.co2e_kg_per_pkm:.3f} kg CO₂e/km) = {annual_co2:.1f} kg CO₂e/yr"
        )

        evaluations.append(
            TravelOptionEvaluation(
                mode=alt,
                weekly_co2_saved_kg=weekly_co2,
                annual_co2_saved_kg=annual_co2,
                annual_nox_saved_g=annual_nox,
                annual_pm25_saved_g=annual_pm25,
                aqi_safety_badge=badge,
                aqi_safety_color=color,
                aqi_safety_note=note,
                suitability_rank=rank,
                formula=formula,
            )
        )

    evaluations.sort(key=lambda e: (e.suitability_rank, -e.annual_co2_saved_kg))
    return evaluations


@dataclass
class ActionImpactItem:
    """Single transparent impact line-item in the Pollution Impact Tracker."""

    action_name: str
    category: str
    weekly_co2_kg: float
    annual_co2_kg: float
    annual_nox_g: float
    annual_pm25_g: float
    formula_text: str
    source_citation: str


@dataclass
class HouseholdImpactReport:
    """Aggregated, auditable environmental impact calculation."""

    items: List[ActionImpactItem]
    total_weekly_co2_kg: float
    total_monthly_co2_kg: float
    total_annual_co2_kg: float
    total_annual_nox_g: float
    total_annual_pm25_g: float
    community_1000_households_co2_tonnes: float


def compute_household_impact(
    commute_from_key: str,
    commute_to_key: str,
    commute_km_per_week: float,
    idling_mins_avoided_per_week: float,
    electricity_kwh_saved_per_week: float,
    grid_preset_label: str,
    biomass_kg_composted_per_month: float,
    weeks_per_year: int = 48,
) -> HouseholdImpactReport:
    """Calculate transparent personal and community pollution reductions from explicit inputs."""
    items: List[ActionImpactItem] = []

    # 1. Commute mode shift
    src_mode = TRANSPORT_MODES[commute_from_key]
    dst_mode = TRANSPORT_MODES[commute_to_key]
    delta_co2 = max(0.0, src_mode.co2e_kg_per_pkm - dst_mode.co2e_kg_per_pkm)
    delta_nox = max(0.0, src_mode.nox_g_per_pkm - dst_mode.nox_g_per_pkm)
    delta_pm25 = max(0.0, src_mode.pm25_g_per_pkm - dst_mode.pm25_g_per_pkm)
    km_wk = max(0.0, commute_km_per_week)

    if km_wk > 0 and delta_co2 > 0:
        wk_co2 = km_wk * delta_co2
        yr_co2 = wk_co2 * weeks_per_year
        yr_nox = km_wk * weeks_per_year * delta_nox
        yr_pm25 = km_wk * weeks_per_year * delta_pm25
        items.append(
            ActionImpactItem(
                action_name=f"Shift {km_wk:.0f} km/wk: {src_mode.label} → {dst_mode.label}",
                category="Transport",
                weekly_co2_kg=round(wk_co2, 2),
                annual_co2_kg=round(yr_co2, 1),
                annual_nox_g=round(yr_nox, 1),
                annual_pm25_g=round(yr_pm25, 2),
                formula_text=(
                    f"{km_wk:.1f} km/wk × {weeks_per_year} wks × "
                    f"({src_mode.co2e_kg_per_pkm:.3f} − {dst_mode.co2e_kg_per_pkm:.3f}) kg CO₂e/km = {yr_co2:.1f} kg/yr"
                ),
                source_citation=f"{src_mode.source}; {dst_mode.source}",
            )
        )

    # 2. Vehicle idling reduction
    idle_mins = max(0.0, idling_mins_avoided_per_week)
    if idle_mins > 0:
        idle_hrs_wk = idle_mins / 60.0
        wk_co2 = idle_hrs_wk * IDLING_CO2_KG_PER_HOUR
        yr_co2 = wk_co2 * 52.0
        # Conservative idling NOx ~3.5 g/hr, PM2.5 ~0.12 g/hr (US EPA MOVES light-duty hot idle range)
        yr_nox = idle_hrs_wk * 52.0 * 3.5
        yr_pm25 = idle_hrs_wk * 52.0 * 0.12
        items.append(
            ActionImpactItem(
                action_name=f"Eliminate {idle_mins:.0f} min/wk of Engine Idling",
                category="Transport",
                weekly_co2_kg=round(wk_co2, 2),
                annual_co2_kg=round(yr_co2, 1),
                annual_nox_g=round(yr_nox, 1),
                annual_pm25_g=round(yr_pm25, 2),
                formula_text=(
                    f"({idle_mins:.0f} min/wk ÷ 60) × 52 wks × {IDLING_CO2_KG_PER_HOUR:.2f} kg CO₂e/hr = {yr_co2:.1f} kg/yr"
                ),
                source_citation="US EPA / NRCan light-duty idling (~0.8 L/hr × 2.31 kg CO₂/L)",
            )
        )

    # 3. Household electricity conservation
    kwh_wk = max(0.0, electricity_kwh_saved_per_week)
    grid_meta = GRID_INTENSITY_PRESETS.get(
        grid_preset_label,
        GRID_INTENSITY_PRESETS["Global Grid Average (0.44 kg CO₂e/kWh)"],
    )
    grid_factor = float(grid_meta["factor"])
    if kwh_wk > 0:
        wk_co2 = kwh_wk * grid_factor
        yr_co2 = wk_co2 * 52.0
        items.append(
            ActionImpactItem(
                action_name=f"Save {kwh_wk:.1f} kWh/wk (Efficient Heating & Appliances)",
                category="Home Energy",
                weekly_co2_kg=round(wk_co2, 2),
                annual_co2_kg=round(yr_co2, 1),
                annual_nox_g=0.0,  # Avoid fabricating plant-specific stack NOx/PM
                annual_pm25_g=0.0,
                formula_text=f"{kwh_wk:.1f} kWh/wk × 52 wks × {grid_factor:.2f} kg CO₂e/kWh = {yr_co2:.1f} kg/yr",
                source_citation=str(grid_meta["source"]),
            )
        )

    # 4. Composting yard waste instead of open burning
    bio_kg_mo = max(0.0, biomass_kg_composted_per_month)
    if bio_kg_mo > 0:
        yr_kg = bio_kg_mo * 12.0
        yr_pm25 = yr_kg * OPEN_BIOMASS_PM25_G_PER_KG
        yr_co2 = yr_kg * OPEN_BIOMASS_CO2_KG_PER_KG
        wk_co2 = yr_co2 / 52.0
        items.append(
            ActionImpactItem(
                action_name=f"Compost {bio_kg_mo:.0f} kg/mo Leaves/Yard Waste (No Open Burning)",
                category="Zero Burning",
                weekly_co2_kg=round(wk_co2, 2),
                annual_co2_kg=round(yr_co2, 1),
                annual_nox_g=0.0,
                annual_pm25_g=round(yr_pm25, 1),
                formula_text=(
                    f"{bio_kg_mo:.1f} kg/mo × 12 mos × {OPEN_BIOMASS_CO2_KG_PER_KG:.2f} kg CO₂e/kg = {yr_co2:.1f} kg CO₂e/yr; "
                    f"× {OPEN_BIOMASS_PM25_G_PER_KG:.0f} g PM2.5/kg = {yr_pm25:,.0f} g PM2.5/yr avoided"
                ),
                source_citation="US EPA AP-42 Section 2.5 (Open Burning of Leaves/Yard Waste PM2.5 factor)",
            )
        )

    total_wk = round(sum(i.weekly_co2_kg for i in items), 2)
    total_yr = round(sum(i.annual_co2_kg for i in items), 1)
    total_mo = round(total_yr / 12.0, 1)
    total_nox = round(sum(i.annual_nox_g for i in items), 1)
    total_pm25 = round(sum(i.annual_pm25_g for i in items), 1)
    community_tonnes = round((total_yr * 1000.0) / 1000.0, 1)  # 1,000 households in metric tonnes

    return HouseholdImpactReport(
        items=items,
        total_weekly_co2_kg=total_wk,
        total_monthly_co2_kg=total_mo,
        total_annual_co2_kg=total_yr,
        total_annual_nox_g=total_nox,
        total_annual_pm25_g=total_pm25,
        community_1000_households_co2_tonnes=community_tonnes,
    )
