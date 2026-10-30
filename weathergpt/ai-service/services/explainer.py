"""
WeatherGPT "Explain this forecast" layer  (feature #5)
======================================================
Non-LLM, deterministic translation of technical weather values into plain
meaning.  Used by:

  * the /explain API endpoint in the AI service
  * the chat engine to append a one-line explanation when the user asks
    ("explain rain probability", "what does uv 9 mean", ...)

Every function is pure and offline — no network, no model.
"""

PROBABILITY_MEANING = [
    (0,   "almost certain dry — the forecast models see no rain signal at all"),
    (10,  "very low chance — plan as if it will stay dry"),
    (20,  "slight chance — unlikely, but don't rule an umbrella out for sensitive plans"),
    (30,  "light chance — it might spot-rain; most people at that time will stay dry. It does NOT mean it rains 30% of the time or over 30% of the area"),
    (40,  "chance worth planning around — half the models see rain nearby"),
    (50,  "coin-flip — equally likely to rain or not; carry an umbrella"),
    (60,  "likely — more models say yes than no; expect at least a few drops"),
    (70,  "highly likely — plan indoor backup for anything outdoors"),
    (80,  "almost certain — treat rain as the default assumption"),
    (91,  "near certainty — heavy organised rain is expected"),
]


def explain_probability(pct) -> str:
    """What a precipitation probability really means."""
    if pct is None:
        return "Probability was not available in this dataset."
    pct = float(pct)
    prev = 0
    for lim, meaning in PROBABILITY_MEANING:
        if pct <= lim:
            return f"{pct:.0f}% rain probability means {meaning}."
        prev = lim
    return f"{pct:.0f}% rain probability means near certainty of rain."


UV_LEVELS = [
    (2,  "Low", "No protection needed; bright sunlight may still warrant sunglasses."),
    (5,  "Moderate", "Cover up, sunscreen SPF 30+, hat on long exposure."),
    (7,  "High", "Unprotected skin burns in ~15–25 minutes; shade at midday."),
    (10, "Very high", "Burn time under ~15 minutes; avoid direct sun 11 AM–3 PM, SPF 50+."),
    (99, "Extreme", "Burn within minutes; seek shade, full coverage clothing."),
]


def explain_uv(uv) -> str:
    if uv is None:
        return "UV index was not available for this location/time."
    for lim, label, advice in UV_LEVELS:
        if uv <= lim:
            return f"UV index {uv:g} is {label}. {advice}"
    return f"UV index {uv:g} is Extreme."


WIND_LEVELS = [
    (2,  "calm", "smoke rises vertically; bad for spray drift dispersion"),
    (6,  "light air", "leaves barely move"),
    (12, "light breeze", "pleasant for cycling/walking"),
    (20, "gentle breeze", "dries laundry slowly but steadily"),
    (29, "moderate breeze", "good drying wind; flags extend"),
    (39, "fresh breeze", "umbrellas start to struggle; cycling in open areas gets harder"),
    (50, "strong breeze", "small branches move; awkward for spraying and two-wheelers"),
    (62, "near gale", "use caution with tall vehicles and loose structures ⚠️"),
    (75, "gale", "outdoor work and two-wheeler travel unsafe ⚠️"),
    (89, "strong gale", "stay indoors if possible 🚨"),
    (10 ** 6, "storm force", "dangerous — structural risk 🚨"),
]


def explain_wind(kmh) -> str:
    if kmh is None:
        return "Wind speed was not available."
    for lim, label, meaning in WIND_LEVELS:
        if kmh <= lim:
            return f"{kmh:g} km/h is a {label} wind — {meaning}."
    return f"{kmh:g} km/h is storm-force wind 🚨"


