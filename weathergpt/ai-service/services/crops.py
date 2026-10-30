"""
WeatherGPT crop-calendar engine  (feature #3)
=============================================
Crop + growth-stage specific weather thresholds: frost, heat stress at
flowering, spraying windows, irrigation need and disease risk.

Pure python / stdlib.  Entry point:

    assess_crop(crop_key, stage_key, hours, days_ahead=5) -> dict

`hours` is the Open-Meteo hourly list for the coming days (same shape as in
scoring.py).  The result contains per-concern findings that nlp.py renders.
"""
import math

CROPS = {
    "wheat": {
        "label": "Wheat", "emoji": "🌾",
        "stages": {
            "sowing":     {"frost_critical_min": None, "heat_stress_max": 30, "spray_wind_max": 15,
                           "spray_rain_gap_h": 6, "swp": 0.25, "disease": [("rust", 15, 25, 80)]},
            "germination":{"frost_critical_min": 2,  "heat_stress_max": 32, "spray_wind_max": 15,
                           "spray_rain_gap_h": 6, "swp": 0.25, "disease": []},
            "tillering":  {"frost_critical_min": 0,  "heat_stress_max": 32, "spray_wind_max": 15,
                           "spray_rain_gap_h": 6, "swp": 0.30, "disease": [("yellow rust", 8, 20, 80), ("aphids", 15, 25, 60)]},
            "flowering":  {"frost_critical_min": 4,  "heat_stress_max": 30, "spray_wind_max": 12,
                           "spray_rain_gap_h": 8, "swp": 0.35,
                           "disease": [("head blight", 20, 30, 85, 3)]},
            "grain_filling": {"frost_critical_min": 2, "heat_stress_max": 32, "spray_wind_max": 15,
                              "spray_rain_gap_h": 6, "swp": 0.35, "disease": [("karnal bunt", 18, 26, 80)]},
            "maturity":   {"frost_critical_min": None, "heat_stress_max": 40, "spray_wind_max": 20,
                           "spray_rain_gap_h": 4, "swp": 0.20, "harvest_dry_days": 3},
        },
        "notes": {
            "flowering": "Temperatures above ~30°C at wheat flowering cause sterility and shrivelled grain; dew + 20–30°C favours head blight.",
        },
    },
    "tomato": {
        "label": "Tomato", "emoji": "🍅",
        "stages": {
            "seedling":   {"frost_critical_min": 10, "heat_stress_max": 35, "spray_wind_max": 12,
                           "spray_rain_gap_h": 6, "swp": 0.35, "disease": [("damping off", 18, 28, 90)]},
            "vegetative": {"frost_critical_min": 8,  "heat_stress_max": 35, "spray_wind_max": 12,
                           "spray_rain_gap_h": 6, "swp": 0.40, "disease": [("early blight", 20, 30, 80, 2)]},
            "flowering":  {"frost_critical_min": 10, "heat_stress_max": 35, "spray_wind_max": 10,
                           "spray_rain_gap_h": 8, "swp": 0.45,
                           "disease": [("flower drop — >35°C day or <15°C night", 35, 45, 0)]},
            "fruit_set":  {"frost_critical_min": 10, "heat_stress_max": 38, "spray_wind_max": 10,
                           "spray_rain_gap_h": 8, "swp": 0.50,
                           "disease": [("late blight", 10, 25, 90, 2), ("bacterial spot", 25, 32, 85, 1)]},
            "ripening":   {"frost_critical_min": 10, "heat_stress_max": 40, "spray_wind_max": 15,
                           "spray_rain_gap_h": 4, "swp": 0.40, "disease": [("fruit cracking after heavy rain", 0, 40, 0, 25)]},
        },
        "notes": {
            "flowering": "Tomato flowers drop if day max exceeds ~35°C or night min below ~15°C; good fruit set needs 21–27°C.",
        },
    },
    "cotton": {
        "label": "Cotton", "emoji": "☁️",
        "stages": {
            "sowing":     {"frost_critical_min": None, "heat_stress_max": 40, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.30, "disease": []},
            "squaring":   {"frost_critical_min": 12, "heat_stress_max": 40, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.40, "disease": [("thrips", 20, 32, 60)]},
            "flowering":  {"frost_critical_min": 12, "heat_stress_max": 42, "spray_wind_max": 12, "spray_rain_gap_h": 8, "swp": 0.45, "disease": [("boll rot", 25, 32, 85, 3)]},
            "boll_dev":   {"frost_critical_min": 12, "heat_stress_max": 42, "spray_wind_max": 12, "spray_rain_gap_h": 8, "swp": 0.50, "disease": [("pink bollworm activity", 25, 35, 70)]},
            "opening":    {"frost_critical_min": 10, "heat_stress_max": 45, "spray_wind_max": 20, "spray_rain_gap_h": 4, "swp": 0.30, "disease": [], "harvest_dry_days": 4},
        },
        "notes": {"flowering": "Cotton sheds flowers/bolls above ~42°C or with sustained water stress."},
    },
    "onion": {
        "label": "Onion", "emoji": "🧅",
        "stages": {
            "seedling":   {"frost_critical_min": 5, "heat_stress_max": 35, "spray_wind_max": 12, "spray_rain_gap_h": 6, "swp": 0.35, "disease": [("thrips", 22, 32, 60)]},
            "bulbing":    {"frost_critical_min": 3, "heat_stress_max": 35, "spray_wind_max": 12, "spray_rain_gap_h": 6, "swp": 0.45, "disease": [("purple blotch", 15, 27, 75, 2)]},
            "maturation": {"frost_critical_min": 2, "heat_stress_max": 38, "spray_wind_max": 15, "spray_rain_gap_h": 4, "swp": 0.30, "disease": [], "harvest_dry_days": 5},
        },
        "notes": {"bulbing": "Stop irrigation ~15 days before harvest; rain during maturation delays curing."},
    },
    "soybean": {
        "label": "Soybean", "emoji": "🫘",
        "stages": {
            "vegetative": {"frost_critical_min": 5, "heat_stress_max": 38, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.35, "disease": []},
            "flowering":  {"frost_critical_min": 2, "heat_stress_max": 38, "spray_wind_max": 12, "spray_rain_gap_h": 8, "swp": 0.45, "disease": [("yellow rust", 15, 25, 85)]},
            "pod_fill":   {"frost_critical_min": 2, "heat_stress_max": 40, "spray_wind_max": 12, "spray_rain_gap_h": 6, "swp": 0.50, "disease": []},
        },
        "notes": {"flowering": "Soybean pods abort under >38°C with dry soil at flowering."},
    },
    "rice": {
        "label": "Rice / Paddy", "emoji": "🌱",
        "stages": {
            "nursery":    {"frost_critical_min": 15, "heat_stress_max": 40, "spray_wind_max": 12, "spray_rain_gap_h": 6, "swp": 0.40, "disease": [("blast", 20, 30, 90, 2)]},
            "tillering":  {"frost_critical_min": 12, "heat_stress_max": 40, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.45, "disease": [("blast", 22, 28, 90, 3)]},
            "flowering":  {"frost_critical_min": 15, "heat_stress_max": 40, "spray_wind_max": 10, "spray_rain_gap_h": 8, "swp": 0.50,
                           "disease": [("bacterial blight", 25, 32, 90, 1), ("sheath blight", 25, 30, 90, 3)]},
            "grain_fill": {"frost_critical_min": 12, "heat_stress_max": 35, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.50, "disease": []},
        },
        "notes": {"flowering": "Day temps >40°C at rice anthesis cause spikelet sterility; night <17°C delays maturity."},
    },
    "sugarcane": {
        "label": "Sugarcane", "emoji": "🎋",
        "stages": {
            "planting":   {"frost_critical_min": 10, "heat_stress_max": 45, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.40, "disease": []},
            "grand_growth": {"frost_critical_min": 8, "heat_stress_max": 45, "spray_wind_max": 15, "spray_rain_gap_h": 6, "swp": 0.55, "disease": [("red rot", 24, 32, 85, 3)]},
            "maturity":   {"frost_critical_min": 5, "heat_stress_max": 45, "spray_wind_max": 20, "spray_rain_gap_h": 4, "swp": 0.25, "disease": []},
        },
        "notes": {"maturity": "Dry, cool, sunny weather in the last 6–8 weeks raises sugar recovery; pre-harvest irrigation lowers it."},
    },
}

