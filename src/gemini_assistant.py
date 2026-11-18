"""Google Gemini API integration for AirAware AI personalized urban air quality coaching.

Security & Integrity:
- Reads GEMINI_API_KEY strictly from environment variables via src.config.get_gemini_api_key().
- Never exposes API keys in frontend text, exceptions, or logs.
- Grounds every prompt in verified live Open-Meteo data and explicitly marks unavailable metrics.
- Gracefully falls back to clearly-labeled deterministic health guidance if Gemini is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional

import pandas as pd

from src.air_quality import AirQualitySnapshot, format_display_timestamp
from src.config import DEFAULT_GEMINI_MODEL, GEMINI_FALLBACK_MODELS, get_gemini_api_key

# Cache the first working Gemini model in-process to avoid repeated 404 fallbacks
_RESOLVED_GEMINI_MODEL: Optional[str] = None

SYSTEM_INSTRUCTION = """You are AirAware AI, an empathetic, science-grounded Urban Air Quality Assistant built to help families and communities navigate severe winter smog and urban air pollution.

STRICT DATA INTEGRITY RULES:
1. Only cite AQI and pollutant values explicitly supplied in the LIVE AIR QUALITY CONTEXT.
2. NEVER invent, estimate, or fill in missing AQI or pollutant readings. If a pollutant is marked "Unavailable", explicitly state that it is unavailable from the live feed.
3. Tailor recommendations specifically to the user's city, live AQI level, hourly forecast window (if available), and household profile (children, elderly, respiratory sensitivities, commuters, budget).
4. Prioritize practical, affordable, realistic actions suitable for severe winter smog (temperature inversions, morning/evening smog peaks, indoor filtration, N95 fit, low-emission routines, safe ventilation timing).
5. Use clean markdown formatting with clear headings and concise bullet points.
6. When AQI is high (>150) or respiratory conditions are mentioned, include a brief reminder to consult a healthcare professional for persistent or worsening symptoms.
"""


@dataclass
class FamilyProfile:
    """User-selected household context for personalizing AI recommendations."""

    household_groups: List[str] = field(default_factory=lambda: ["General Adults"])
    health_sensitivities: List[str] = field(default_factory=list)
    home_type: str = "Apartment / Flat"
    air_purifier_access: str = "No air purifier (need affordable/DIY options)"
    primary_commute: str = "Mixed / Public Transit"
    winter_smog_priority: str = "Protecting family health & planning daily routines"

    def to_prompt_block(self) -> str:
        groups = ", ".join(self.household_groups) if self.household_groups else "General Adults"
        sens = ", ".join(self.health_sensitivities) if self.health_sensitivities else "None specified"
        return (
            f"- Household Members: {groups}\n"
            f"- Health Sensitivities: {sens}\n"
            f"- Home Environment: {self.home_type}\n"
            f"- Indoor Filtration Access: {self.air_purifier_access}\n"
            f"- Typical Daily Commute: {self.primary_commute}\n"
            f"- Top Priority Today: {self.winter_smog_priority}"
        )


@dataclass
class AIResponse:
    """Result returned by Gemini assistant or its transparent deterministic fallback."""

    content: str
    is_ai_generated: bool
    model_used: str
    error_message: Optional[str] = None


def is_gemini_configured() -> bool:
    """Return True if a non-placeholder GEMINI_API_KEY is present in the environment."""
    return get_gemini_api_key() is not None


def build_live_context_block(snapshot: AirQualitySnapshot) -> str:
    """Serialize live Open-Meteo air quality data transparently for Gemini grounding."""
    local_time, tz_label = format_display_timestamp(
        snapshot.data_timestamp, snapshot.timezone_abbr, snapshot.timezone_name
    )
    us_aqi_str = (
        f"{snapshot.us_aqi:.0f} ({snapshot.us_aqi_category.name})"
        if snapshot.us_aqi is not None and snapshot.us_aqi_category is not None
        else "Unavailable"
    )
    eaqi_str = (
        f"{snapshot.european_aqi:.0f} ({snapshot.european_aqi_label})"
        if snapshot.european_aqi is not None
        else "Unavailable"
    )

    pollutant_lines: List[str] = []
    for p in snapshot.pollutants.values():
        if p.available and p.value is not None:
            ratio_note = f" [{p.who_ratio:.1f}x WHO guideline]" if p.who_ratio is not None else ""
            pollutant_lines.append(f"  - {p.formula} ({p.name}): {p.value:.1f} {p.unit}{ratio_note}")
        else:
            pollutant_lines.append(f"  - {p.formula} ({p.name}): Unavailable (not reported by API)")

    fs = snapshot.forecast_summary
    if fs.available:
        forecast_block = (
            f"- Next {fs.hours_analyzed}h Best Outdoor Window: {fs.best_window_label} (avg US AQI ~{fs.best_window_avg_aqi})\n"
            f"- Next {fs.hours_analyzed}h Peak Smog Hour: {fs.worst_window_label} (US AQI ~{fs.worst_window_aqi})\n"
            f"- Forecast Note: {fs.note}"
        )
    else:
        forecast_block = f"- Hourly Forecast: Unavailable ({fs.note})"

    return (
        f"LIVE AIR QUALITY CONTEXT (Source: {snapshot.source_name}):\n"
        f"- Location: {snapshot.location.display_name} ({snapshot.location.coordinates_label})\n"
        f"- Data Timestamp: {local_time} · {tz_label}\n"
        f"- Live US AQI: {us_aqi_str}\n"
        f"- Live European AQI: {eaqi_str}\n"
        f"- Live Pollutants:\n" + "\n".join(pollutant_lines) + "\n"
        f"{forecast_block}"
    )


def _call_gemini(prompt: str, temperature: float = 0.4) -> AIResponse:
    """Invoke Google Gemini via the official google-genai SDK with safe error handling."""
    api_key = get_gemini_api_key()
    if not api_key:
        return AIResponse(
            content="",
            is_ai_generated=False,
            model_used="none",
            error_message=(
                "GEMINI_API_KEY is not configured in your environment. "
                "Add it to a local `.env` file (see `.env.example`) and restart Streamlit to enable live Gemini AI responses."
            ),
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return AIResponse(
            content="",
            is_ai_generated=False,
            model_used="none",
            error_message="The `google-genai` package is not installed. Run `pip install -r requirements.txt`.",
        )

    global _RESOLVED_GEMINI_MODEL

    candidate_order: List[str] = []
    if _RESOLVED_GEMINI_MODEL:
        candidate_order.append(_RESOLVED_GEMINI_MODEL)
    candidate_order.append(DEFAULT_GEMINI_MODEL)
    candidate_order.extend(GEMINI_FALLBACK_MODELS)

    # Deduplicate while preserving priority order
    models_to_try = list(dict.fromkeys(m.strip() for m in candidate_order if m and m.strip()))

    last_error = ""
    client = genai.Client(api_key=api_key)

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=temperature,
                    max_output_tokens=1400,
                ),
            )
            text = (response.text or "").strip()
            if text:
                _RESOLVED_GEMINI_MODEL = model_name
                return AIResponse(
                    content=text,
                    is_ai_generated=True,
                    model_used=model_name,
                )
            last_error = "Gemini returned an empty response."
        except Exception as exc:
            # Sanitize error message so no API key material could ever leak
            err_str = str(exc).replace(api_key, "[REDACTED]")
            err_str = re.sub(r"(?:AIza|AQ\.)[0-9A-Za-z\-_.]{10,}", "[REDACTED]", err_str)
            err_str = re.sub(r"(?i)(api[_-]?key|key)\s*[=:]\s*[^\s,&'\"]+", r"\1=[REDACTED]", err_str)
            lower = err_str.lower()
            if (
                "api_key_invalid" in lower
                or "api key not valid" in lower
                or "invalid api key" in lower
                or "unauthenticated" in lower
                or "permission_denied" in lower
                or "401" in lower
                or "403" in lower
            ):
                return AIResponse(
                    content="",
                    is_ai_generated=False,
                    model_used=model_name,
                    error_message="Gemini API authentication failed. Please verify that your `GEMINI_API_KEY` environment variable is valid.",
                )
            if "429" in lower or "quota" in lower or "resource_exhausted" in lower:
                return AIResponse(
                    content="",
                    is_ai_generated=False,
                    model_used=model_name,
                    error_message="Gemini API rate limit or quota reached. Showing live-data deterministic guidance instead.",
                )
            if "404" in lower or "not_found" in lower or "no longer available" in lower:
                last_error = f"Configured Gemini model (`{model_name}`) is no longer available; fallback models also failed."
                continue
            last_error = "Unable to reach Google Gemini right now. Showing verified live-data rule guidance instead."

    return AIResponse(
        content="",
        is_ai_generated=False,
        model_used=models_to_try[-1],
        error_message=last_error or "Unable to reach Google Gemini API right now.",
    )


def _deterministic_briefing_fallback(snapshot: AirQualitySnapshot, profile: FamilyProfile) -> str:
    """Evidence-based, live-data-grounded fallback when Gemini API is not configured."""
    cat = snapshot.us_aqi_category
    city = snapshot.location.display_name
    aqi_txt = f"{snapshot.us_aqi:.0f} ({cat.name})" if snapshot.us_aqi is not None and cat else "Unavailable"
    dom = snapshot.dominant_pollutant
    dom_txt = (
        f"**{dom.formula}** at `{dom.value:.1f} {dom.unit}` ({dom.who_ratio:.1f}× WHO 2021 guideline)"
        if dom and dom.value is not None and dom.who_ratio is not None
        else "No dominant pollutant exceeded a reference threshold or data is unavailable"
    )

    fs = snapshot.forecast_summary
    window_txt = (
        f"Cleanest upcoming 2-hour window: **{fs.best_window_label}** (avg US AQI ~`{fs.best_window_avg_aqi}`). "
        f"Peak smog expected around **{fs.worst_window_label}** (US AQI ~`{fs.worst_window_aqi}`)."
        if fs.available
        else "Hourly forecast timing is currently unavailable from the API."
    )

    groups = ", ".join(profile.household_groups) if profile.household_groups else "your household"
    sens_note = ""
    if profile.health_sensitivities:
        sens_note = (
            f"\n- **Sensitive-Group Alert ({', '.join(profile.health_sensitivities)})**: "
            "Keep rescue inhalers or prescribed medications accessible, avoid peak traffic hours, and monitor for coughing, wheezing, or eye/throat irritation."
        )

    outdoor = cat.outdoor_guidance if cat else "Check local official advisories before prolonged outdoor activity."
    vent = cat.ventilation_advice if cat else "Monitor outdoor haze visually before opening windows."
    mask = cat.mask_advice if cat else "Keep certified N95/KN95 masks on hand during winter smog season."

    return (
        f"### Live Air Quality Action Plan for {city}\n\n"
        f"- **Current US AQI**: `{aqi_txt}`\n"
        f"- **Primary Concern**: {dom_txt}\n"
        f"- **Household Tailoring**: Prepared for **{groups}** ({profile.home_type})\n\n"
        f"#### 1. Immediate Protective Priorities\n"
        f"- **Outdoor Activity**: {outdoor}\n"
        f"- **Respiratory Protection**: {mask}\n"
        f"- **Ventilation Protocol**: {vent}{sens_note}\n\n"
        f"#### 2. Timing Your Day (Live Forecast)\n"
        f"- {window_txt}\n\n"
        f"#### 3. Winter Smog Indoor & Low-Emission Habits\n"
        f"- Avoid indoor smoke sources (incense, candles, unvented cooking/frying without exhaust).\n"
        f"- Wet-mop floors instead of dry sweeping to keep settled PM2.5/PM10 from resuspending.\n"
        f"- Batch errands and avoid vehicle idling during cold winter mornings when temperature inversions trap exhaust near street level.\n\n"
        f"*Note: This summary uses deterministic public-health rules grounded in your live Open-Meteo data. Configure `GEMINI_API_KEY` in `.env` for deeply personalized Google Gemini coaching.*"
    )


def generate_personalized_briefing(snapshot: AirQualitySnapshot, profile: FamilyProfile) -> AIResponse:
    """Generate a personalized air-quality & winter-smog action briefing via Gemini."""
    context = build_live_context_block(snapshot)
    prompt = (
        f"{context}\n\n"
        f"USER HOUSEHOLD PROFILE:\n{profile.to_prompt_block()}\n\n"
        "TASK:\n"
        "Create a clear, compassionate, personalized air quality action briefing for today with these 4 concise sections:\n"
        "1. **Situation Snapshot & Dominant Risk** (cite only exact live numbers from context; mention winter inversion / smog dynamics if relevant)\n"
        "2. **Tailored Family Protection Plan** (specific guidance for the exact household members & health sensitivities listed)\n"
        "3. **Smart Timing & Ventilation Strategy** (use the exact live forecast windows if available)\n"
        "4. **3 Practical Low-Emission Actions for Today** (realistic for their home & commute)\n"
        "Keep it actionable, under 450 words, and easy for a busy family to scan."
    )
    res = _call_gemini(prompt, temperature=0.35)
    if res.is_ai_generated:
        return res
    return AIResponse(
        content=_deterministic_briefing_fallback(snapshot, profile),
        is_ai_generated=False,
        model_used="deterministic-fallback",
        error_message=res.error_message,
    )


def generate_smart_routine_plan(snapshot: AirQualitySnapshot, profile: FamilyProfile) -> AIResponse:
    """Generate an AI hour-by-hour low-emission daily routine grounded in live hourly AQI."""
    context = build_live_context_block(snapshot)
    hourly_preview = ""
    if not snapshot.hourly_df.empty:
        rows = []
        for _, r in snapshot.hourly_df.head(24).iterrows():
            t_str = r["time"].strftime("%I:%M %p (%b %d)")
            aqi_v = f"{float(r['us_aqi']):.0f}" if pd.notna(r["us_aqi"]) else "N/A"
            pm25_v = f"{float(r['pm2_5']):.1f}" if pd.notna(r["pm2_5"]) else "N/A"
            rows.append(f"  {t_str}: US AQI={aqi_v}, PM2.5={pm25_v} μg/m³")
        hourly_preview = "NEXT 24-HOUR LIVE FORECAST:\n" + "\n".join(rows)

    prompt = (
        f"{context}\n\n"
        f"{hourly_preview}\n\n"
        f"USER HOUSEHOLD PROFILE:\n{profile.to_prompt_block()}\n\n"
        "TASK:\n"
        "Build a practical **Smart Low-Emission Daily Routine** structured into 4 time blocks:\n"
        "- **Morning (6 AM – 11 AM)**\n"
        "- **Midday / Afternoon (11 AM – 4 PM)**\n"
        "- **Evening (4 PM – 8 PM)**\n"
        "- **Night / Sleep Prep (8 PM – 6 AM)**\n\n"
        "For each block:\n"
        "1. Reference the actual forecasted AQI trend (without fabricating missing hours).\n"
        "2. Suggest safe outdoor vs indoor activities & exercise timing.\n"
        "3. Include one low-emission habit (cooking, commuting, heating/energy) that avoids adding to urban smog.\n"
        "4. Note practical precautions (masks, hydration, ventilation)."
    )
    res = _call_gemini(prompt, temperature=0.4)
    if res.is_ai_generated:
        return res

    fs = snapshot.forecast_summary
    cat = snapshot.us_aqi_category
    aqi_val = snapshot.us_aqi
    aqi_lbl = f"{aqi_val:.0f} ({cat.name})" if aqi_val is not None and cat else "Unavailable"
    best_line = (
        f"Best forecast window: **{fs.best_window_label}** (avg US AQI ~`{fs.best_window_avg_aqi}`)"
        if fs.available
        else "Hourly forecast window unavailable."
    )
    worst_line = (
        f"Peak smog expected around **{fs.worst_window_label}** (US AQI ~`{fs.worst_window_aqi}`)."
        if fs.available
        else ""
    )
    groups_txt = ", ".join(profile.household_groups) if profile.household_groups else "General Adults"
    sens_txt = (
        f" Extra care for **{', '.join(profile.health_sensitivities)}**: keep rescue medications handy and limit exertion near traffic."
        if profile.health_sensitivities
        else ""
    )

    if aqi_val is not None and aqi_val <= 50:
        morning = (
            "Air quality is currently **Good**—ideal for outdoor walks, jogging, cycling, or school play. "
            "Open windows briefly for natural cross-ventilation and walk/cycle short errands instead of driving."
        )
        midday = (
            f"Conditions remain favorable for outdoor activities and errands. {best_line}. "
            "Use lids while cooking and batch any vehicle trips to keep local emissions low."
        )
        evening = (
            f"Enjoy outdoor family time away from heavy traffic junctions. {worst_line} "
            "Choose public transit, walking, or carpooling to help keep neighborhood air clean."
        )
        night = (
            "Light natural ventilation is safe if outdoor air remains clean; avoid indoor smoke sources (incense, candles) "
            "and switch off standby appliances to cut energy emissions."
        )
    elif aqi_val is not None and aqi_val <= 100:
        morning = (
            "Air quality is **Moderate**—most people can exercise outdoors, while sensitive individuals should choose quieter side streets "
            "and avoid heavy traffic idling."
        )
        midday = (
            f"Schedule longer outdoor activities and brief cross-ventilation during the cleanest daylight hours. {best_line}. "
            "Combine errands into one trip to avoid cold-start exhaust."
        )
        evening = (
            f"Rush-hour traffic can push PM2.5 and NO₂ upward. {worst_line} "
            "Close road-facing windows during rush hour, use kitchen exhaust/lids while cooking, and prefer transit or carpooling."
        )
        night = (
            "Keep traffic-facing windows closed overnight if haze builds; wet-mop floors instead of dry sweeping and avoid burning candles or incense."
        )
    elif aqi_val is not None and aqi_val <= 150:
        morning = (
            "Air quality is **Unhealthy for Sensitive Groups**. Children, older adults, and anyone with asthma/heart sensitivities should move vigorous workouts indoors "
            "and wear a snug N95/KN95 mask near busy roads. Avoid engine idling."
        )
        midday = (
            f"Use the cleanest afternoon window for essential outdoor errands; keep ventilation brief and only if AQI drops ≤ 100. {best_line}. "
            "Use energy-efficient cooking (pressure cooker/lids) to avoid indoor PM2.5 spikes."
        )
        evening = (
            f"Evening traffic and cooling air can intensify pollution. {worst_line} "
            "Shift play and cardio indoors, keep windows closed, and opt for enclosed transit or carpooling."
        )
        night = (
            "Keep bedroom windows closed, run indoor filtration if available (HEPA or DIY MERV-13 fan), and avoid all indoor combustion."
        )
    else:
        morning = (
            "Air quality is **elevated/unhealthy** (or unconfirmed). Winter inversions trap overnight traffic and heating emissions near street level—move early jogs and school play indoors, "
            "wear a properly sealed N95/KN95/FFP2 mask for essential commutes, and avoid vehicle idling."
        )
        midday = (
            f"Avoid strenuous outdoor activity; limit outdoor time to essential errands during the lowest-AQI window. {best_line}. "
            "Do not open windows unless live AQI drops ≤ 100."
        )
        evening = (
            f"Rush-hour exhaust plus cooling air causes PM2.5 and NO₂ to climb further. {worst_line} "
            "Keep windows sealed, use lids and exhaust hoods while cooking, and choose enclosed Metro/Bus or carpooling."
        )
        night = (
            "Maintain a dedicated clean-air sleeping room with doors/windows sealed, run filtration continuously if available, "
            "avoid incense/candles, and block drafty door gaps."
        )

    fallback = (
        f"### Smart Daily Routine for {snapshot.location.display_name}\n\n"
        f"- **Live US AQI**: `{aqi_lbl}` · **Tailored for**: {groups_txt} ({profile.home_type})\n\n"
        f"- **Morning (6 AM – 11 AM)**: {morning}{sens_txt}\n"
        f"- **Midday / Afternoon (11 AM – 4 PM)**: {midday}\n"
        f"- **Evening (4 PM – 8 PM)**: {evening}\n"
        f"- **Night / Sleep Prep (8 PM – 6 AM)**: {night}\n\n"
        f"*Note: This schedule uses deterministic live-data rules (non-AI fallback). Configure `GEMINI_API_KEY` in `.env` for live Google Gemini personalization.*"
    )
    return AIResponse(
        content=fallback,
        is_ai_generated=False,
        model_used="deterministic-fallback",
        error_message=res.error_message,
    )


def generate_indoor_air_plan(
    snapshot: AirQualitySnapshot,
    profile: FamilyProfile,
    budget_tier: str,
) -> AIResponse:
    """Generate a tailored, budget-conscious indoor air quality & ventilation protocol."""
    context = build_live_context_block(snapshot)
    prompt = (
        f"{context}\n\n"
        f"USER HOUSEHOLD PROFILE:\n{profile.to_prompt_block()}\n"
        f"- Budget Focus: {budget_tier}\n\n"
        "TASK:\n"
        "Provide a highly practical, affordable **Indoor Air Quality & Ventilation Plan** tailored to the live outdoor AQI and this home:\n"
        "1. **Right-Now Ventilation Decision** (Open, Brief Window, or Keep Sealed — tied to live AQI and forecast)\n"
        "2. **Affordable / DIY Clean-Air Hacks** matched to their budget (e.g., DIY Corsi-Rosenthal box fan + MERV-13 filter, clean-air bedroom setup, draft sealing, wet mopping, kitchen exhaust management)\n"
        "3. **Hidden Indoor Pollution Traps to Eliminate** (cooking PM2.5/NO₂, incense, dry sweeping, unvented heaters)\n"
        "4. **Quick Evening Reset Checklist** (5 simple steps)."
    )
    res = _call_gemini(prompt, temperature=0.4)
    if res.is_ai_generated:
        return res

    cat = snapshot.us_aqi_category
    vent_line = cat.ventilation_advice if cat else "Verify outdoor AQI before opening windows."
    fallback = (
        f"### Indoor Air Quality Protocol ({budget_tier})\n\n"
        f"- **Ventilation Decision**: {vent_line}\n"
        f"- **Affordable DIY Filtration**: A 20-inch box fan taped to one or four MERV-13 furnace filters (Corsi-Rosenthal box) removes fine PM2.5 effectively at a fraction of commercial purifier costs.\n"
        f"- **Create One Clean-Air Room**: Prioritize sealing and filtering the main sleeping bedroom first so lungs get 8 hours of cleaner recovery air every night.\n"
        f"- **Kitchen & Dust Control**: Always run the kitchen exhaust fan or crack only the kitchen window while cooking, keep lids on pots, wet-mop instead of dry sweeping, and avoid burning candles or incense."
    )
    return AIResponse(
        content=fallback,
        is_ai_generated=False,
        model_used="deterministic-fallback",
        error_message=res.error_message,
    )


def answer_followup_question(
    snapshot: AirQualitySnapshot,
    profile: FamilyProfile,
    question: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> AIResponse:
    """Answer a user's free-form question grounded in live air quality data and chat history."""
    context = build_live_context_block(snapshot)
    history_lines: List[str] = []
    for turn in (chat_history or [])[-6:]:
        role = "User" if turn.get("role") == "user" else "AirAware AI"
        history_lines.append(f"{role}: {turn.get('content', '')[:500]}")
    history_block = "\n".join(history_lines) if history_lines else "No previous turns."

    prompt = (
        f"{context}\n\n"
        f"USER HOUSEHOLD PROFILE:\n{profile.to_prompt_block()}\n\n"
        f"RECENT CONVERSATION:\n{history_block}\n\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        "Answer clearly, concisely, and helpfully using ONLY the verified live data above. "
        "Never fabricate missing sensor metrics."
    )
    res = _call_gemini(prompt, temperature=0.45)
    if res.is_ai_generated:
        return res

    cat = snapshot.us_aqi_category
    aqi_desc = f"{snapshot.us_aqi:.0f} ({cat.name})" if snapshot.us_aqi is not None and cat else "Unavailable"
    fallback = (
        f"I cannot reach Google Gemini right now, so here is verified live context for **{snapshot.location.display_name}** "
        f"to help answer your question:\n\n"
        f"- **Live US AQI**: `{aqi_desc}`\n"
        f"- **Outdoor Guidance**: {cat.outdoor_guidance if cat else 'Monitor local conditions.'}\n"
        f"- **Ventilation Guidance**: {cat.ventilation_advice if cat else 'Check local haze before opening windows.'}\n"
        f"- **Mask Guidance**: {cat.mask_advice if cat else 'Use N95/KN95 during heavy smog.'}\n\n"
        f"To enable conversational AI Q&A, set `GEMINI_API_KEY` in your `.env` file and restart the app."
    )
    return AIResponse(
        content=fallback,
        is_ai_generated=False,
        model_used="deterministic-fallback",
        error_message=res.error_message,
    )
