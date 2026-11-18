"""Custom CSS styling and reusable HTML UI components for AirAware AI."""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from src.air_quality import PollutantReading
from src.config import APP_NAME, CHALLENGE_BADGE

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Deep dark-navy backdrop with subtle emerald atmospheric glow */
.stApp {
    background:
        radial-gradient(circle at 12% 8%, rgba(16, 185, 129, 0.13) 0%, transparent 36%),
        radial-gradient(circle at 88% 12%, rgba(56, 189, 248, 0.08) 0%, transparent 32%),
        linear-gradient(180deg, #070E1B 0%, #0A1527 50%, #08101E 100%);
    color: #F1F5F9;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #091324 0%, #0D1A30 100%);
    border-right: 1px solid rgba(52, 211, 153, 0.14);
}

[data-testid="stSidebar"] .stRadio > div {
    gap: 0.32rem;
}

/* Hero Banner */
.aa-hero {
    background: linear-gradient(135deg, rgba(15, 29, 52, 0.92) 0%, rgba(11, 38, 44, 0.88) 100%);
    border: 1px solid rgba(52, 211, 153, 0.24);
    border-radius: 20px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.35rem;
    box-shadow: 0 18px 45px rgba(2, 8, 20, 0.45);
    position: relative;
    overflow: hidden;
}

.aa-hero::after {
    content: "";
    position: absolute;
    top: -45px;
    right: -45px;
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(16, 185, 129, 0.22) 0%, transparent 70%);
    pointer-events: none;
}

.aa-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.3rem 0.78rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: rgba(16, 185, 129, 0.14);
    color: #34D399;
    border: 1px solid rgba(52, 211, 153, 0.32);
    margin-bottom: 0.75rem;
}

.aa-hero-title {
    font-size: 2.05rem;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: #F8FAFC;
    margin: 0 0 0.45rem 0;
    line-height: 1.15;
}

.aa-hero-title span {
    background: linear-gradient(90deg, #34D399 0%, #10B981 55%, #38BDF8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.aa-hero-sub {
    color: #CBD5E1;
    font-size: 0.98rem;
    line-height: 1.55;
    max-width: 760px;
    margin: 0;
}

/* Glass Cards */
.aa-card {
    background: rgba(15, 27, 46, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 16px;
    padding: 1.15rem 1.25rem;
    margin-bottom: 0.95rem;
    box-shadow: 0 8px 24px rgba(2, 8, 20, 0.28);
    transition: border-color 0.2s ease, transform 0.2s ease;
}

.aa-card:hover {
    border-color: rgba(52, 211, 153, 0.34);
}

.aa-card-accent {
    background: linear-gradient(145deg, rgba(16, 185, 129, 0.11) 0%, rgba(15, 27, 46, 0.84) 100%);
    border: 1px solid rgba(52, 211, 153, 0.28);
}

.aa-kpi-label {
    font-size: 0.76rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94A3B8;
    margin-bottom: 0.35rem;
}

.aa-kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.65rem;
    font-weight: 700;
    color: #F8FAFC;
    line-height: 1.15;
}

.aa-kpi-sub {
    font-size: 0.8rem;
    color: #94A3B8;
    margin-top: 0.35rem;
    line-height: 1.35;
}

/* Status Dots & Pills */
.aa-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.62rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
}

.aa-pill-live {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(52, 211, 153, 0.35);
}

.aa-pill-unavail {
    background: rgba(100, 116, 139, 0.18);
    color: #94A3B8;
    border: 1px solid rgba(148, 163, 184, 0.25);
}

/* Pollutant Card */
.aa-pollutant-card {
    background: rgba(13, 24, 42, 0.84);
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 14px;
    padding: 0.95rem 1.05rem;
    height: 100%;
    margin-bottom: 0.8rem;
}

.aa-pollutant-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
}

.aa-pollutant-formula {
    font-size: 0.95rem;
    font-weight: 700;
    color: #F8FAFC;
}

.aa-pollutant-name {
    font-size: 0.74rem;
    color: #94A3B8;
    margin-bottom: 0.55rem;
}

.aa-pollutant-reading {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.45rem;
    font-weight: 700;
    color: #F8FAFC;
}

.aa-pollutant-unit {
    font-size: 0.78rem;
    font-weight: 500;
    color: #94A3B8;
    margin-left: 0.2rem;
}

/* Section Headers */
.aa-section-title {
    font-size: 1.32rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 0.25rem 0 0.2rem 0;
    letter-spacing: -0.01em;
}

.aa-section-sub {
    font-size: 0.9rem;
    color: #94A3B8;
    margin: 0 0 1rem 0;
}

/* Timestamp bar */
.aa-timestamp-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1.25rem;
    align-items: center;
    background: rgba(15, 27, 46, 0.72);
    border: 1px solid rgba(52, 211, 153, 0.18);
    border-radius: 12px;
    padding: 0.65rem 1rem;
    font-size: 0.82rem;
    color: #CBD5E1;
    margin-bottom: 1.1rem;
}

.aa-timestamp-bar strong {
    color: #F8FAFC;
}

/* Sidebar Brand Card */
.aa-brand-box {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.16) 0%, rgba(15, 27, 46, 0.9) 100%);
    border: 1px solid rgba(52, 211, 153, 0.28);
    border-radius: 14px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.9rem;
}

