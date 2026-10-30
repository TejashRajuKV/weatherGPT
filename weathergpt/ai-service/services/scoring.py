"""
WeatherGPT scoring helpers  (feature #1, #2, #7)
=================================================
Pure-python (stdlib only) scoring used by the activity planner, travel/commute
advice and the health & comfort index.

All functions accept Open-Meteo style hourly lists:

    [{"time": "2026-10-30T09:00", "temperature_2m": 28.1,
      "precipitation": 0.0, "precipitation_probability": 5,
      "relative_humidity_2m": 55, "windspeed_10m": 12.0,
      "uv_index": 3.2, "visibility": 20000, "weather_code": 1}, ...]

Missing values are tolerated — every metric is optional and scores simply
skip what it does not have.
"""
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Activity profiles:  key = (label, emoji, [hour-window hints])
# Each profile defines per-metric ideal ranges; a score of 1.0 means perfect.
# ─────────────────────────────────────────────────────────────────────────────
ACTIVITY_PROFILES = {
    "cycling": {
        "label": "Cycling", "emoji": "🚴",
        "temp": (12, 32), "wind_max": 35, "rain_max": 0.5, "prob_max": 40,
        "uv_max": 8, "hum_max": None, "prefer_hours": (5, 10, 16, 20),
    },
    "running": {
        "label": "Running / jogging", "emoji": "🏃",
        "temp": (10, 30), "wind_max": 35, "rain_max": 0.5, "prob_max": 40,
        "uv_max": 8, "hum_max": None, "prefer_hours": (5, 9, 17, 21),
    },
    "walking": {
        "label": "Outdoor walk", "emoji": "🚶",
        "temp": (10, 33), "wind_max": 40, "rain_max": 1.0, "prob_max": 50,
        "uv_max": 9, "hum_max": None, "prefer_hours": (6, 10, 16, 20),
    },
    "picnic": {
        "label": "Picnic / outdoor event", "emoji": "🧺",
        "temp": (15, 32), "wind_max": 30, "rain_max": 0.2, "prob_max": 25,
        "uv_max": 9, "hum_max": None, "prefer_hours": (7, 10, 15, 19),
    },
    "event": {
        "label": "Outdoor event", "emoji": "🎪",
        "temp": (14, 33), "wind_max": 35, "rain_max": 0.2, "prob_max": 25,
        "uv_max": 9, "hum_max": None, "prefer_hours": (7, 10, 15, 20),
    },
    "cricket": {
        "label": "Cricket / outdoor sports", "emoji": "🏏",
        "temp": (14, 34), "wind_max": 35, "rain_max": 0.2, "prob_max": 30,
        "uv_max": 9, "hum_max": None, "prefer_hours": (7, 10, 15, 19),
    },
    "laundry": {
        "label": "Drying clothes outdoors", "emoji": "👕",
        "temp": (20, 40), "wind_max": 60, "rain_max": 0.0, "prob_max": 15,
        "uv_max": 12, "hum_max": 70, "prefer_hours": (9, 16),
    },
    "spraying": {
        "label": "Crop spraying", "emoji": "🌾",
        "temp": (10, 30), "wind_max": 15, "rain_max": 0.0, "prob_max": 30,
        "uv_max": 10, "hum_max": None, "prefer_hours": (6, 10, 16, 19),
    },
    "fishing": {
        "label": "Fishing / boating", "emoji": "🎣",
        "temp": (12, 35), "wind_max": 30, "rain_max": 1.0, "prob_max": 50,
        "uv_max": 10, "hum_max": None, "prefer_hours": (5, 10, 16, 20),
    },
    "solar": {
        "label": "Solar-panel cleaning", "emoji": "☀️",
        "temp": (10, 40), "wind_max": 40, "rain_max": 0.0, "prob_max": 20,
        "uv_max": 12, "hum_max": None, "prefer_hours": (6, 11),
    },
    "photography": {
        "label": "Outdoor photography", "emoji": "📷",
        "temp": (8, 34), "wind_max": 40, "rain_max": 0.5, "prob_max": 40,
        "uv_max": 11, "hum_max": None, "prefer_hours": (5, 9, 16, 20),
    },
    "general": {
        "label": "Being outdoors", "emoji": "🌤",
        "temp": (12, 34), "wind_max": 40, "rain_max": 1.0, "prob_max": 50,
        "uv_max": 9, "hum_max": None, "prefer_hours": (6, 10, 16, 20),
    },
}


def _band(value, lo, hi):
    """1.0 inside [lo, hi], falls off smoothly outside."""
    if value is None:
        return 1.0
    if lo <= value <= hi:
        return 1.0
    span = max(hi - lo, 1.0)
    d = (lo - value) if value < lo else (value - hi)
    return max(0.0, 1.0 - d / (span * 0.6))


def _cap_score(value, cap, soft=1.5):
    """1.0 up to `cap`, decaying to 0 at cap*soft-ish beyond."""
    if value is None or cap is None:
        return 1.0
    if value <= cap:
        return 1.0
    return max(0.0, 1.0 - (value - cap) / max(cap * soft, 1.0))