RAIN_AMOUNTS = [
    (0.1, "trace", "wet ground patchily; no real impact"),
    (2.5, "very light", "a few minutes of drizzle; negligible runoff"),
    (7.5, "light", "roads get wet; umbrellas out; minor waterlogging only in bad drains"),
    (35.5, "moderate", "sustained rain; local flooding of low spots possible; farming-friendly"),
    (64.5, "heavy", "travel disruption likely; waterlogging in cities; warning level"),
    (115.6, "very heavy", "flash-flood risk; rivers/Nullahs rise fast; avoid travel ⚠️"),
    (204.5, "extremely heavy", "severe flooding risk; disaster alert territory 🚨"),
    (10 ** 7, "beyond scale", "record-level event 🚨"),
]


def explain_rain(mm) -> str:
    if mm is None:
        return "Rainfall amount was not available."
    for lim, label, meaning in RAIN_AMOUNTS:
        if mm <= lim:
            return f"{mm:g} mm is {label} rain — {meaning}. (1 mm ≈ 1 litre per square metre.)"
    return f"{mm:g} mm is extreme rain 🚨"


def explain_humidity(rh) -> str:
    if rh is None:
        return "Humidity was not available."
    if rh < 30:  return f"{rh:.0f}% humidity is dry air — static electricity, irritated throat, faster sweat evaporation."
    if rh < 50:  return f"{rh:.0f}% humidity is comfortable — sweat evaporates efficiently."
    if rh < 65:  return f"{rh:.0f}% humidity is slightly muggy — perceived temperature starts rising above the reading."
    if rh < 80:  return f"{rh:.0f}% humidity is muggy — sweat doesn't evaporate well; feels several degrees hotter; laundry dries slowly."
    return f"{rh:.0f}% humidity is very humid — high discomfort, slower drying, higher mould risk."


def explain_feels_like(temp, feels):
    if temp is None or feels is None:
        return "Feels-like combines temperature, humidity and wind into what your skin actually experiences."
    diff = feels - temp
    if abs(diff) < 1:
        return f"At {temp:.0f}°C the 'feels like' {feels:.0f}°C matches the thermometer — conditions are neutral."
    if diff > 0:
        return f"'Feels like' {feels:.0f}°C vs actual {temp:.0f}°C: humidity is making it feel {diff:.0f}° hotter (sweat can't cool you)."
    return f"'Feels like' {feels:.0f}°C vs actual {temp:.0f}°C: wind is chilling you by {-diff:.0f}° (wind-chill effect)."


def explain_pressure(hpa):
    if hpa is None:
        return "Pressure was not available."
    if hpa < 1000: return f"{hpa:.0f} hPa is low pressure — associated with clouds, rain and storms."
    if hpa < 1013: return f"{hpa:.0f} hPa is slightly below standard (1013 hPa) — unsettled weather possible."
    if hpa < 1020: return f"{hpa:.0f} hPa is near normal — typical fair-weather reading."
    return f"{hpa:.0f} hPa is high pressure — stable, clear, often dry; winter fogs favoured under such calm highs."


def explain_visibility(vis_m):
    if vis_m is None:
        return "Visibility was not available."
    km = vis_m / 1000.0
    if km >= 10: return f"Visibility {km:.0f} km is excellent — no driving restrictions."
    if km >= 4:  return f"Visibility {km:.1f} km is moderate — haze/mist present; use headlights at night."
    if km >= 1:  return f"Visibility {km:.1f} km is poor — fog/drizzle; reduce speed, keep distance."
    return f"Visibility {km*1000:.0f} m is dangerous — dense fog; avoid highway travel if possible 🚨"


def explain_dewpoint(td):
    if td is None:
        return "Dew point was not available."
    if td < 10:  return f"Dew point {td:.0f}°C is dry air — comfortable night."
    if td < 16:  return f"Dew point {td:.0f}°C is mild — most people comfortable."
    if td < 21:  return f"Dew point {td:.0f}°C is somewhat humid — sticky evenings likely."
    if td < 24:  return f"Dew point {td:.0f}°C is oppressive — tropical discomfort, poor sweat cooling."
    return f"Dew point {td:.0f}°C is extremely humid — dangerous for outdoor exertion."