# generic fallback profile when the crop/stage pair is unknown
_GENERIC_STAGE = {"frost_critical_min": 5, "heat_stress_max": 38, "spray_wind_max": 15,
                  "spray_rain_gap_h": 6, "swp": 0.40, "disease": []}


def find_crop(text: str):
    """Map free text to a crop key."""
    t = (text or "").lower()
    aliases = {
        "wheat": ["wheat", "gehu", "गेहूं", "गेंहू", "गाव"],
        "tomato": ["tomato", "tamatar", "टमाटर", "టమాటా", "தக்காளி"],
        "cotton": ["cotton", "kapas", "कपास", "పత్తి", "பருத்தி"],
        "onion": ["onion", "pyaz", "कांदा", "उల్ली", "ఉల్లి", "வெங்காயம்"],
        "soybean": ["soybean", "soya", "मोयरा", "soyabean"],
        "rice": ["rice", "paddy", "dhan", "भात", "धान", "நெல்"],
        "sugarcane": ["sugarcane", "sugar cane", "ganna", "ऊस", "खंडीर", "पेरु"],
    }
    for key, words in aliases.items():
        for w in words:
            if w and w in t:
                return key
    return None


def find_stage(text: str):
    t = (text or "").lower()
    table = [
        ("flowering", ["flowering", "flower", "blossom", "anthesis", "phul", "फूल", "पुष्प", "flowering stage", "blooming"]),
        ("fruit_set", ["fruit set", "fruiting", "fruits", "fal", "फळ", "పండ్ల"] ),
        ("ripening", ["ripen", "maturity approaching", "pre harvest colour"]),
        ("grain_filling", ["grain fill", "dane", "दाणे", "grain filling"]),
        ("grain_fill", ["grain fill"]),
        ("tillering", ["tiller"]),
        ("boll_dev", ["boll"]),
        ("opening", ["boll opening", "opening"]),
        ("pod_fill", ["pod"]),
        ("squaring", ["square"]),
        ("bulbing", ["bulb"]),
        ("grand_growth", ["grand growth", "growth phase"]),
        ("vegetative", ["vegetative", "leaf", "pat"]),
        ("nursery", ["nursery"]),
        ("germination", ["germinat"]),
        ("sowing", ["sowing", "sown", "buvai", "बुवाई", "peerni", "पेरणी"]),
        ("planting", ["planting", "planted"]),
        ("maturation", ["maturation", "maturity", "tapt"]),
    ]
    for key, words in table:
        for w in words:
            if w in t:
                return key
    return None