def score_hour(h: dict, profile: dict) -> float:
    s = 0.0
    wsum = 0.0

    temp = h.get("temperature_2m")
    lo, hi = profile["temp"]
    s += 2.5 * _band(temp, lo, hi); wsum += 2.5

    wind = h.get("windspeed_10m")
    s += 2.0 * _cap_score(wind, profile["wind_max"], 1.2); wsum += 2.0

    prob = h.get("precipitation_probability")
    rain = h.get("precipitation") or 0.0
    if prob is None:
        prob_score = 1.0 if rain <= profile["rain_max"] else 0.2
    else:
        p1 = _cap_score(prob, profile["prob_max"], 1.5)
        p2 = 1.0 if rain <= profile["rain_max"] else 0.25
        prob_score = min(p1, p2) if rain > profile["rain_max"] else p1
    s += 3.0 * prob_score; wsum += 3.0

    hum = h.get("relative_humidity_2m")
    hmax = profile.get("hum_max")
    if hmax is not None:
        s += 1.0 * _cap_score(hum, hmax, 1.4); wsum += 1.0

    uv = h.get("uv_index")
    s += 1.0 * _cap_score(uv, profile["uv_max"], 1.3); wsum += 1.0

    code = h.get("weather_code")
    if code is not None:
        thunder = 1.0 if code >= 95 else 1.0
        s += 0.5 * (0.0 if code >= 95 else 1.0); wsum += 0.5

    return s / wsum if wsum else 0.0


def hour_of(t: str) -> int:
    try:
        return int(t[11:13])
    except Exception:
        return 12


def in_preferred_hours(hh: int, windows) -> bool:
    if len(windows) == 2:
        return windows[0] <= hh < windows[1]
    a, b, c, d = windows
    return (a <= hh < b) or (c <= hh < d)


def plan_activity(hours: list, day_label: str = "", activity_key: str = "general",
                  window_hours: Optional[tuple] = None, top_n: int = 3) -> dict:
    """
    Score every hour of `hours` for the given activity and return the best
    contiguous windows.  window_hours=(start,end) restricts the search
    (e.g. "tomorrow morning" -> (5, 12)).
    """
    prof = ACTIVITY_PROFILES.get(activity_key, ACTIVITY_PROFILES["general"])
    scored = []
    for h in hours or []:
        hh = hour_of(h.get("time", ""))
        if window_hours and not (window_hours[0] <= hh < window_hours[1]):
            continue
        sc = score_hour(h, prof)
        # small bonus for the activity's preferred time-of-day
        if in_preferred_hours(hh, prof["prefer_hours"]):
            sc = min(1.0, sc + 0.05)
        scored.append((sc, h, hh))
    if not scored:
        return {"activity": prof["label"], "emoji": prof["emoji"], "day": day_label,
                "best": [], "overall": 0.0, "verdict": "No hourly data available."}

    scored.sort(key=lambda x: -x[0])
    best = []
    seen_hours = set()
    for sc, h, hh in scored[:top_n]:
        if hh in seen_hours:
            continue
        seen_hours.add(hh)
        best.append({
            "hour": f"{hh:02d}:00",
            "score": round(sc * 100),
            "temp": h.get("temperature_2m"),
            "rain_prob": h.get("precipitation_probability"),
            "rain_mm": h.get("precipitation"),
            "wind": h.get("windspeed_10m"),
            "humidity": h.get("relative_humidity_2m"),
            "uv": h.get("uv_index"),
        })
    overall = sum(sc for sc, _, _ in scored) / len(scored)
    verdict = verdict_for(overall)
    return {"activity": prof["label"], "emoji": prof["emoji"], "day": day_label,
            "best": best, "overall": round(overall * 100), "verdict": verdict}


def verdict_for(score01: float) -> str:
    if score01 >= 0.8:   return "Excellent conditions ✅"
    if score01 >= 0.65:  return "Good conditions 👍"
    if score01 >= 0.5:   return "Doable with caveats ⚠️"
    if score01 >= 0.35:  return "Poor conditions 😕"
    return "Not recommended ❌"


def score_label(score_pct: int) -> str:
    if score_pct >= 80:  return "Excellent ✅"
    if score_pct >= 65:  return "Good 👍"
    if score_pct >= 50:  return "Fair ⚠️"
    if score_pct >= 35:  return "Poor 😕"
    return "Bad ❌"


# ─────────────────────────────────────────────────────────────────────────────
# Health & comfort indices (feature #7)
# ─────────────────────────────────────────────────────────────────────────────
def heat_index_c(temp_c, rh):
    """Rothfusz regression in °C."""
    if temp_c is None or rh is None:
        return temp_c
    if temp_c < 27:
        return round(float(temp_c), 1)
    T = temp_c * 9 / 5 + 32
    HI = (-42.379 + 2.04901523 * T + 10.14333127 * rh
          - 0.22475541 * T * rh - 6.83783e-3 * T ** 2
          - 5.481717e-2 * rh ** 2 + 1.22874e-3 * T ** 2 * rh
          + 8.5282e-4 * T * rh ** 2 - 1.99e-6 * T ** 2 * rh ** 2)
    return round((HI - 32) * 5 / 9, 1)


