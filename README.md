# 🌿 AirAware AI — Urban Air Quality Assistant

**Built for Hack2Skill PromptWars Challenge 6 – Urban Air Quality Assistant**

AirAware AI is a modern, AI-powered Streamlit web application designed to help families and communities navigate severe winter smog and urban air pollution using **real-time Open-Meteo air quality data**, **Google Gemini personalized coaching**, and **transparent environmental impact calculations**.

---

## ✨ Core Features

1. **📊 Live Air Quality Dashboard**
   - Global city lookup with automatic disambiguation via the **Open-Meteo Geocoding API**.
   - Real-time **US EPA AQI**, **European AQI**, and pollutant concentrations (**PM2.5, PM10, NO₂, CO, O₃, SO₂, Dust, Aerosol Optical Depth**) via the **Open-Meteo Air Quality API**.
   - Clear visual distinction between `● LIVE` readings and `○ UNAVAILABLE` fields — **AQI and pollutant numbers are never invented**.
   - Prominent local data timestamp, timezone, UTC fetch timestamp, EPA color-coded gauge, WHO 2021 guideline comparison chart, and 24h/48h interactive forecast trajectories.

2. **🤖 AI Smart Assistant (Google Gemini)**
   - Powered by the official `google-genai` SDK (`gemini-3.8-flash` with automatic fallback).
   - Grounds every prompt in live city readings, forecast windows, and the user's **Family & Home Profile** (children, seniors, asthma/sensitivities, purifier access, commute type).
   - Includes a one-click **Personalized Action Briefing** and a multi-turn **Ask AirAware AI** chat assistant.
   - Gracefully falls back to clearly-labeled **deterministic live-data health guidance** if `GEMINI_API_KEY` is not yet configured or if the API is unreachable.

3. **🗓️ Smart Daily Routine**
   - Analyzes live next-24-hour Open-Meteo forecasts to pinpoint the **cleanest 2-hour outdoor window**, **peak smog hour**, and **safe ventilation hours (AQI ≤ 100)**.
   - Suggests low-emission daily activities, practical pollution precautions, and an AI-generated hour-by-hour family routine.

4. **🏠 Indoor Air Quality Hacks**
   - **Outdoor-aware ventilation advisor** (`SAFE TO OPEN WINDOWS` vs `KEEP WINDOWS SEALED`) driven directly by live AQI.
   - Affordable clean-air solutions (DIY Corsi-Rosenthal box fan + MERV-13 filter, clean-air bedroom setup, wet mopping, zero-smoke kitchen habits).
   - Interactive smog-readiness checklist and budget-tiered AI indoor protocol.

5. **🚲 Eco-Friendly Travel**
   - Evaluates Walking, Cycling, Metro/Rail, Public Bus, and 3-Person Carpooling against the user's current commute.
   - **Winter-smog aware**: automatically warns when high live AQI (>150) makes enclosed low-emission transit safer than unmasked cycling/walking.
   - Displays exact CO₂e, NOx, and PM2.5 savings formulas using published UK DEFRA/DESNZ 2024 & EEA factors.

6. **🌱 Pollution Impact Tracker**
   - Interactive personal & household calculator covering commute shifts, reduced vehicle idling, home electricity conservation, and avoiding open leaf/yard-waste burning.
   - **100% transparent math**: every number includes its exact formula, user inputs, and published emission-factor citation (DEFRA, US EPA MOVES/AP-42, IEA), plus a linear 1,000-family community scale-up.

---

## 🏗️ Project Architecture

```text
AirAware-AI/
├── .streamlit/
│   └── config.toml             # Dark navy & emerald theme configuration
├── src/
│   ├── __init__.py
│   ├── config.py               # Environment loading, EPA AQI bands, WHO 2021 guidelines
│   ├── air_quality.py          # Open-Meteo Geocoding & Air Quality API client + strict null safety
│   ├── gemini_assistant.py     # Google Gemini integration (google-genai) + deterministic fallback
│   ├── impact_calculator.py    # Transparent, source-cited eco-travel & household impact engine
│   ├── charts.py               # Interactive Plotly gauges, trajectories, and comparison charts
│   └── styles.py               # Custom dark navy & emerald CSS + reusable glassmorphic UI cards
├── tests/
│   └── test_core.py            # Automated pytest suite for API parsing, math, & fallbacks
├── app.py                      # Main Streamlit dashboard application
├── requirements.txt            # Python runtime dependencies
├── .env.example                # Environment variable template (safe to commit)
├── .gitignore
└── README.md
```

---

## 🚀 Local Setup & Running

### 1. Prerequisites
- Python **3.10+** (tested on Python 3.13)
- A free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) *(optional to start exploring live AQI, required for live Gemini AI generation)*

### 2. Clone & Create Virtual Environment
```bash
git clone <your-repo-url>
cd AirAware-AI

python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and add your Gemini API key:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# macOS / Linux
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
DEFAULT_CITY=New Delhi
```
> **Security Note:** `.env` is excluded via `.gitignore`. API keys are read strictly from server-side environment variables (or `st.secrets`) and are never exposed in frontend code or UI logs.

### 5. Run the Application
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

---

## 🧪 Running Tests

```bash
pip install pytest
pytest -v
```

---

## ☁️ Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub (verify `.env` is **not** committed).
2. Go to [share.streamlit.io](https://share.streamlit.io/) and click **New app**.
3. Select your repository, branch, and set **Main file path** to `app.py`.
4. Open **Advanced settings → Secrets** and add:
   ```toml
   GEMINI_API_KEY = "your_actual_gemini_api_key"
   GEMINI_MODEL = "gemini-3.8-flash"
   DEFAULT_CITY = "New Delhi"
   ```
5. Click **Deploy**. Open-Meteo Geocoding & Air Quality APIs work automatically with zero API key setup.

---

## 📜 Data Sources & Integrity

- **Real-Time Air Quality & Forecasts:** [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) (Copernicus CAMS / global atmospheric models)
- **City Location Detection:** [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- **Health Benchmarks:** US EPA AQI Standard & WHO Global Air Quality Guidelines (2021)
- **Emission Factors:** UK DEFRA/DESNZ 2024 Conversion Factors, US EPA MOVES & AP-42, IEA Grid Carbon Intensity
- **Medical Disclaimer:** AirAware AI provides informational guidance and is not a substitute for professional medical advice. Consult a healthcare provider if experiencing acute respiratory or cardiovascular symptoms.
