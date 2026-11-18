"""AirAware AI — Urban Air Quality Assistant (Hack2Skill PromptWars Challenge 6).

Main Streamlit entry point uniting:
1. Live Air Quality Dashboard (Open-Meteo Geocoding + Air Quality APIs)
2. AI Smart Assistant (Google Gemini API + transparent deterministic fallback)
3. Smart Daily Routine (forecast-timed outdoor windows & low-emission habits)
4. Indoor Air Quality Hacks (AQI-driven ventilation & affordable clean-air DIY)
5. Eco-Friendly Travel (AQI-safe commute options & transparent emission savings)
6. Pollution Impact Tracker (auditable, source-cited household & community impact)
"""

from __future__ import annotations

import html
from typing import List, Optional

import streamlit as st

from src.air_quality import (
    AirQualityServiceError,
    AirQualitySnapshot,
    GeoLocation,
    fetch_air_quality,
    format_display_timestamp,
    search_cities,
)
from src.charts import (
    create_aqi_gauge,
    create_hourly_forecast_chart,
    create_impact_breakdown_chart,
    create_pollutant_trend_chart,
    create_pollutant_who_chart,
    create_travel_comparison_chart,
)
from src.config import (
    APP_NAME,
    APP_TAGLINE,
    DEFAULT_CITY,
    FEATURED_CITIES,
    US_AQI_CATEGORIES,
)
from src.gemini_assistant import (
    AIResponse,
    FamilyProfile,
    answer_followup_question,
    generate_indoor_air_plan,
    generate_personalized_briefing,
    generate_smart_routine_plan,
    is_gemini_configured,
)
from src.impact_calculator import (
    GRID_INTENSITY_PRESETS,
    TRANSPORT_MODES,
    compute_household_impact,
    evaluate_eco_travel_options,
)
from src.styles import (
    inject_custom_css,
    render_hero_banner,
    render_kpi_card,
    render_pollutant_card,
    render_section_header,
)