def _day_hours(hours, date_str):
    return [h for h in hours or [] if (h.get("time") or "").startswith(date_str)]


def _hour_index_map(hours):
    return {(h.get("time") or "")[:13]: i for i, h in enumerate(hours or [])}


def assess_crop(crop_key: str, stage_key: str, hours: list, days_ahead: int = 5) -> dict:
    """
    Evaluate frost / heat / spray-window / irrigation / disease concerns for a
    crop stage against hourly forecast data.
    """
    crop = CROPS.get(crop_key) or {}
    stages = crop.get("stages") or {}
    stage = stages.get(stage_key) or _GENERIC_STAGE
    label = f"{crop.get('label', crop_key or 'Crop')} · {stage_key.replace('_', ' ').title()}" if stage_key else (crop.get('label') or 'Crop')

    out = {
        "crop": crop_key, "stage": stage_key, "label": label,
        "emoji": crop.get("emoji", "🌱"),
        "note": (crop.get("notes") or {}).get(stage_key, ""),
        "frost": None, "heat": None, "spray_windows": [], "irrigation": None,
        "disease": [], "rain_next_72h": 0.0,
    }

    dates = sorted({(h.get("time") or "")[:10] for h in hours or []})[:days_ahead]
    idx = _hour_index_map(hours)

    # ── frost ────────────────────────────────────────────────────────────
    fcrit = stage.get("frost_critical_min")
    if fcrit is not None and dates:
        hits = []
        for d in dates:
            dh = _day_hours(hours, d)
            mins = [h.get("temperature_2m") for h in dh if h.get("temperature_2m") is not None]
            if not mins:
                continue
            tmin = min(mins)
            if tmin <= fcrit:
                worst = min(dh, key=lambda h: h.get("temperature_2m") or 99)
                hits.append({"date": d, "temp_min": round(tmin, 1),
                             "at": (worst.get("time") or "")[11:16],
                             "critical": fcrit})
        out["frost"] = {"risk": bool(hits), "events": hits, "threshold": fcrit}

    # ── heat stress ──────────────────────────────────────────────────────
    hmax_t = stage.get("heat_stress_max")
    if hmax_t is not None and dates:
        hits = []
        for d in dates:
            dh = [h for h in _day_hours(hours, d) if h.get("temperature_2m") is not None]
            if not dh:
                continue
            tmax = max(h["temperature_2m"] for h in dh)
            if tmax > hmax_t:
                hot_hours = sum(1 for h in dh if h["temperature_2m"] > hmax_t)
                hits.append({"date": d, "temp_max": round(tmax, 1), "hot_hours": hot_hours})
        out["heat"] = {"risk": bool(hits), "events": hits, "threshold": hmax_t}

    # ── spraying windows (next 3 days) ───────────────────────────────────
    wind_cap = stage.get("spray_wind_max", 15)
    gap = stage.get("spray_rain_gap_h", 6)
    windows = []
    for h in hours or []:
        hh = int((h.get("time") or "T12") [11:13])
        if not (5 <= hh <= 19):
            continue
        temp = h.get("temperature_2m")
        wind = h.get("windspeed_10m")
        prob = h.get("precipitation_probability")
        if temp is None or wind is None:
            continue
        if not (5 <= temp <= 30 and wind <= wind_cap):
            continue
        # rain-free look-ahead of `gap` hours
        i = idx.get((h.get("time") or "")[:13])
        future = (hours or [])[i + 1: i + 1 + gap] if i is not None else []
        wet = any((f.get("precipitation") or 0) > 0.1 or (f.get("precipitation_probability") or 0) >= 60 for f in future)
        if wet or (prob is not None and prob >= 60):
            continue
        windows.append({"time": h.get("time"), "temp": round(temp, 1),
                        "wind": round(wind, 1), "rain_prob": prob})
    # keep one window per morning/evening block, first 4
    picked, seen_day_block = [], set()
    for w in windows:
        key = (w["time"][:10], "AM" if int(w["time"][11:13]) < 12 else "PM")
        if key in seen_day_block:
            continue
        seen_day_block.add(key)
        picked.append(w)
    out["spray_windows"] = picked[:4]

    # ── irrigation need (soil-water proxy over last/next 3 days) ─────────
    swp = stage.get("swp", 0.4)
    rain3 = sum((h.get("precipitation") or 0) for h in (hours or [])[:72])
    evap_proxy = 0.0
    for h in (hours or [])[:72]:
        t = h.get("temperature_2m")
        if t is None:
            continue
        evap_proxy += max(0.0, (t - 20)) * 0.12 + (h.get("windspeed_10m") or 0) * 0.03
    deficit = evap_proxy - rain3
    if rain3 >= 25:
        out["irrigation"] = {"need": "skip", "reason": f"{rain3:.0f} mm rain in the last 3 days has recharged the root zone."}
    elif deficit > 22 * swp * 10:
        out["irrigation"] = {"need": "urgent", "reason": f"No effective rain ({rain3:.1f} mm) and high evaporative demand for this stage."}
    elif deficit > 12 * swp * 10:
        out["irrigation"] = {"need": "light", "reason": f"Soil drying trend (rain {rain3:.1f} mm); a light irrigation in 1–2 days suits this stage."}
    else:
        out["irrigation"] = {"need": "ok", "reason": f"Moisture balance adequate (rain {rain3:.1f} mm vs demand ~{evap_proxy:.0f} mm equivalent)."}

    # ── disease risk ─────────────────────────────────────────────────────
    for entry in stage.get("disease") or []:
        if not isinstance(entry, tuple):
            continue
        name, lo, hi, rhmin = entry[0], entry[1], entry[2], entry[3]
        dur = entry[4] if len(entry) > 4 else 0
        streak = best = 0
        best_window = None
        prev_time = None
        for h in hours or []:
            t, r = h.get("temperature_2m"), h.get("relative_humidity_2m")
            wet_ok = (r is not None and r >= rhmin) if rhmin else True
            temp_ok = (t is not None and lo <= t <= hi) if hi else (t is not None)
            cond = wet_ok and temp_ok
            if cond and prev_time and ((h.get("time") or "")[:10] == (prev_time or "")[:10] or True):
                streak += 1
            elif cond:
                streak = 1
            else:
                streak = 0
            prev_time = h.get("time")
            if streak > best:
                best = streak
                best_window = h.get("time")
        threshold_h = max(dur * 24, 6)
        if best >= threshold_h:
            out["disease"].append({"name": name, "hours": best, "until": best_window,
                                   "level": "high" if best >= threshold_h * 1.5 else "moderate"})

    out["rain_next_72h"] = round(rain3, 1)
    return out
