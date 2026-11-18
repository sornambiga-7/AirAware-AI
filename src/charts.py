"""Interactive Plotly visualizations styled for AirAware AI's dark navy & emerald theme."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go

from src.air_quality import PollutantReading
from src.config import AQICategory
from src.impact_calculator import (
    TRANSPORT_MODES,
    HouseholdImpactReport,
    TravelOptionEvaluation,
)

BG_TRANSPARENT = "rgba(0,0,0,0)"
PLOT_BG = "rgba(15, 27, 46, 0.55)"
GRID_COLOR = "rgba(148, 163, 184, 0.14)"
TEXT_PRIMARY = "#F1F5F9"
TEXT_MUTED = "#94A3B8"
EMERALD = "#10B981"
MINT = "#34D399"


def _base_layout(title: str = "", height: int = 340) -> dict:
    return dict(
        title=dict(
            text=title,
            font=dict(size=15, color=TEXT_PRIMARY, family="Plus Jakarta Sans, sans-serif"),
            x=0.01,
            xanchor="left",
        )
        if title
        else None,
        height=height,
        paper_bgcolor=BG_TRANSPARENT,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_PRIMARY, family="Plus Jakarta Sans, sans-serif", size=12),
        margin=dict(l=18, r=18, t=44 if title else 22, b=24),
        hoverlabel=dict(
            bgcolor="#0B1526",
            bordercolor="rgba(52, 211, 153, 0.45)",
            font=dict(color=TEXT_PRIMARY, size=12),
        ),
    )


def create_aqi_gauge(us_aqi: Optional[float], category: Optional[AQICategory]) -> go.Figure:
    """Render an EPA color-coded US AQI radial gauge without fabricating unavailable values."""
    if us_aqi is None or category is None:
        fig = go.Figure()
        fig.add_annotation(
            text="Live US AQI<br><b>Unavailable</b>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color=TEXT_MUTED),
        )
        fig.update_layout(
            height=270,
            paper_bgcolor=BG_TRANSPARENT,
            plot_bgcolor=BG_TRANSPARENT,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=20, b=10),
        )
        return fig

    capped_max = max(350, int(us_aqi) + 50) if us_aqi > 300 else 350

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(us_aqi),
            number=dict(
                font=dict(size=48, color=category.color, family="JetBrains Mono, monospace"),
                suffix="",
            ),
            title=dict(
                text=f"<span style='font-size:13px;color:{TEXT_MUTED}'>US EPA AQI</span><br>"
                f"<span style='font-size:16px;color:{category.color};font-weight:700'>{category.name}</span>",
            ),
            gauge=dict(
                axis=dict(
                    range=[0, capped_max],
                    tickwidth=1,
                    tickcolor=TEXT_MUTED,
                    tickfont=dict(color=TEXT_MUTED, size=10),
                    tickvals=[0, 50, 100, 150, 200, 300],
                ),
                bar=dict(color=category.color, thickness=0.28),
                bgcolor="rgba(15, 27, 46, 0.85)",
                borderwidth=1,
                bordercolor="rgba(148, 163, 184, 0.2)",
                steps=[
                    dict(range=[0, 50], color="rgba(16, 185, 129, 0.22)"),
                    dict(range=[50, 100], color="rgba(250, 204, 21, 0.20)"),
                    dict(range=[100, 150], color="rgba(249, 115, 22, 0.20)"),
                    dict(range=[150, 200], color="rgba(239, 68, 68, 0.22)"),
                    dict(range=[200, 300], color="rgba(168, 85, 247, 0.22)"),
                    dict(range=[300, capped_max], color="rgba(225, 29, 72, 0.25)"),
                ],
                threshold=dict(
                    line=dict(color="#FFFFFF", width=3),
                    thickness=0.82,
                    value=round(us_aqi),
                ),
            ),
        )
    )
    fig.update_layout(
        height=275,
        paper_bgcolor=BG_TRANSPARENT,
        margin=dict(l=22, r=22, t=42, b=10),
        font=dict(color=TEXT_PRIMARY, family="Plus Jakarta Sans, sans-serif"),
    )
    return fig


def create_hourly_forecast_chart(hourly_df: pd.DataFrame, hours: int = 24) -> Optional[go.Figure]:
    """Plot live hourly US AQI forecast with EPA severity thresholds."""
    if hourly_df.empty or "us_aqi" not in hourly_df.columns:
        return None
    df = hourly_df.head(hours).dropna(subset=["us_aqi"]).copy()
    if df.empty:
        return None

    # Build informative hover text only using non-null live metrics
    hover_texts: List[str] = []
    for _, row in df.iterrows():
        ts = row["time"].strftime("%b %d · %I:%M %p")
        parts = [f"<b>{ts}</b>", f"US AQI: <b>{row['us_aqi']:.0f}</b>"]
        if pd.notna(row.get("pm2_5")):
            parts.append(f"PM2.5: {row['pm2_5']:.1f} μg/m³")
        if pd.notna(row.get("pm10")):
            parts.append(f"PM10: {row['pm10']:.1f} μg/m³")
        hover_texts.append("<br>".join(parts))

    marker_colors = []
    for v in df["us_aqi"]:
        if v <= 50:
            marker_colors.append("#10B981")
        elif v <= 100:
            marker_colors.append("#FACC15")
        elif v <= 150:
            marker_colors.append("#F97316")
        elif v <= 200:
            marker_colors.append("#EF4444")
        elif v <= 300:
            marker_colors.append("#A855F7")
        else:
            marker_colors.append("#E11D48")

    fig = go.Figure()

    # Subtle EPA zone reference bands
    max_y = max(160.0, float(df["us_aqi"].max()) * 1.18)
    zones = [
        (0, 50, "rgba(16, 185, 129, 0.06)"),
        (50, 100, "rgba(250, 204, 21, 0.05)"),
        (100, 150, "rgba(249, 115, 22, 0.05)"),
        (150, 200, "rgba(239, 68, 68, 0.06)"),
        (200, max_y, "rgba(168, 85, 247, 0.06)"),
    ]
    for y0, y1, fill in zones:
        if y0 < max_y:
            fig.add_hrect(y0=y0, y1=min(y1, max_y), fillcolor=fill, line_width=0)

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["us_aqi"],
            mode="lines+markers",
            name="Hourly US AQI",
            line=dict(color=MINT, width=2.8, shape="spline"),
            marker=dict(size=7, color=marker_colors, line=dict(width=1.2, color="#08101E")),
            fill="tozeroy",
            fillcolor="rgba(16, 185, 129, 0.12)",
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
        )
    )

    for level, lbl, clr in [
        (50, "Good (50)", "#10B981"),
        (100, "Moderate (100)", "#FACC15"),
        (150, "Unhealthy (150)", "#F97316"),
    ]:
        if max_y >= level - 10:
            fig.add_hline(
                y=level,
                line_dash="dot",
                line_color=clr,
                line_width=1,
                opacity=0.65,
                annotation_text=lbl,
                annotation_position="top right",
                annotation_font=dict(size=10, color=clr),
            )

    layout = _base_layout(f"Next {hours}h Live US AQI Forecast", height=340)
    layout["title"]["font"]["size"] = 14
    layout["xaxis"] = dict(
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickformat="%I %p\n%b %d",
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["yaxis"] = dict(
        title=dict(text="US AQI", font=dict(color=TEXT_MUTED, size=11)),
        range=[0, max_y],
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


def create_pollutant_who_chart(pollutants: Dict[str, PollutantReading]) -> Optional[go.Figure]:
    """Compare available live pollutants against WHO 2021 guidelines (multiple of WHO limit)."""
    rows = []
    for p in pollutants.values():
        if p.available and p.value is not None and p.who_ratio is not None:
            rows.append(
                {
                    "label": f"{p.formula}",
                    "ratio": round(p.who_ratio, 2),
                    "value": p.value,
                    "unit": p.unit,
                    "guideline": p.who_guideline,
                    "basis": p.who_basis,
                }
            )
    if not rows:
        return None

    rows.sort(key=lambda r: r["ratio"])
    colors = []
    for r in rows:
        ratio = r["ratio"]
        if ratio <= 1.0:
            colors.append("#10B981")
        elif ratio <= 2.0:
            colors.append("#FACC15")
        elif ratio <= 4.0:
            colors.append("#F97316")
        else:
            colors.append("#EF4444")

    fig = go.Figure(
        go.Bar(
            y=[r["label"] for r in rows],
            x=[r["ratio"] for r in rows],
            orientation="h",
            marker=dict(color=colors, line=dict(width=0), cornerradius=6),
            text=[f"{r['ratio']:.2f}×" for r in rows],
            textposition="outside",
            cliponaxis=False,
            textfont=dict(color=TEXT_PRIMARY, size=11, family="JetBrains Mono, monospace"),
            customdata=[[r["basis"], r["value"], r["unit"], r["guideline"]] for r in rows],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Live Reading: %{customdata[1]:.1f} %{customdata[2]}<br>"
                "Reference: %{customdata[0]}<br>"
                "Ratio: <b>%{x:.2f}× WHO guideline</b><extra></extra>"
            ),
        )
    )

    max_x = max(1.6, max(r["ratio"] for r in rows) * 1.48)
    fig.add_vline(
        x=1.0,
        line_dash="dash",
        line_color=MINT,
        line_width=1.5,
        annotation_text="WHO 1×",
        annotation_position="top left",
        annotation_font=dict(size=10, color=MINT),
    )

    layout = _base_layout("Pollutants vs WHO Limit (×)", height=340)
    layout["title"]["font"]["size"] = 14
    layout["margin"] = dict(l=18, r=52, t=44, b=36)
    layout["xaxis"] = dict(
        title=dict(text="× WHO Guideline", font=dict(color=TEXT_MUTED, size=11)),
        range=[0, max_x],
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["yaxis"] = dict(
        showgrid=False,
        tickfont=dict(color=TEXT_PRIMARY, size=12),
    )
    fig.update_layout(**layout)
    return fig


def create_pollutant_trend_chart(hourly_df: pd.DataFrame, hours: int = 24) -> Optional[go.Figure]:
    """Multi-series live hourly pollutant chart (PM2.5, PM10, NO2, O3)."""
    if hourly_df.empty:
        return None
    df = hourly_df.head(hours)
    series_spec = [
        ("pm2_5", "PM2.5 (μg/m³)", "#EF4444"),
        ("pm10", "PM10 (μg/m³)", "#F97316"),
        ("nitrogen_dioxide", "NO₂ (μg/m³)", "#38BDF8"),
        ("ozone", "O₃ (μg/m³)", "#34D399"),
    ]

    fig = go.Figure()
    added = 0
    for col, label, clr in series_spec:
        if col in df.columns and df[col].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=df["time"],
                    y=df[col],
                    mode="lines",
                    name=label,
                    line=dict(color=clr, width=2.2),
                    hovertemplate=f"<b>{label}</b>: %{{y:.1f}}<br>%{{x|%b %d, %I:%M %p}}<extra></extra>",
                )
            )
            added += 1

    if added == 0:
        return None

    layout = _base_layout(f"Next {hours}-Hour Pollutant Concentrations (Live Forecast)", height=310)
    layout["xaxis"] = dict(
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickformat="%I %p\n%b %d",
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["yaxis"] = dict(
        title=dict(text="Concentration (μg/m³)", font=dict(color=TEXT_MUTED, size=11)),
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["legend"] = dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1.0,
        font=dict(size=11, color=TEXT_PRIMARY),
    )
    fig.update_layout(**layout)
    return fig


def create_travel_comparison_chart(
    current_mode_key: str,
    one_way_km: float,
    days_per_week: int,
    evaluations: List[TravelOptionEvaluation],
    weeks_per_year: int = 48,
) -> go.Figure:
    """Compare annual CO2e footprint of current commute vs eco-friendly alternatives."""
    annual_km = max(0.0, one_way_km) * 2.0 * max(0, days_per_week) * weeks_per_year
    cur = TRANSPORT_MODES[current_mode_key]
    cur_co2 = round(annual_km * cur.co2e_kg_per_pkm, 1)

    labels = [f"{cur.icon} {cur.label} (Current)"]
    values = [cur_co2]
    colors = ["#EF4444"]

    for ev in evaluations:
        alt_co2 = round(annual_km * ev.mode.co2e_kg_per_pkm, 1)
        labels.append(f"{ev.mode.icon} {ev.mode.label}")
        values.append(alt_co2)
        colors.append("#10B981" if alt_co2 == 0 else "#34D399")

    fig = go.Figure(
        go.Bar(
            y=labels[::-1],
            x=values[::-1],
            orientation="h",
            marker=dict(color=colors[::-1], cornerradius=6),
            text=[f"{v:,.1f} kg CO₂e/yr" for v in values[::-1]],
            textposition="outside",
            textfont=dict(color=TEXT_PRIMARY, size=11, family="JetBrains Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>Estimated Annual Emissions: <b>%{x:,.1f} kg CO₂e</b><extra></extra>",
        )
    )
    max_x = max(10.0, max(values) * 1.35) if values else 100.0
    layout = _base_layout("Annual Commute Emissions Comparison (Transparent DEFRA Factors)", height=320)
    layout["xaxis"] = dict(
        title=dict(text="Estimated Annual CO₂e (kg/year)", font=dict(color=TEXT_MUTED, size=11)),
        range=[0, max_x],
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["yaxis"] = dict(showgrid=False, tickfont=dict(color=TEXT_PRIMARY, size=11))
    fig.update_layout(**layout)
    return fig


def create_impact_breakdown_chart(report: HouseholdImpactReport) -> Optional[go.Figure]:
    """Visualize annual CO2e avoided by each selected household habit."""
    if not report.items:
        return None

    labels = [item.action_name for item in report.items]
    values = [item.annual_co2_kg for item in report.items]
    palette = {"Transport": "#10B981", "Home Energy": "#38BDF8", "Zero Burning": "#34D399"}
    colors = [palette.get(item.category, MINT) for item in report.items]

    fig = go.Figure(
        go.Bar(
            y=labels[::-1],
            x=values[::-1],
            orientation="h",
            marker=dict(color=colors[::-1], cornerradius=6),
            text=[f"{v:,.1f} kg/yr" for v in values[::-1]],
            textposition="outside",
            textfont=dict(color=TEXT_PRIMARY, size=11, family="JetBrains Mono, monospace"),
            hovertemplate="<b>%{y}</b><br>Estimated Annual Reduction: <b>%{x:,.1f} kg CO₂e/yr</b><extra></extra>",
        )
    )
    max_x = max(10.0, max(values) * 1.35)
    layout = _base_layout("Estimated Annual CO₂e Reduction by Habit", height=max(240, 72 * len(labels) + 90))
    layout["xaxis"] = dict(
        title=dict(text="Estimated Annual CO₂e Saved (kg/year)", font=dict(color=TEXT_MUTED, size=11)),
        range=[0, max_x],
        showgrid=True,
        gridcolor=GRID_COLOR,
        tickfont=dict(color=TEXT_MUTED, size=10),
    )
    layout["yaxis"] = dict(showgrid=False, tickfont=dict(color=TEXT_PRIMARY, size=11))
    fig.update_layout(**layout)
    return fig