st.set_page_config(
    page_title=f"{APP_NAME} · Urban Air Quality Assistant",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()


# ---------------------------------------------------------------------------
# Cached API wrappers (short TTL to keep readings fresh without hammering API)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def cached_search_cities(query: str) -> List[GeoLocation]:
    return search_cities(query, count=8)


@st.cache_data(ttl=300, show_spinner=False)
def cached_fetch_air_quality(
    name: str,
    latitude: float,
    longitude: float,
    country: str,
    admin1: str,
    country_code: str,
    tz: str,
    population: Optional[int],
) -> AirQualitySnapshot:
    loc = GeoLocation(
        name=name,
        latitude=latitude,
        longitude=longitude,
        country=country,
        admin1=admin1,
        country_code=country_code,
        timezone=tz,
        population=population,
    )
    return fetch_air_quality(loc)


def load_city_data(city_query: str) -> None:
    """Resolve city via Geocoding API and fetch live Open-Meteo Air Quality data."""
    st.session_state["api_error"] = None
    try:
        matches = cached_search_cities(city_query)
        st.session_state["city_matches"] = matches
        st.session_state["city_search_ver"] = st.session_state.get("city_search_ver", 0) + 1
        selected = matches[0]
        st.session_state["selected_location"] = selected
        st.session_state["snapshot"] = cached_fetch_air_quality(
            selected.name,
            selected.latitude,
            selected.longitude,
            selected.country,
            selected.admin1,
            selected.country_code,
            selected.timezone,
            selected.population,
        )
        # Reset city-specific cached AI outputs when switching location
        for key in ("ai_briefing", "ai_routine", "ai_indoor", "ai_indoor_tier", "chat_messages"):
            st.session_state.pop(key, None)
    except AirQualityServiceError as exc:
        st.session_state["api_error"] = exc


def select_specific_location(loc: GeoLocation) -> None:
    """Switch to a disambiguated city match and fetch its live AQI."""
    st.session_state["api_error"] = None
    try:
        st.session_state["selected_location"] = loc
        st.session_state["snapshot"] = cached_fetch_air_quality(
            loc.name,
            loc.latitude,
            loc.longitude,
            loc.country,
            loc.admin1,
            loc.country_code,
            loc.timezone,
            loc.population,
        )
        for key in ("ai_briefing", "ai_routine", "ai_indoor", "ai_indoor_tier", "chat_messages"):
            st.session_state.pop(key, None)
    except AirQualityServiceError as exc:
        st.session_state["api_error"] = exc


def _init_session_state() -> None:
    if "city_query" not in st.session_state:
        st.session_state["city_query"] = DEFAULT_CITY
    if "nav_section" not in st.session_state:
        st.session_state["nav_section"] = "Air Quality Dashboard"
    if "initialized" not in st.session_state:
        st.session_state["initialized"] = True
        load_city_data(st.session_state["city_query"])


def _get_family_profile() -> FamilyProfile:
    return FamilyProfile(
        household_groups=st.session_state.get("profile_groups", ["Adults", "School Children"]),
        health_sensitivities=st.session_state.get("profile_sensitivities", []),
        home_type=st.session_state.get("profile_home_type", "Apartment / Flat"),
        air_purifier_access=st.session_state.get(
            "profile_purifier", "No air purifier (need affordable/DIY options)"
        ),
        primary_commute=st.session_state.get("profile_commute", "Mixed / Public Transit"),
        winter_smog_priority=st.session_state.get(
            "profile_priority", "Protecting family health & planning daily routines"
        ),
    )


def _render_ai_response_card(response: AIResponse, heading: str) -> None:
    """Render an AI or deterministic fallback response with transparent provenance badge."""
    if response.is_ai_generated:
        badge = f'<span class="aa-pill aa-pill-live">✨ Google Gemini ({html.escape(response.model_used)})</span>'
    else:
        badge = '<span class="aa-pill aa-pill-unavail">📋 Live-Data Rule Guidance (Non-AI Fallback)</span>'

    if response.error_message:
        st.info(response.error_message, icon="ℹ️")

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'flex-wrap:wrap;gap:0.5rem;margin-bottom:0.55rem;">'
        f'<strong style="font-size:1.02rem;color:#F8FAFC;">{html.escape(heading)}</strong>'
        f"{badge}</div>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown(response.content)


# ---------------------------------------------------------------------------
# Sidebar Navigation, City Search & Family Profile
# ---------------------------------------------------------------------------
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="aa-brand-box">
                <div class="aa-brand-title">🌿 {html.escape(APP_NAME)}</div>
                <div class="aa-brand-sub">Urban Winter Smog Copilot</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Navigation
        nav_options = [
            "Air Quality Dashboard",
            "AI Smart Assistant",
            "Smart Daily Routine",
            "Indoor Air Hacks",
            "Eco-Friendly Travel",
            "Pollution Impact Tracker",
        ]
        nav_icons = {
            "Air Quality Dashboard": "📊 Air Quality Dashboard",
            "AI Smart Assistant": "🤖 AI Smart Assistant",
            "Smart Daily Routine": "🗓️ Smart Daily Routine",
            "Indoor Air Hacks": "🏠 Indoor Air Hacks",
            "Eco-Friendly Travel": "🚲 Eco-Friendly Travel",
            "Pollution Impact Tracker": "🌱 Pollution Impact Tracker",
        }
        selected_nav = st.radio(
            "Navigation",
            options=nav_options,
            format_func=lambda k: nav_icons[k],
            key="nav_section",
            label_visibility="collapsed",
        )

        st.divider()

        # City Search Form
        st.markdown("##### 📍 Location Detection")
        with st.form("city_search_form", clear_on_submit=False):
            city_input = st.text_input(
                "Enter your city",
                value=st.session_state.get("city_query", DEFAULT_CITY),
                placeholder="e.g., New Delhi, Lahore, London...",
                help="Uses Open-Meteo Geocoding API to resolve coordinates and timezone.",
            )
            c1, c2 = st.columns([1.45, 1])
            with c1:
                submitted = st.form_submit_button("Fetch Live AQI", type="primary", use_container_width=True)
            with c2:
                refreshed = st.form_submit_button("Refresh", use_container_width=True)

        if submitted:
            cleaned_city = city_input.strip()
            if cleaned_city:
                st.session_state["city_query"] = cleaned_city
            with st.spinner(f"Fetching live air quality for {cleaned_city or 'your query'}..."):
                load_city_data(cleaned_city)
        elif refreshed:
            cached_fetch_air_quality.clear()
            loc: Optional[GeoLocation] = st.session_state.get("selected_location")
            with st.spinner("Refreshing live Open-Meteo data..."):
                if loc:
                    select_specific_location(loc)
                else:
                    load_city_data(st.session_state.get("city_query", DEFAULT_CITY))

        # Disambiguation selector when multiple cities match
        matches: List[GeoLocation] = st.session_state.get("city_matches") or []
        current_loc: Optional[GeoLocation] = st.session_state.get("selected_location")
        if len(matches) > 1 and current_loc:
            labels = [f"{m.display_name} ({m.coordinates_label})" for m in matches]
            try:
                cur_idx = next(
                    i for i, m in enumerate(matches)
                    if m.latitude == current_loc.latitude and m.longitude == current_loc.longitude
                )
            except StopIteration:
                cur_idx = 0

            search_ver = st.session_state.get("city_search_ver", 0)
            chosen_idx = st.selectbox(
                "Did you mean another city?",
                options=list(range(len(matches))),
                index=cur_idx,
                format_func=lambda i: labels[i],
                key=f"city_disambiguate_{search_ver}",
            )
            if chosen_idx != cur_idx:
                with st.spinner(f"Loading {matches[chosen_idx].display_name}..."):
                    select_specific_location(matches[chosen_idx])
                st.rerun()

        # Quick city switcher
        quick_city = st.selectbox(
            "Quick-select city",
            options=["— Choose a city —"] + FEATURED_CITIES,
            index=0,
            key="quick_city_picker",
        )
        if quick_city != "— Choose a city —":
            if st.button(f"Load {quick_city}", use_container_width=True):
                st.session_state["city_query"] = quick_city
                with st.spinner(f"Fetching live air quality for {quick_city}..."):
                    load_city_data(quick_city)
                st.rerun()

        st.divider()

        # Personalization Profile Expander
        with st.expander("👨‍👩‍👧‍👦 Family & Home Profile", expanded=False):
            st.caption("Personalizes AI Smart Assistant, Daily Routine, and Indoor Hacks.")
            st.multiselect(
                "Household members",
                options=["Infants / Toddlers", "School Children", "Adults", "Older Adults (60+)", "Pregnant Member", "Pets"],
                default=st.session_state.get("profile_groups", ["Adults", "School Children"]),
                key="profile_groups",
            )
            st.multiselect(
                "Health sensitivities",
                options=["Asthma", "Allergies / Sinus", "COPD / Bronchitis", "Heart / Cardiovascular", "Outdoor Worker"],
                default=st.session_state.get("profile_sensitivities", []),
                key="profile_sensitivities",
            )
            st.selectbox(
                "Home type",
                options=["Apartment / Flat", "Independent House", "Shared / Hostel Room", "Ground-Floor Near Traffic"],
                key="profile_home_type",
            )
            st.selectbox(
                "Air filtration access",
                options=[
                    "No air purifier (need affordable/DIY options)",
                    "1 HEPA purifier (bedroom)",
                    "Multiple HEPA purifiers",
                    "Central HVAC with MERV-13 filter",
                ],
                key="profile_purifier",
            )
            st.selectbox(
                "Typical commute",
                options=["Mixed / Public Transit", "Petrol/Diesel Car", "Two-Wheeler / Scooter", "Walking / Cycling", "Work / Study from Home"],
                key="profile_commute",
            )
            st.text_input(
                "Top priority today",
                value=st.session_state.get("profile_priority", "Protecting family health & planning daily routines"),
                key="profile_priority",
            )

        st.divider()

        # System & API Status (Never exposes keys!)
        gemini_ready = is_gemini_configured()
        snap: Optional[AirQualitySnapshot] = st.session_state.get("snapshot")
        om_status = (
            '<span class="aa-pill aa-pill-live">● Open-Meteo Live</span>'
            if snap is not None
            else '<span class="aa-pill aa-pill-unavail">○ Open-Meteo Idle</span>'
        )
        ai_status = (
            '<span class="aa-pill aa-pill-live">● Gemini API Ready</span>'
            if gemini_ready
            else '<span class="aa-pill aa-pill-unavail">○ Gemini Key Not Set</span>'
        )
        st.markdown(
            f'<div style="display:flex;flex-direction:column;gap:0.45rem;">{om_status}{ai_status}</div>',
            unsafe_allow_html=True,
        )
        if not gemini_ready:
            st.caption("Set `GEMINI_API_KEY` in `.env` to enable live Google Gemini responses.")

    return selected_nav


# ---------------------------------------------------------------------------
# Reusable Data Timestamp & Integrity Strip
# ---------------------------------------------------------------------------
def render_timestamp_strip(snapshot: AirQualitySnapshot) -> None:
    local_time, tz_label = format_display_timestamp(
        snapshot.data_timestamp, snapshot.timezone_abbr, snapshot.timezone_name
    )
    st.markdown(
        f"""
        <div class="aa-timestamp-bar">
            <span>🕒 <strong>Data Timestamp:</strong> {html.escape(local_time)} ({html.escape(tz_label)})</span>
            <span>🔄 <strong>Fetched:</strong> {html.escape(snapshot.fetched_at_utc)}</span>
            <span>📡 <strong>Source:</strong> {html.escape(snapshot.source_name)}</span>
            <span>✅ <strong>Live Metrics:</strong> {snapshot.available_pollutant_count}/{len(snapshot.pollutants)} pollutants reported</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Feature 1: AIR QUALITY DASHBOARD
# ---------------------------------------------------------------------------
def render_dashboard_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)

    cat = snapshot.us_aqi_category
    us_aqi_str = f"{snapshot.us_aqi:.0f}" if snapshot.us_aqi is not None else "Unavailable"
    cat_name = cat.name if cat else "Unavailable"
    cat_color = cat.color if cat else "#94A3B8"

    # Top Hero Metrics + Gauge Row
    gauge_col, summary_col = st.columns([1.15, 1.85], gap="large")
    with gauge_col:
        st.plotly_chart(create_aqi_gauge(snapshot.us_aqi, cat), use_container_width=True, config={"displayModeBar": False})

    with summary_col:
        # Category Health Advisory Card
        advisory_text = (
            cat.health_summary
            if cat
            else "Live US AQI was not reported by Open-Meteo for this coordinate. Inspect individual live pollutants below."
        )
        outdoor_txt = cat.outdoor_guidance if cat else "Monitor local municipal air quality stations."
        mask_txt = cat.mask_advice if cat else "Carry an N95/KN95 mask during visible winter smog."
        st.markdown(
            f"""
            <div class="aa-card" style="border-left: 4px solid {cat_color};">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
                    <span class="aa-kpi-label" style="margin:0;">Current Air Quality Advisory</span>
                    <span class="aa-pill" style="background:{cat.bg_tint if cat else 'rgba(100,116,139,0.2)'};color:{cat_color};border:1px solid {cat_color};">
                        {cat.emoji if cat else '⚪'} {html.escape(cat_name)} (US AQI {html.escape(us_aqi_str)})
                    </span>
                </div>
                <p style="margin:0.65rem 0 0.7rem 0;color:#E2E8F0;font-size:0.95rem;line-height:1.5;">
                    {html.escape(advisory_text)}
                </p>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:0.65rem;font-size:0.84rem;color:#CBD5E1;">
                    <div style="background:rgba(8,16,30,0.55);padding:0.6rem 0.75rem;border-radius:10px;">
                        <strong style="color:#34D399;">🏃 Outdoor:</strong> {html.escape(outdoor_txt)}
                    </div>
                    <div style="background:rgba(8,16,30,0.55);padding:0.6rem 0.75rem;border-radius:10px;">
                        <strong style="color:#34D399;">😷 Masking:</strong> {html.escape(mask_txt)}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Quick Secondary KPIs
        k1, k2, k3 = st.columns(3)
        with k1:
            eaqi_val = f"{snapshot.european_aqi:.0f}" if snapshot.european_aqi is not None else "N/A"
            render_kpi_card(
                "European AQI",
                eaqi_val,
                f"Category: {snapshot.european_aqi_label}",
                value_color=snapshot.european_aqi_color,
            )
        with k2:
            dom = snapshot.dominant_pollutant
            if dom and dom.value is not None and dom.who_ratio is not None:
                render_kpi_card(
                    "Dominant Pollutant",
                    dom.formula,
                    f"{dom.value:.1f} {dom.unit} ({dom.who_ratio:.1f}× WHO limit)",
                    value_color="#F97316" if dom.who_ratio > 2 else "#34D399",
                )
            else:
                render_kpi_card("Dominant Pollutant", "Unavailable", "No WHO-benchmarked live pollutant exceeded or reported", "#94A3B8")
        with k3:
            fs = snapshot.forecast_summary
            if fs.available and fs.best_window_label:
                render_kpi_card(
                    "Cleanest 24h Window",
                    f"AQI ~{fs.best_window_avg_aqi:.0f}" if fs.best_window_avg_aqi is not None else "Available",
                    fs.best_window_label,
                    value_color="#34D399",
                    accent=True,
                )
            else:
                render_kpi_card("Cleanest 24h Window", "Unavailable", "Hourly forecast not reported", "#94A3B8")

    # Live Pollutants Breakdown Grid
    st.markdown("---")
    render_section_header(
        "Live Pollutant Concentrations",
        "Real-time readings directly from Open-Meteo. Unavailable pollutants are explicitly flagged and never invented.",
    )
    ordered_keys = [
        "pm2_5",
        "pm10",
        "nitrogen_dioxide",
        "carbon_monoxide",
        "ozone",
        "sulphur_dioxide",
        "dust",
        "aerosol_optical_depth",
    ]
    for row_start in range(0, len(ordered_keys), 4):
        cols = st.columns(4)
        for col, key in zip(cols, ordered_keys[row_start : row_start + 4]):
            with col:
                render_pollutant_card(snapshot.pollutants[key])

    # Interactive Charts Row
    st.markdown("---")
    render_section_header(
        "Air Quality Trends & WHO Guideline Comparison",
        "Inspect upcoming smog peaks and compare live readings against WHO 2021 air quality guidelines.",
    )
    horizon = st.radio(
        "Forecast Horizon",
        options=[24, 48],
        format_func=lambda h: f"Next {h} Hours",
        horizontal=True,
        key="dash_forecast_hours",
    )

    c_left, c_right = st.columns([1.2, 1.0], gap="medium")
    with c_left:
        fc_fig = create_hourly_forecast_chart(snapshot.hourly_df, hours=horizon)
        if fc_fig is not None:
            st.plotly_chart(fc_fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.warning("Hourly US AQI forecast is unavailable for this location.")

    with c_right:
        who_fig = create_pollutant_who_chart(snapshot.pollutants)
        if who_fig is not None:
            st.plotly_chart(who_fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No live pollutants with WHO 2021 reference thresholds were reported.")

    trend_fig = create_pollutant_trend_chart(snapshot.hourly_df, hours=horizon)
    if trend_fig is not None:
        st.plotly_chart(trend_fig, use_container_width=True, config={"displayModeBar": False})

    # Reference EPA AQI Scale Legend
    with st.expander("📘 Understand US EPA AQI Categories & Pollutant Sources"):
        legend_cols = st.columns(3)
        for idx, c_item in enumerate(US_AQI_CATEGORIES):
            rng = f"{c_item.min_val}–{c_item.max_val}" if c_item.max_val is not None else f"{c_item.min_val}+"
            with legend_cols[idx % 3]:
                st.markdown(
                    f"""
                    <div class="aa-card" style="border-left:4px solid {c_item.color};padding:0.75rem 0.9rem;">
                        <div style="font-weight:700;color:{c_item.color};font-size:0.88rem;">
                            {c_item.emoji} {html.escape(c_item.name)} ({rng})
                        </div>
                        <div style="font-size:0.78rem;color:#CBD5E1;margin-top:0.25rem;">
                            {html.escape(c_item.health_summary)}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Feature 2: AI SMART ASSISTANT (Google Gemini)
# ---------------------------------------------------------------------------
def render_ai_assistant_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)
    profile = _get_family_profile()

    render_section_header(
        "AI Smart Assistant · Powered by Google Gemini",
        f"Context-aware recommendations grounded strictly in live air quality for {snapshot.location.display_name}.",
    )

    # Active Family Profile Banner
    groups_lbl = ", ".join(profile.household_groups) if profile.household_groups else "General Adults"
    sens_lbl = ", ".join(profile.health_sensitivities) if profile.health_sensitivities else "None specified"
    st.markdown(
        f"""
        <div class="aa-card aa-card-accent" style="padding:0.85rem 1.1rem;">
            <div style="font-size:0.82rem;color:#CBD5E1;">
                <strong style="color:#34D399;">Active Personalization Profile:</strong>
                Household: <strong>{html.escape(groups_lbl)}</strong> ·
                Sensitivities: <strong>{html.escape(sens_lbl)}</strong> ·
                Home: <strong>{html.escape(profile.home_type)}</strong> ·
                Commute: <strong>{html.escape(profile.primary_commute)}</strong>
                <span style="color:#94A3B8;">(Customize in sidebar → Family & Home Profile)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Action Briefing Generator
    b1, b2 = st.columns([1.2, 2.8])
    with b1:
        gen_clicked = st.button("✨ Generate Personalized Briefing", type="primary", use_container_width=True)
    with b2:
        st.caption(
            "Analyzes live US AQI, PM2.5/PM10/NO₂/CO readings, next-24h forecast windows, and your family profile."
        )

    if gen_clicked:
        with st.spinner("Analyzing live air quality with Google Gemini..."):
            st.session_state["ai_briefing"] = generate_personalized_briefing(snapshot, profile)

    if "ai_briefing" in st.session_state:
        _render_ai_response_card(
            st.session_state["ai_briefing"],
            f"Personalized Smog & Health Briefing · {snapshot.location.name}",
        )

    st.markdown("---")
    render_section_header(
        "Ask AirAware AI Anything",
        "Ask follow-up questions about school runs, masks, exercise safety, cooking fumes, or winter smog inversions.",
    )

    # Quick Prompt Chips
    suggested_prompts = [
        "Is it safe for my kids to play outside today, and what is the best hour?",
        "What type of mask should we wear today and how do we check the seal?",
        "Should I open windows tonight or keep them closed given the live forecast?",
        "Why does winter smog peak in the morning and evening here?",
    ]
    chip_cols = st.columns(2)
    queued_prompt: Optional[str] = None
    for idx, prompt_text in enumerate(suggested_prompts):
        with chip_cols[idx % 2]:
            if st.button(f"💬 {prompt_text}", key=f"prompt_chip_{idx}", use_container_width=True):
                queued_prompt = prompt_text

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tag"):
                st.caption(msg["tag"])

    user_q = st.chat_input(f"Ask about air quality in {snapshot.location.name}...")
    active_question = queued_prompt or user_q

    if active_question:
        st.session_state["chat_messages"].append({"role": "user", "content": active_question})
        with st.chat_message("user"):
            st.markdown(active_question)

        with st.chat_message("assistant"):
            with st.spinner("Consulting AirAware AI..."):
                reply = answer_followup_question(
                    snapshot,
                    profile,
                    active_question,
                    chat_history=st.session_state["chat_messages"][:-1],
                )
            if reply.error_message:
                st.info(reply.error_message, icon="ℹ️")
            st.markdown(reply.content)
            tag = (
                f"✨ Google Gemini ({reply.model_used})"
                if reply.is_ai_generated
                else "📋 Live-Data Rule Guidance (Non-AI Fallback)"
            )
            st.caption(tag)

        st.session_state["chat_messages"].append(
            {"role": "assistant", "content": reply.content, "tag": tag}
        )


# ---------------------------------------------------------------------------
# Feature 3: SMART DAILY ROUTINE
# ---------------------------------------------------------------------------
def render_daily_routine_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)
    profile = _get_family_profile()
    fs = snapshot.forecast_summary

    render_section_header(
        "Smart Low-Emission Daily Routine",
        "Time outdoor errands around real forecasted clean-air windows and cut household emissions during winter smog.",
    )

    # Live Forecast Timing Cards
    c1, c2, c3 = st.columns(3)
    with c1:
        if fs.available and fs.best_window_label:
            render_kpi_card(
                "Best 2-Hr Outdoor Window",
                f"AQI ~{fs.best_window_avg_aqi:.0f}",
                fs.best_window_label,
                value_color="#10B981",
                accent=True,
            )
        else:
            render_kpi_card("Best 2-Hr Outdoor Window", "Unavailable", fs.note, "#94A3B8")

    with c2:
        if fs.available and fs.worst_window_label:
            render_kpi_card(
                "Peak Smog Window to Avoid",
                f"AQI ~{fs.worst_window_aqi:.0f}",
                fs.worst_window_label,
                value_color="#EF4444",
            )
        else:
            render_kpi_card("Peak Smog Window", "Unavailable", fs.note, "#94A3B8")

    with c3:
        if fs.available:
            safe_cnt = len(fs.safe_ventilation_hours)
            render_kpi_card(
                "Hours with AQI ≤ 100 (Next 24h)",
                f"{safe_cnt} / {fs.hours_analyzed} hrs",
                "Safe for natural cross-ventilation" if safe_cnt > 0 else "Keep windows sealed & filter indoors",
                value_color="#34D399" if safe_cnt > 0 else "#F97316",
            )
        else:
            render_kpi_card("Safe Ventilation Hours", "Unavailable", "No live hourly forecast", "#94A3B8")

    # Hourly Trajectory Visual
    fc_fig = create_hourly_forecast_chart(snapshot.hourly_df, hours=24)
    if fc_fig is not None:
        st.plotly_chart(fc_fig, use_container_width=True, config={"displayModeBar": False})

    # Practical Precautions & Low-Emission Activities
    st.markdown("---")
    left_col, right_col = st.columns(2, gap="large")
    aqi_val = snapshot.us_aqi

    with left_col:
        st.markdown("#### 🛡️ Practical Pollution Precautions Today")
        precautions = [
            (
                "Respiratory Fit Check",
                "Wear a snug N95/KN95/FFP2 respirator outdoors with nose-bridge sealed (cloth/surgical masks do not block PM2.5)."
                if (aqi_val is not None and aqi_val > 100)
                else "Keep certified N95/KN95 masks stocked in school bags and work backpacks for sudden winter smog spikes.",
            ),
            (
                "Post-Outdoor Hygiene",
                "Wash face, hands, and rinse nasal passages with gentle saline after commuting through congested corridors.",
            ),
            (
                "Exercise Adaptation",
                "Move cardio/HIIT indoors today to avoid 5–10× deeper PM2.5 inhalation from heavy mouth breathing."
                if (aqi_val is not None and aqi_val > 125)
                else "Schedule brisk walks or outdoor play during the cleanest forecast window away from main arterials.",
            ),
            (
                "Hydration & Symptom Watch",
                "Stay hydrated to keep airways moist; monitor children and seniors for persistent cough, wheeze, or chest tightness.",
            ),
        ]
        for title, desc in precautions:
            st.markdown(
                f'<div class="aa-card" style="padding:0.85rem 1rem;">'
                f'<strong style="color:#34D399;">✓ {html.escape(title)}</strong>'
                f'<div style="font-size:0.86rem;color:#CBD5E1;margin-top:0.25rem;">{html.escape(desc)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    with right_col:
        st.markdown("#### 🌿 Low-Emission Daily Activities")
        activities = [
            (
                "Clean-Heat & Smart Cooking",
                "Use pressure cookers, lids, or induction/electric kettles; avoid deep-frying or open charcoal/wood fires during inversion hours.",
            ),
            (
                "Trip Chaining & Zero Idling",
                "Combine grocery, school, and pharmacy errands into one warm-engine trip; turn off engines at railway crossings or pickups.",
            ),
            (
                "Peak-Smog Indoor Routines",
                "Shift evening outdoor hangouts to indoor yoga, stretching, reading, or community indoor spaces when dusk smog settles.",
            ),
            (
                "Zero Open Burning",
                "Compost dry winter leaves and garden trimmings instead of burning—open leaf fires emit dense local PM2.5 plumes.",
            ),
        ]
        for title, desc in activities:
            st.markdown(
                f'<div class="aa-card" style="padding:0.85rem 1rem;">'
                f'<strong style="color:#38BDF8;">⚡ {html.escape(title)}</strong>'
                f'<div style="font-size:0.86rem;color:#CBD5E1;margin-top:0.25rem;">{html.escape(desc)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    # AI-Generated Hour-by-Hour Schedule
    st.markdown("---")
    if st.button("🗓️ Generate AI Hour-by-Hour Family Schedule", type="primary"):
        with st.spinner("Building your forecast-aligned schedule with Gemini..."):
            st.session_state["ai_routine"] = generate_smart_routine_plan(snapshot, profile)

    if "ai_routine" in st.session_state:
        _render_ai_response_card(
            st.session_state["ai_routine"],
            f"Personalized Smart Daily Schedule · {snapshot.location.name}",
        )


# ---------------------------------------------------------------------------
# Feature 4: INDOOR AIR QUALITY HACKS
# ---------------------------------------------------------------------------
def render_indoor_hacks_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)
    profile = _get_family_profile()
    cat = snapshot.us_aqi_category
    fs = snapshot.forecast_summary

    render_section_header(
        "Indoor Air Quality Hacks & Smart Ventilation",
        "Outdoor-aware ventilation rules and affordable, evidence-backed strategies to keep indoor air breathable.",
    )

    # Live Outdoor-Driven Ventilation Advisor
    if snapshot.us_aqi is None or cat is None:
        vent_status = "VERIFY OUTDOOR CONDITIONS"
        vent_color = "#94A3B8"
        vent_detail = "Live US AQI is unavailable from the API. Check local visibility and municipal monitors before opening windows."
    elif snapshot.us_aqi <= 50:
        vent_status = "SAFE TO OPEN WINDOWS"
        vent_color = "#10B981"
        vent_detail = f"Live US AQI is {snapshot.us_aqi:.0f} (Good). Open opposite windows for 15–30 minutes to flush indoor CO₂ and cooking VOCs."
    elif snapshot.us_aqi <= 100:
        vent_status = "SELECTIVE VENTILATION"
        vent_color = "#FACC15"
        vent_detail = f"Live US AQI is {snapshot.us_aqi:.0f} (Moderate). Briefly ventilate away from road-facing windows during the cleanest afternoon hours."
    elif snapshot.us_aqi <= 150:
        vent_status = "LIMIT OPENING · FILTER INDOORS"
        vent_color = "#F97316"
        vent_detail = f"Live US AQI is {snapshot.us_aqi:.0f} (USG). Keep windows closed—especially for kids/seniors. Use only brief exhaust while cooking."
    else:
        vent_status = "KEEP WINDOWS SEALED"
        vent_color = "#EF4444"
        vent_detail = f"Live US AQI is {snapshot.us_aqi:.0f} ({cat.name}). Do NOT cross-ventilate with smoky outdoor air. Seal drafts and run indoor filtration."

    safe_window_line = (
        f"Next 24h hours with AQI ≤ 100: {', '.join(fs.safe_ventilation_hours[:5])}"
        + ("…" if len(fs.safe_ventilation_hours) > 5 else "")
        if fs.available and fs.safe_ventilation_hours
        else ("No hours ≤ 100 AQI forecasted in next 24h — maintain closed-window filtration." if fs.available else "Hourly ventilation forecast unavailable.")
    )

    st.markdown(
        f"""
        <div class="aa-card" style="border-left:5px solid {vent_color};background:rgba(15,27,46,0.9);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
                <span class="aa-kpi-label" style="margin:0;">Live Ventilation Decision · {html.escape(snapshot.location.name)}</span>
                <span class="aa-pill" style="color:{vent_color};border:1px solid {vent_color};background:rgba(8,16,30,0.65);">
                    🪟 {html.escape(vent_status)}
                </span>
            </div>
            <p style="margin:0.65rem 0 0.45rem 0;color:#F1F5F9;font-size:0.95rem;">{html.escape(vent_detail)}</p>
            <div style="font-size:0.82rem;color:#94A3B8;">⏱️ {html.escape(safe_window_line)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Affordable Hacks Grid
    st.markdown("#### 💡 Affordable, Proven Clean-Air Hacks")
    hacks = [
        (
            "🌀 DIY Corsi-Rosenthal Box Filter",
            "Budget: ~$35–$70 (fraction of commercial purifiers)",
            "Tape 1–4 MERV-13 pleated HVAC filters to a standard 20-inch box fan with a cardboard shroud. Peer-reviewed studies show Clean Air Delivery Rates (CADR) matching or beating $300+ HEPA units for PM2.5.",
        ),
        (
            "🛏️ Create One Dedicated Clean-Air Room",
            "Budget: Free – Low",
            "Can't filter the whole home? Seal one bedroom (damp towel or foam weather-stripping at door gaps) and run your single purifier/DIY fan there so your family gets 8 hours of clean lung recovery nightly.",
        ),
        (
            "🧽 Wet Mopping Over Dry Sweeping",
            "Budget: Free",
            "Brooms and dry dusters kick settled PM2.5 and lead-rich street dust straight back into breathing zones. Use a damp microfiber mop and wipe window sills daily during smog peaks.",
        ),
        (
            "🍳 Zero-Smoke Kitchen Habits",
            "Budget: Free",
            "Gas stoves and high-heat frying spike indoor NO₂ and PM2.5 past outdoor smog levels. Always run the range hood, cook on back burners, cover pans with lids, and skip incense/scented candles.",
        ),
        (
            "🚪 Entryway Pollution Trap",
            "Budget: Free",
            "Leave outdoor shoes and smog-dusted jackets at the door. Use a washable doormat and change outer clothes after heavy traffic commutes.",
        ),
        (
            "💧 Optimal Humidity (40%–50%)",
            "Budget: Low",
            "Very dry winter indoor air dries nasal membranes and keeps fine dust suspended longer. Avoid over-humidifying (>60% encourages mold); a simple bowl of water near safe heat or cool-mist humidifier helps.",
        ),
    ]

    for i in range(0, len(hacks), 3):
        cols = st.columns(3)
        for col, (title, cost, desc) in zip(cols, hacks[i : i + 3]):
            with col:
                st.markdown(
                    f"""
                    <div class="aa-card" style="height:100%;">
                        <div style="font-weight:700;color:#F8FAFC;font-size:0.96rem;">{html.escape(title)}</div>
                        <div style="font-size:0.75rem;color:#34D399;font-weight:600;margin:0.2rem 0 0.5rem 0;">{html.escape(cost)}</div>
                        <div style="font-size:0.84rem;color:#CBD5E1;line-height:1.45;">{html.escape(desc)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # Interactive Household Readiness Checklist
    st.markdown("---")
    chk_col, ai_col = st.columns([1.0, 1.35], gap="large")
    with chk_col:
        st.markdown("#### ✅ Tonight's Clean-Air Home Checklist")
        checklist_items = [
            "Closed traffic-facing windows & sealed visible door gaps",
            "Switched from dry sweeping to damp mopping",
            "Ran kitchen exhaust / kept lids on during cooking",
            "Avoided burning incense, candles, or mosquito coils indoors",
            "Placed filtration (HEPA or DIY MERV-13 fan) in the sleeping room",
            "Removed outdoor shoes & jackets at the entryway",
        ]
        completed = 0
        for idx, item in enumerate(checklist_items):
            if st.checkbox(item, key=f"indoor_chk_{idx}"):
                completed += 1
        pct = int((completed / len(checklist_items)) * 100)
        st.progress(pct / 100.0, text=f"Home Smog Readiness: {completed}/{len(checklist_items)} ({pct}%)")

    with ai_col:
        st.markdown("#### 🤖 Custom Indoor Plan for Your Budget")
        budget_tier = st.selectbox(
            "Select household budget tier",
            options=[
                "Zero-cost habits & ventilation only",
                "Low budget ($25–$80: DIY MERV-13 filter + draft sealing)",
                "Moderate budget ($100–$300: True HEPA bedroom purifier)",
            ],
            key="indoor_budget_tier",
        )
        if st.button("🏠 Generate AI Indoor Clean-Air Plan", type="primary"):
            with st.spinner("Creating your personalized indoor air plan..."):
                st.session_state["ai_indoor"] = generate_indoor_air_plan(snapshot, profile, budget_tier)
                st.session_state["ai_indoor_tier"] = budget_tier

        if "ai_indoor" in st.session_state:
            rendered_tier = st.session_state.get("ai_indoor_tier", budget_tier)
            _render_ai_response_card(
                st.session_state["ai_indoor"],
                f"Indoor Air Protocol · {rendered_tier}",
            )


# ---------------------------------------------------------------------------
# Feature 5: ECO-FRIENDLY TRAVEL
# ---------------------------------------------------------------------------
def render_eco_travel_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)
    render_section_header(
        "Eco-Friendly & AQI-Safe Travel Planner",
        "Compare walking, cycling, public transit, and carpooling using transparent DEFRA emission factors—adjusted for live AQI safety.",
    )

    in1, in2, in3 = st.columns([1.4, 1.0, 1.0])
    with in1:
        current_mode = st.selectbox(
            "Your current primary commute mode",
            options=["petrol_car", "diesel_car", "motorcycle", "rideshare"],
            format_func=lambda k: f"{TRANSPORT_MODES[k].icon} {TRANSPORT_MODES[k].label}",
            key="travel_current_mode",
        )
    with in2:
        one_way_km = st.number_input(
            "One-way distance (km)",
            min_value=0.5,
            max_value=80.0,
            value=8.0,
            step=0.5,
            key="travel_one_way_km",
        )
    with in3:
        days_per_week = st.slider(
            "Commute days / week",
            min_value=1,
            max_value=7,
            value=5,
            key="travel_days_week",
        )

    evaluations = evaluate_eco_travel_options(
        current_mode_key=current_mode,
        one_way_km=float(one_way_km),
        days_per_week=int(days_per_week),
        live_us_aqi=snapshot.us_aqi,
    )

    # Smog Safety Callout when live AQI is elevated
    if snapshot.us_aqi is not None and snapshot.us_aqi > 150:
        st.warning(
            f"**Winter Smog Travel Advisory ({snapshot.location.name} · Live US AQI {snapshot.us_aqi:.0f}):** "
            "While walking and cycling produce zero tailpipe emissions, strenuous outdoor breathing increases inhaled PM2.5 during severe smog. "
            "Today, **Metro/Rail, Public Bus, or 3-Person Carpooling** offer the smartest balance of cutting urban emissions AND protecting your lungs.",
            icon="⚠️",
        )

    # Ranked Alternative Cards
    st.markdown("#### 🧭 Recommended Low-Emission Alternatives (Ranked for Live AQI & Distance)")
    for ev in evaluations:
        st.markdown(
            f"""
            <div class="aa-card" style="border-left:4px solid {ev.aqi_safety_color};">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
                    <div style="font-size:1.05rem;font-weight:700;color:#F8FAFC;">
                        {ev.mode.icon} {html.escape(ev.mode.label)}
                    </div>
                    <span class="aa-pill" style="color:{ev.aqi_safety_color};border:1px solid {ev.aqi_safety_color};background:rgba(8,16,30,0.65);">
                        {html.escape(ev.aqi_safety_badge)}
                    </span>
                </div>
                <p style="margin:0.45rem 0 0.6rem 0;color:#CBD5E1;font-size:0.88rem;">
                    {html.escape(ev.aqi_safety_note)} {html.escape(ev.mode.notes)}
                </p>
                <div style="display:flex;flex-wrap:wrap;gap:1.1rem;font-size:0.82rem;color:#94A3B8;font-family:'JetBrains Mono',monospace;">
                    <span>💚 <strong style="color:#34D399;">-{ev.annual_co2_saved_kg:,.1f} kg CO₂e/yr</strong> (-{ev.weekly_co2_saved_kg:.2f} kg/wk)</span>
                    <span>🌫️ <strong style="color:#38BDF8;">-{ev.annual_nox_saved_g:,.0f} g NOx/yr</strong></span>
                    <span>🫁 <strong style="color:#FACC15;">-{ev.annual_pm25_saved_g:,.1f} g PM2.5/yr</strong></span>
                </div>
                <div style="margin-top:0.45rem;font-size:0.75rem;color:#64748B;">
                    Formula: {html.escape(ev.formula)} · Source: {html.escape(ev.mode.source)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.plotly_chart(
        create_travel_comparison_chart(current_mode, float(one_way_km), int(days_per_week), evaluations),
        use_container_width=True,
        config={"displayModeBar": False},
    )


# ---------------------------------------------------------------------------
# Feature 6: POLLUTION IMPACT TRACKER
# ---------------------------------------------------------------------------
def render_impact_tracker_page(snapshot: AirQualitySnapshot) -> None:
    render_timestamp_strip(snapshot)
    render_section_header(
        "Transparent Pollution Impact Tracker",
        "See exactly how everyday choices reduce urban smog precursors and carbon emissions—every number backed by an explicit formula and published factor.",
    )

    st.markdown(
        """
        <div class="aa-card aa-card-accent" style="padding:0.9rem 1.15rem;">
            <strong style="color:#34D399;">Why Individual Choices Matter in Winter Smog:</strong>
            <span style="color:#CBD5E1;font-size:0.88rem;">
                During winter temperature inversions, pollutants stay trapped in a shallow layer right where families breathe.
                Local tailpipe NOx, idling exhaust, inefficient electricity generation, and open leaf burning directly amplify
                neighborhood PM2.5 peaks. Adjust your habits below to calculate transparent, verifiable reductions.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Interactive Controls
    col_a, col_b = st.columns(2, gap="large")
    with col_a:
        st.markdown("##### 🚗 Commute & Driving Habits")
        from_mode = st.selectbox(
            "Replacing transport mode",
            options=["petrol_car", "diesel_car", "motorcycle", "rideshare"],
            format_func=lambda k: f"{TRANSPORT_MODES[k].icon} {TRANSPORT_MODES[k].label}",
            key="imp_from_mode",
        )
        to_mode = st.selectbox(
            "Switching to eco-friendly mode",
            options=["metro_rail", "city_bus", "carpool_3", "cycling", "walking"],
            format_func=lambda k: f"{TRANSPORT_MODES[k].icon} {TRANSPORT_MODES[k].label}",
            key="imp_to_mode",
        )
        commute_km_wk = st.slider(
            "Weekly distance shifted (km/week)",
            min_value=0,
            max_value=250,
            value=50,
            step=5,
            key="imp_commute_km",
        )
        idling_mins_wk = st.slider(
            "Vehicle engine idling avoided (minutes/week)",
            min_value=0,
            max_value=180,
            value=30,
            step=5,
            help="Turning off your engine at long signals, school pickups, or morning warm-ups.",
            key="imp_idling_mins",
        )

    with col_b:
        st.markdown("##### ⚡ Home Energy & Zero Open Burning")
        grid_preset = st.selectbox(
            "Regional electricity grid carbon intensity",
            options=list(GRID_INTENSITY_PRESETS.keys()),
            index=0,
            key="imp_grid_preset",
        )
        kwh_saved_wk = st.slider(
            "Household electricity conserved (kWh/week)",
            min_value=0.0,
            max_value=80.0,
            value=10.0,
            step=1.0,
            help="e.g., sealing drafts to reduce space-heater load, LED lighting, cold-water laundry.",
            key="imp_kwh_wk",
        )
        biomass_kg_mo = st.slider(
            "Dry leaves / yard waste composted instead of burned (kg/month)",
            min_value=0,
            max_value=50,
            value=5,
            step=1,
            help="Uses US EPA AP-42 open leaf-burning emission factor (~19 g PM2.5 per kg dry matter).",
            key="imp_biomass_kg",
        )

    report = compute_household_impact(
        commute_from_key=from_mode,
        commute_to_key=to_mode,
        commute_km_per_week=float(commute_km_wk),
        idling_mins_avoided_per_week=float(idling_mins_wk),
        electricity_kwh_saved_per_week=float(kwh_saved_wk),
        grid_preset_label=grid_preset,
        biomass_kg_composted_per_month=float(biomass_kg_mo),
    )

    st.markdown("---")

    # KPI Summary Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_kpi_card(
            "Estimated Annual CO₂e Saved",
            f"{report.total_annual_co2_kg:,.1f} kg",
            f"≈ {report.total_monthly_co2_kg:,.1f} kg/month ({report.total_weekly_co2_kg:.2f} kg/wk)",
            value_color="#10B981",
            accent=True,
        )
    with m2:
        render_kpi_card(
            "Direct PM2.5 Avoided / Yr",
            f"{report.total_annual_pm25_g:,.1f} g",
            "Tailpipe + avoided open biomass burning",
            value_color="#34D399",
        )
    with m3:
        render_kpi_card(
            "Tailpipe NOx Avoided / Yr",
            f"{report.total_annual_nox_g:,.1f} g",
            "Direct transport smog precursor reduction",
            value_color="#38BDF8",
        )
    with m4:
        render_kpi_card(
            f"If 1,000 Families in {snapshot.location.name}",
            f"{report.community_1000_households_co2_tonnes:,.1f} t CO₂e",
            "Linear 1,000× community annual scale-up",
            value_color="#FACC15",
        )

    chart = create_impact_breakdown_chart(report)
    if chart is not None:
        st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Adjust one or more sliders above to compute transparent environmental impact estimates.")

    # Full Audit Trail / Calculation Transparency Table
    with st.expander("🔍 Transparent Calculation Formulas & Cited Emission Factors", expanded=True):
        if not report.items:
            st.caption("No active actions selected yet.")
        else:
            for item in report.items:
                st.markdown(
                    f"""
                    <div class="aa-card" style="padding:0.8rem 1rem;">
                        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.4rem;">
                            <strong style="color:#F8FAFC;">{html.escape(item.action_name)}</strong>
                            <span style="font-family:'JetBrains Mono',monospace;color:#34D399;font-weight:700;">
                                -{item.annual_co2_kg:,.1f} kg CO₂e/yr
                            </span>
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:0.78rem;color:#CBD5E1;margin-top:0.3rem;">
                            Formula: {html.escape(item.formula_text)}
                        </div>
                        <div style="font-size:0.75rem;color:#94A3B8;margin-top:0.2rem;">
                            Source: {html.escape(item.source_citation)}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.caption(
            "Methodology Note: Values are transparent engineering estimates derived strictly from your inputs and published "
            "conversion factors (UK DEFRA/DESNZ 2024, US EPA MOVES/AP-42, IEA). Electricity NOx/PM2.5 are deliberately shown "
            "as 0 g because power-plant stack emissions vary significantly by local generation mix."
        )


# ---------------------------------------------------------------------------
# Main Application Flow
# ---------------------------------------------------------------------------
def main() -> None:
    _init_session_state()
    active_page = render_sidebar()

    snapshot: Optional[AirQualitySnapshot] = st.session_state.get("snapshot")
    api_error: Optional[AirQualityServiceError] = st.session_state.get("api_error")

    # Build Hero Banner Live Chip
    city_label = snapshot.location.display_name if snapshot else None
    aqi_badge_html = ""
    if snapshot:
        if snapshot.us_aqi is not None and snapshot.us_aqi_category is not None:
            c = snapshot.us_aqi_category
            aqi_badge_html = (
                f'<span class="aa-pill" style="background:{c.bg_tint};color:{c.color};border:1px solid {c.color};">'
                f"{c.emoji} Live US AQI: {snapshot.us_aqi:.0f} · {html.escape(c.name)}</span>"
            )
        else:
            aqi_badge_html = '<span class="aa-pill aa-pill-unavail">○ Live US AQI Unavailable</span>'

    render_hero_banner(city_label=city_label, aqi_badge_html=aqi_badge_html)

    # Graceful API Error Banner
    if api_error is not None:
        st.error(f"**Live Air Quality Fetch Issue:** {api_error.message}", icon="⚠️")
        if snapshot is not None:
            st.caption(
                f"Showing last successfully loaded live snapshot for **{snapshot.location.display_name}** "
                f"(fetched {snapshot.fetched_at_utc}). Use the sidebar to search another city or retry."
            )

    if snapshot is None:
        st.markdown(
            """
            <div class="aa-card" style="text-align:center;padding:2rem;">
                <h3 style="color:#F8FAFC;margin-bottom:0.5rem;">Enter a City to Start Monitoring Live Air Quality</h3>
                <p style="color:#94A3B8;max-width:560px;margin:0 auto;">
                    Use the <strong>Location Detection</strong> search box in the left sidebar to look up any city worldwide
                    via the Open-Meteo Geocoding & Air Quality APIs. No API key is required for live AQI data.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Dispatch active module
    if active_page == "Air Quality Dashboard":
        render_dashboard_page(snapshot)
    elif active_page == "AI Smart Assistant":
        render_ai_assistant_page(snapshot)
    elif active_page == "Smart Daily Routine":
        render_daily_routine_page(snapshot)
    elif active_page == "Indoor Air Hacks":
        render_indoor_hacks_page(snapshot)
    elif active_page == "Eco-Friendly Travel":
        render_eco_travel_page(snapshot)
    elif active_page == "Pollution Impact Tracker":
        render_impact_tracker_page(snapshot)


if __name__ == "__main__":
    main()