def explain_frost_risk(temp_min, rh=None, wind=None):
    if temp_min is None:
        return None
    if temp_min <= 0:
        return f"Minimum {temp_min:.0f}°C → frost/freezing is expected; protect sensitive crops 🚨"
    if temp_min <= 4:
        return f"Minimum {temp_min:.0f}°C → radiative frost possible on clear calm nights; watch young crops ⚠️"
    if temp_min <= 8:
        return f"Minimum {temp_min:.0f}°C → light frost unlikely but cold-sensitive plants may suffer."
    return f"Minimum {temp_min:.0f}°C → no frost risk."


TOPICS = {
    "probability": ("Rain probability / chance of rain", explain_probability),
    "rain":        ("Rainfall amount", explain_rain),
    "uv":          ("UV index", explain_uv),
    "wind":        ("Wind speed", explain_wind),
    "humidity":    ("Relative humidity", explain_humidity),
    "pressure":    ("Atmospheric pressure", explain_pressure),
    "visibility":  ("Visibility", explain_visibility),
    "dewpoint":    ("Dew point", explain_dewpoint),
    "feels":       ("Feels-like temperature", None),
}

import re as _re

_NUM = _re.compile(r"(\d+(?:\.\d+)?)")


def explain_query(query: str, weather_data: dict = None) -> str:
    """
    Answer an 'explain ...' question. Extracts a number from the query when
    present ("explain uv 9", "what does 30% rain mean"), otherwise uses the
    live/current data supplied by the caller.
    """
    q = (query or "").lower()
    weather_data = weather_data or {}
    cur = (weather_data.get("current") or {})
    # ignore numbers that are just unit words like "km/h"
    m = _NUM.search(_re.sub(r"km/?h", "", q.replace("%", "")))
    num = float(m.group(1)) if m else None

    if _re.search(r"prob|chance of rain|rain ?%|precipitation", q) and not _re.search(r"\bfrost\b|\buv\b|humid|wind|visib|pressure|dew", q):
        return explain_probability(num if num is not None else cur.get("precipitation_probability"))
    if _re.search(r"\buv\b|ultraviolet|sunburn", q):
        return explain_uv(num if num is not None else cur.get("uv_index"))
    if _re.search(r"\bwind\b|breeze|gust|km/?h.*wind|wind.*speed", q):
        return explain_wind(num if num is not None else cur.get("wind_speed"))
    if _re.search(r"humid|sticky|muggy", q):
        return explain_humidity(num if num is not None else cur.get("humidity"))
    if _re.search(r"pressure|hpa|mbars?\b", q):
        return explain_pressure(num if num is not None else cur.get("pressure"))
    if _re.search(r"visib|fog.*how far|kohra", q):
        vis = num * 1000 if (num is not None and num < 100) else num
        return explain_visibility(vis if vis is not None else cur.get("visibility"))
    if _re.search(r"dew ?point", q):
        return explain_dewpoint(num if num is not None else cur.get("dew_point"))
    if _re.search(r"feels? like|apparent", q):
        return explain_feels_like(cur.get("temperature"), cur.get("feels_like"))
    if _re.search(r"\bfrost\b", q):
        return explain_frost_risk(num) or (
            "Frost forms when surfaces reach 0°C — usually on clear, calm nights "
            "even if the day was mild.")
    if _re.search(r"\brain(?:fall|ing)?\b|\bmm\b", q):
        return explain_rain(num if num is not None else cur.get("rainfall_1h"))
    # generic help
    return ("I can explain any forecast value in plain words — try:\n"
            "• \"explain rain probability 30%\"\n"
            "• \"what does UV index 9 mean\"\n"
            "• \"explain wind speed 40 km/h\"\n"
            "• \"explain humidity\", \"explain visibility\", \"explain pressure\", "
            "\"explain dew point\", \"explain feels like\"")