.aa-brand-title {
    font-size: 1.22rem;
    font-weight: 800;
    color: #F8FAFC;
    letter-spacing: -0.02em;
}

.aa-brand-sub {
    font-size: 0.75rem;
    color: #34D399;
    font-weight: 600;
    margin-top: 0.15rem;
}

/* Primary button accent */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #059669 0%, #10B981 100%);
    color: #041310;
    font-weight: 700;
    border: none;
    border-radius: 10px;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(90deg, #10B981 0%, #34D399 100%);
    color: #03110E;
}

/* Mobile responsiveness refinements (preserves desktop layout) */
@media (max-width: 640px) {
    .aa-hero {
        padding: 1.2rem 1.15rem;
        border-radius: 16px;
    }
    .aa-hero-title {
        font-size: 1.45rem;
    }
    .aa-hero-sub {
        font-size: 0.88rem;
    }
    .aa-kpi-value {
        font-size: 1.35rem;
    }
    .aa-timestamp-bar {
        padding: 0.55rem 0.75rem;
        font-size: 0.76rem;
        gap: 0.45rem 0.8rem;
    }
}

/* Hide default Streamlit hamburger footer clutter subtly */
footer {visibility: hidden;}
</style>
"""


def inject_custom_css() -> None:
    """Inject the AirAware AI dark navy & emerald stylesheet."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_hero_banner(city_label: Optional[str] = None, aqi_badge_html: str = "") -> None:
    """Render the attractive landing hero section."""
    city_chip = ""
    if city_label:
        safe_city = html.escape(city_label)
        city_chip = (
            f'<div style="margin-top:1rem;display:flex;flex-wrap:wrap;gap:0.65rem;align-items:center;">'
            f'<span class="aa-pill aa-pill-live">📍 Active City: {safe_city}</span>'
            f"{aqi_badge_html}"
            f"</div>"
        )

    st.markdown(
        f"""
        <div class="aa-hero">
            <div class="aa-badge">🌿 {html.escape(CHALLENGE_BADGE)}</div>
            <h1 class="aa-hero-title">{html.escape(APP_NAME)} · <span>Breathe Smarter Through Winter Smog</span></h1>
            <p class="aa-hero-sub">
                Real-time urban air quality monitoring paired with personalized Google Gemini guidance,
                low-emission daily routines, affordable indoor clean-air hacks, AQI-safe eco-travel, and
                transparent environmental impact calculations.
            </p>
            {city_chip}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="aa-section-title">{html.escape(title)}</div>'
        f'<div class="aa-section-sub">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def render_kpi_card(
    label: str,
    value: str,
    subtitle: str = "",
    value_color: str = "#F8FAFC",
    accent: bool = False,
) -> None:
    cls = "aa-card aa-card-accent" if accent else "aa-card"
    st.markdown(
        f"""
        <div class="{cls}">
            <div class="aa-kpi-label">{html.escape(label)}</div>
            <div class="aa-kpi-value" style="color:{value_color};">{html.escape(value)}</div>
            <div class="aa-kpi-sub">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pollutant_card(reading: PollutantReading) -> None:
    """Render a single pollutant card clearly distinguishing live API data from unavailable fields."""
    if reading.available and reading.value is not None:
        status_pill = '<span class="aa-pill aa-pill-live">● LIVE</span>'
        val_html = (
            f'<span class="aa-pollutant-reading">{reading.value:.1f}</span>'
            f'<span class="aa-pollutant-unit">{html.escape(reading.unit)}</span>'
        )
        if reading.who_ratio is not None:
            ratio = reading.who_ratio
            if ratio <= 1.0:
                r_color = "#10B981"
                r_label = f"Within WHO limit ({ratio:.2f}×)"
            elif ratio <= 2.0:
                r_color = "#FACC15"
                r_label = f"{ratio:.1f}× WHO guideline"
            elif ratio <= 4.0:
                r_color = "#F97316"
                r_label = f"{ratio:.1f}× WHO guideline"
            else:
                r_color = "#EF4444"
                r_label = f"{ratio:.1f}× WHO guideline (High)"
            guideline_html = (
                f'<div style="margin-top:0.45rem;font-size:0.78rem;color:{r_color};font-weight:600;">'
                f"{html.escape(r_label)}</div>"
            )
        else:
            guideline_html = (
                f'<div style="margin-top:0.45rem;font-size:0.76rem;color:#94A3B8;">'
                f"{html.escape(reading.who_basis)}</div>"
            )
    else:
        status_pill = '<span class="aa-pill aa-pill-unavail">○ UNAVAILABLE</span>'
        val_html = '<span class="aa-pollutant-reading" style="color:#64748B;font-size:1.15rem;">Not Reported</span>'
        guideline_html = (
            '<div style="margin-top:0.45rem;font-size:0.76rem;color:#64748B;">'
            "No live sensor/model reading returned by Open-Meteo for this location."
            "</div>"
        )

    st.markdown(
        f"""
        <div class="aa-pollutant-card">
            <div class="aa-pollutant-header">
                <span class="aa-pollutant-formula">{html.escape(reading.formula)}</span>
                {status_pill}
            </div>
            <div class="aa-pollutant-name">{html.escape(reading.name)}</div>
            <div>{val_html}</div>
            {guideline_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