def humidex_c(temp_c, rh):
    """Canadian Humidex from dewpoint (Magnus approximation)."""
    if temp_c is None or rh is None:
        return None
    try:
        alpha = 17.27 * temp_c / (temp_c + 237.7) + __import__("math").log(max(rh, 1) / 100.0)
        td = 237.7 * alpha / (17.27 - alpha)
        e = 6.11 * __import__("math").exp(3734.0 / 273.16 * td / (td + 237.7))
        return round(temp_c + 0.555 * (e - 10.0), 1)
    except Exception:
        return None


def humidex_label(hx):
    if hx is None:      return "unknown"
    if hx < 20:         return "comfortable"
    if hx < 30:         return "little discomfort"
    if hx < 40:         return "some discomfort — watch hydration"
    if hx < 45:         return "great discomfort — reduce outdoor effort"
    return "dangerous — avoid outdoor exertion 🚨"


def heat_stress_advice(temp_c, rh):
    hi = heat_index_c(temp_c, rh)
    if hi is None:
        return None
    if hi < 27:  return "Low risk. Normal activity is fine."
    if hi < 32:  return "Moderate risk — drink water regularly during prolonged exposure."
    if hi < 38:  return "High risk — limit strenuous outdoor work, take shaded breaks."
    if hi < 46:  return "Very high risk — heat exhaustion possible; avoid midday sun. ⚠️"
    return "Extreme danger — heat stroke likely with exposure. Stay indoors / cool. 🚨"


AQI_BANDS = [
    (50,  "Good", "#22c55e", "Air quality is satisfactory; outdoor activity is safe."),
    (100, "Moderate", "#eab308", "Acceptable air quality; unusually sensitive people should limit long exertion."),
    (150, "Unhealthy for Sensitive Groups", "#f97316", "People with lung/heart disease, children and elderly should reduce prolonged outdoor exertion."),
    (200, "Unhealthy", "#ef4444", "Everyone may begin to feel effects; limit outdoor activity."),
    (300, "Very Unhealthy", "#a855f7", "Health alert — avoid outdoor exertion, keep windows closed. ⚠️"),
    (10 ** 9, "Hazardous", "#991b1b", "Emergency conditions — stay indoors with filtered air. 🚨"),
]


def aqi_band(aqi):
    if aqi is None:
        return None
    for lim, label, color, advice in AQI_BANDS:
        if aqi <= lim:
            return {"aqi": aqi, "label": label, "color": color, "advice": advice}
    return None


def asthma_advice(aqi, pollen=None, temp_c=None, rh=None, wind=None):
    bits = []
    band = aqi_band(aqi) if aqi is not None else None
    if band:
        if band["label"] in ("Good", "Moderate"):
            bits.append(f"Air quality {band['label']} — generally OK for outdoor time.")
        elif band["label"] in ("Unhealthy for Sensitive Groups", "Unhealthy"):
            bits.append(f"Air quality {band['label']} — asthmatics should carry a reliever inhaler and prefer early-morning outdoor time. ⚠️")
        else:
            bits.append(f"Air quality {band['label']} — asthmatics should stay indoors. 🚨")
    if pollen is not None:
        if pollen >= 6:   bits.append("High pollen load — worst trigger window; consider masking outdoors.")
        elif pollen >= 3: bits.append("Moderate pollen load — sensitive individuals may need pre-medication.")
        else:             bits.append("Low pollen load.")
    if temp_c is not None and rh is not None:
        if temp_c < 10:
            bits.append("Cold air can trigger bronchospasm — cover mouth/nose on exertion.")
        if rh > 80:
            bits.append("High humidity favours mould/dust-mite triggers indoors.")
        if rh < 30:
            bits.append("Dry air irritates airways — hydrate well.")
    if wind is not None and wind > 35:
        bits.append("Strong winds stir up dust and pollutants.")
    return bits


def uv_advice(uv):
    if uv is None:       return None
    if uv < 3:   return (f"UV {uv:.0f} — Low. Sunglasses on bright days; no special protection needed.")
    if uv < 6:   return (f"UV {uv:.0f} — Moderate. Sunscreen if outside >30 min, hat advisable.")
    if uv < 8:   return (f"UV {uv:.0f} — High. Seek shade around midday; SPF 30+, hat, sunglasses.")
    if uv < 11:  return (f"UV {uv:.0f} — Very high. Avoid direct sun between 11 AM and 3 PM; SPF 50+, protective clothing.")
    return (f"UV {uv:.0f} — Extreme. Unprotected skin burns within minutes; stay indoors at midday. 🚨")


def visibility_risk(vis_m):
    """Returns (level, text) from metres."""
    if vis_m is None:
        return None
    if vis_m >= 10000:  return ("good", "excellent (>10 km)")
    if vis_m >= 4000:   return ("moderate", "fair (4–10 km)")
    if vis_m >= 1000:   return ("poor", "poor (1–4 km) — drive with care")
    if vis_m >= 500:    return ("very_poor", "very poor (<1 km) — fog risk ⚠️")
    return ("hazardous", "dangerously low (<500 m) — delay travel if possible 🚨")
