"""
Basic tests for the rule-based NLP pipeline.
Run with: python -m pytest ai-service/tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.nlp import detect_intent, extract_location, extract_time_range, detect_domain
from services.normalizer import normalize
from services.lang_detect import detect_language


# ── Normalizer ───────────────────────────────────────────────────────────────
def test_normalize_lowercase():
    assert normalize("What Is The WEATHER") == "what is the weather"

def test_normalize_contraction():
    assert "will not" in normalize("won't it rain")

def test_normalize_repeat():
    result = normalize("baaaarish ho rahi haiiii")
    assert "baaarish" not in result  # collapsed

def test_normalize_synonym():
    result = normalize("aaj mausam kaisa hai")
    assert "today" in result or "weather" in result


# ── Language detection ───────────────────────────────────────────────────────
def test_lang_english():
    r = detect_language("Will it rain in Mumbai tomorrow?")
    assert r["lang"] == "en"

def test_lang_hindi_devanagari():
    r = detect_language("कल मुंबई में बारिश होगी?")
    assert r["lang"] in ("hi", "mr")

def test_lang_hinglish():
    r = detect_language("aaj kya mausam hai yaar")
    assert r["lang"] in ("hi-Latn", "en")

def test_lang_tamil():
    r = detect_language("நாளை மழை பெய்யுமா?")
    assert r["lang"] == "ta"


# ── Intent detection ─────────────────────────────────────────────────────────
def test_intent_current():
    assert detect_intent("what is the weather in Delhi") == "current"

def test_intent_forecast():
    # v2 nlp has a dedicated 'rain' intent; time-bound rain queries → rain, not forecast
    assert detect_intent("will it rain tomorrow in Mumbai") == "rain"
    assert detect_intent("7 day forecast for Chennai") == "forecast"

def test_intent_alerts():
    assert detect_intent("any cyclone warning near coast") == "alerts"

def test_intent_umbrella():
    assert detect_intent("should I carry an umbrella today") == "umbrella"

def test_intent_heatwave():
    assert detect_intent("is there a heatwave in Nagpur") == "heatwave"

def test_intent_fog():
    assert detect_intent("is it foggy in Delhi this morning") == "fog"

def test_intent_climate():
    assert detect_intent("show me historical rainfall in Pune last 10 years") == "climate"

def test_intent_greeting():
    assert detect_intent("hello") == "greeting"
    assert detect_intent("hi there") == "greeting"

def test_intent_outdoor():
    assert detect_intent("is it good weather for a picnic") == "outdoor"

def test_intent_clothing():
    assert detect_intent("what should I wear today") == "clothing"


# ── Location extraction ──────────────────────────────────────────────────────
def test_location_known_city():
    assert extract_location("weather in Mumbai today") == "Mumbai"

def test_location_case_insensitive():
    loc = extract_location("will it rain in pune tomorrow")
    assert loc is not None and "Pune" in loc

def test_location_prepositional():
    loc = extract_location("forecast for Nashik this weekend")
    assert loc is not None


# ── Time extraction ──────────────────────────────────────────────────────────
def test_time_today():
    assert extract_time_range("weather today in Delhi") == "today"

def test_time_tomorrow():
    assert extract_time_range("will it rain tomorrow") == "tomorrow"

def test_time_weekend():
    assert extract_time_range("weather this weekend in Goa") == "weekend"

def test_time_this_week():
    assert extract_time_range("forecast for this week") == "this_week"


# ── Domain detection ─────────────────────────────────────────────────────────
def test_domain_agriculture():
    assert detect_domain("should I spray pesticide on my cotton crop") == "agriculture"

def test_domain_marine():
    assert detect_domain("is it safe to go fishing tomorrow") == "marine"

def test_domain_aviation():
    assert detect_domain("weather briefing for my flight") == "aviation"

def test_domain_general():
    assert detect_domain("will it rain tomorrow") == "general"
