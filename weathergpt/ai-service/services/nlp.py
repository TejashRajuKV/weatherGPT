"""
WeatherGPT Rule-based NLP Engine  (v2)
======================================
No external AI/LLM required. Standard library only.

What changed compared with v1
-----------------------------
* Time is honoured by EVERY intent (umbrella tomorrow, humidity next 3 days ...).
* Weekdays, months, "in N days", "next N days", "last N years", "tonight" parsed.
* Multi-location extraction ("Delhi and Mumbai", "from Delhi to Mumbai").
* Lowercase / unknown place names ("weather in ooty") and typo-tolerant matching.
* Language detection + Hindi / Hinglish / Marathi / Bengali / Tamil / Telugu /
  Kannada / Malayalam / Gujarati / Punjabi / Odia keywords and city aliases.
* New intents: rain, thanks, bye, fallback. Greetings no longer swallow questions.
* Advisory answers for spraying / sowing / irrigation / harvesting / fishing /
  flying / flood risk instead of a generic current-weather dump.
* Conversation context for follow-ups ("and tomorrow?", "what about Pune?").
* Wind labels, heat-index, alerts text and "feels like None" bugs fixed.

Optional trained model
----------------------
If models/intent_model.joblib exists (made by train_intent.py) it is used as a backup
whenever the rules find no intent. parse_query() reports where the intent came from in
"intent_source": rules | model | context | default | none.

Public API (backwards compatible)
---------------------------------
    parse_query(query, context=None) -> dict
    generate_response(intent, parsed, weather_data) -> str
    update_context(context, parsed) -> dict          (new, optional)

parse_query() now also returns a "fetch" list telling your backend which data
it should load: any of "current", "forecast", "alerts", "climate".

NOTE: Keyword lists and city aliases for non-English languages are starter data
and should be reviewed by a native speaker. Weather replies are still written in
English; greetings / fallback / clarification messages are localised for
English, Hindi, Hinglish and Marathi (see I18N).
"""
import os
import re
import sys
import random
import unicodedata
import difflib
from datetime import date, timedelta
from typing import Optional

try:  # optional feature engines (activity scoring, crop calendar, explainer)
    from services import scoring as _scoring
    from services import crops as _crops
    from services import explainer as _explainer
except Exception:  # pragma: no cover - keeps nlp usable standalone
    try:
        import scoring as _scoring
        import crops as _crops
        import explainer as _explainer
    except Exception:
        _scoring = _crops = _explainer = None

# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────
# Unit of "wind_max" in your forecast data. Open-Meteo returns km/h by default.
# Set to "ms" if your data service converts it to metres per second.
WIND_MAX_UNIT = "kmh"

# Optional trained intent model (see train_intent.py). It is only consulted when the
# rules find no intent. If models/intent_model.joblib or scikit-learn is missing, nlp.py
# simply keeps working with rules only.
ML_CONFIDENCE_THRESHOLD = 0.55     # below this the model's answer is ignored
_ML = {"tried": False, "clf": None}


def _ml_predict(text: str, places=None):
    """Returns [(intent, probability), ...] or None when no model is available."""
    if not _ML["tried"]:
        _ML["tried"] = True
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            path = os.environ.get("WEATHERGPT_INTENT_MODEL") or os.path.join(here, "models", "intent_model.joblib")
            if os.path.exists(path):
                if here not in sys.path:
                    sys.path.insert(0, here)
                from train_intent import IntentClassifier
                _ML["clf"] = IntentClassifier(path)
        except Exception:
            _ML["clf"] = None
    if _ML["clf"] is None:
        return None
    try:
        return _ML["clf"].predict(text, top_k=3, known_places=places)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# WMO weather code descriptions
# ─────────────────────────────────────────────────────────────────────────────
WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "moderate snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "moderate showers", 82: "violent showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm",
}

WMO_EMOJI = {
    0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫",
    51: "🌦", 53: "🌧", 55: "🌧", 56: "🌧", 57: "🌧",
    61: "🌧", 63: "🌧", 65: "🌧", 66: "🌧", 67: "🌧",
    71: "🌨", 73: "🌨", 75: "❄️", 77: "🌨", 85: "🌨", 86: "❄️",
    80: "🌦", 81: "🌧", 82: "⛈",
    95: "⛈", 96: "⛈", 99: "⛈",
}

# ─────────────────────────────────────────────────────────────────────────────
# Localised short messages (greeting, help, fallback, clarification ...)
# Languages without an entry fall back to English.
# ─────────────────────────────────────────────────────────────────────────────
I18N = {
    "en": {
        "greeting": ["Hello! 👋 Ask me about the weather anywhere in India.",
                     "Hi there! 🌦 What weather info do you need today?",
                     "Hey! I'm WeatherGPT. Ask me about rain, forecast, alerts — anything weather!",
                     "Namaste! 🙏 How can I help with your weather query?"],
        "ask_location": "Which place do you want the weather for? (For example: Pune, Delhi, Chennai)",
        "thanks": "You're welcome! 😊 Ask me anything else about the weather.",
        "bye": "Goodbye! Stay safe and keep an eye on the sky. 🌤",
        "fallback": ("I didn't quite understand that. 🤔 I can help with weather, forecasts, "
                     "alerts and advice.\n\nTry asking:\n"
                     "  • Will it rain in Mumbai tomorrow?\n"
                     "  • What is the temperature in Delhi?\n"
                     "  • Should I spray my crops in Nashik today?\n"
                     "  • Any weather alerts for Odisha?"),
    },
    "hi": {
        "greeting": ["नमस्ते! 🙏 भारत में कहीं का भी मौसम पूछिए।",
                     "नमस्कार! 🌦 आज आपको किस जगह का मौसम जानना है?"],
        "ask_location": "आप किस जगह का मौसम जानना चाहते हैं? (जैसे: पुणे, दिल्ली, चेन्नई)",
        "thanks": "आपका स्वागत है! 😊 मौसम के बारे में कुछ और पूछना हो तो बताइए।",
        "bye": "अलविदा! सुरक्षित रहिए। 🌤",
        "fallback": ("मैं आपकी बात ठीक से समझ नहीं पाया। 🤔 मैं मौसम, पूर्वानुमान और चेतावनी में मदद कर सकता हूँ।\n\n"
                     "ऐसे पूछ सकते हैं:\n"
                     "  • कल मुंबई में बारिश होगी क्या?\n"
                     "  • दिल्ली का तापमान कितना है?\n"
                     "  • आज पुणे का मौसम कैसा है?"),
    },
    "hi-Latn": {
        "greeting": ["Namaste! 🙏 India mein kahin ka bhi mausam poochiye.",
                     "Hello! 🌦 Aaj kis jagah ka mausam jaanna hai?"],
        "ask_location": "Aap kis jagah ka mausam jaanna chahte hain? (jaise: Pune, Delhi, Chennai)",
        "thanks": "Aapka swagat hai! 😊 Mausam ke baare mein aur kuch poochna ho to bataiye.",
        "bye": "Alvida! Surakshit rahiye. 🌤",
        "fallback": ("Mujhe aapki baat samajh nahi aayi. 🤔 Main mausam, forecast aur alerts mein madad kar sakta hoon.\n\n"
                     "Aise poochiye:\n"
                     "  • Kal Mumbai mein barish hogi kya?\n"
                     "  • Delhi ka temperature kitna hai?\n"
                     "  • Aaj Pune ka mausam kaisa hai?"),
    },
    "mr": {
        "greeting": ["नमस्कार! 🙏 भारतातील कोणत्याही ठिकाणचे हवामान विचारा."],
        "ask_location": "तुम्हाला कोणत्या ठिकाणचे हवामान हवे आहे? (उदा. पुणे, मुंबई, नाशिक)",
        "thanks": "आपले स्वागत आहे! 😊 हवामानाबद्दल आणखी काही विचारायचे असल्यास सांगा.",
        "bye": "निरोप! सुरक्षित राहा. 🌤",
        "fallback": ("मला तुमचे बोलणे नीट समजले नाही. 🤔 मी हवामान, अंदाज आणि इशारे देण्यास मदत करू शकतो.\n\n"
                     "असे विचारा:\n"
                     "  • उद्या पुण्यात पाऊस पडेल का?\n"
                     "  • आज मुंबईचे हवामान कसे आहे?"),
    },
}
I18N["mr-Latn"] = I18N["hi-Latn"]


def _msg(key: str, lang: str):
    table = I18N.get(lang) or I18N.get(lang.split("-")[0]) or I18N["en"]
    return table.get(key) or I18N["en"][key]


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation & language detection
# ─────────────────────────────────────────────────────────────────────────────
_B = r"(?<![\w\u0900-\u0DFF])"   # "word start" that also works for Indic scripts
_E = r"(?![\w\u0900-\u0DFF])"    # "word end"   that also works for Indic scripts

TYPO_FIXES = {
    "tomorow": "tomorrow", "tommorow": "tomorrow", "tommorrow": "tomorrow",
    "tmrw": "tomorrow", "tmr": "tomorrow", "tomo": "tomorrow",
    "wether": "weather", "wheather": "weather", "weahter": "weather",
    "raning": "raining", "rainning": "raining", "temprature": "temperature",
    "temperture": "temperature", "tempreture": "temperature", "forcast": "forecast",
    "forecas": "forecast", "umbrela": "umbrella", "humidty": "humidity",
    "thunderstrom": "thunderstorm", "cylone": "cyclone", "cyclon": "cyclone",
}
_TYPO_RE = re.compile(r"\b(" + "|".join(map(re.escape, TYPO_FIXES)) + r")\b")


def normalize(text: str) -> str:
    """Lower-case, NFC, Indic digits -> ASCII, collapse repeated letters, fix typos."""
    t = unicodedata.normalize("NFC", text or "").lower().strip()
    t = "".join(
        str(unicodedata.decimal(c)) if (not c.isascii() and unicodedata.category(c) == "Nd") else c
        for c in t
    )
    t = re.sub(r"[’‘`´]", "'", t)
    t = re.sub(r"([a-z])\1{2,}", r"\1", t)          # baaarish -> barish
    t = _TYPO_RE.sub(lambda m: TYPO_FIXES[m.group(1)], t)
    return re.sub(r"\s+", " ", t)


_SCRIPTS = [
    ("hi", 0x0900, 0x097F),   # Devanagari (Hindi / Marathi – refined below)
    ("bn", 0x0980, 0x09FF),
    ("pa", 0x0A00, 0x0A7F),
    ("gu", 0x0A80, 0x0AFF),
    ("or", 0x0B00, 0x0B7F),
    ("ta", 0x0B80, 0x0BFF),
    ("te", 0x0C00, 0x0C7F),
    ("kn", 0x0C80, 0x0CFF),
    ("ml", 0x0D00, 0x0D7F),
]
HINGLISH_MARKERS = {
    "kal", "aaj", "parso", "mein", "mai", "hai", "hain", "hogi", "hoga", "hoge", "kya",
    "barish", "baarish", "barsat", "mausam", "kaisa", "kaisi", "kaise", "garmi", "sardi",
    "thand", "hawa", "batao", "bataiye", "kitna", "kitni", "raha", "rahi", "rahega",
    "nahi", "kab", "chahiye", "dhoop", "bahut", "abhi", "kahan", "mujhe", "aapka", "ka", "ki", "ke",
    "namaste", "dhanyavad", "dhanyawad", "shukriya", "alvida", "kaun", "sunao", "chalo",
}
_HINGLISH_STRONG = HINGLISH_MARKERS - {"ka", "ki", "ke", "mai", "hai", "kal"}
MARATHI_LATIN = {"udya", "paus", "aahe", "ahe", "yeil", "kuthe", "havaman", "padel", "kasa", "kasa", "ka", "aaj", "nahi"}
MARATHI_DEVANAGARI = ["आहे", "काय", "मध्ये", "उद्या", "पाऊस", "होईल", "पडेल", "वारा", "थंडी", "हवामान", "आज चे", "कसे", "आणि"]


def detect_language(text: str) -> str:
    """Returns: en, hi, hi-Latn, mr, mr-Latn, bn, pa, gu, or, ta, te, kn, ml."""
    counts = {}
    for ch in text or "":
        cp = ord(ch)
        for code, lo, hi_ in _SCRIPTS:
            if lo <= cp <= hi_:
                counts[code] = counts.get(code, 0) + 1
                break
    if counts:
        code = max(counts, key=counts.get)
        if code == "hi" and any(m in text for m in MARATHI_DEVANAGARI):
            return "mr"
        return code
    words = set(re.findall(r"[a-z]+", normalize(text)))
    hi_hits = len(words & _HINGLISH_STRONG)
    mr_hits = len(words & (MARATHI_LATIN - {"ka", "aaj", "nahi"}))
    if mr_hits and mr_hits >= hi_hits:
        return "mr-Latn"
    if hi_hits or len(words & HINGLISH_MARKERS) >= 2:
        return "hi-Latn"
    return "en"


# ─────────────────────────────────────────────────────────────────────────────
# Locations
# ─────────────────────────────────────────────────────────────────────────────
KNOWN_LOCATIONS = [
    "mumbai", "delhi", "new delhi", "bangalore", "bengaluru", "hyderabad", "chennai",
    "kolkata", "calcutta", "pune", "ahmedabad", "jaipur", "surat", "lucknow", "kanpur",
    "nagpur", "patna", "indore", "thane", "bhopal", "visakhapatnam", "vizag", "pimpri",
    "vadodara", "baroda", "ghaziabad", "ludhiana", "coimbatore", "agra", "madurai",
    "nashik", "faridabad", "meerut", "rajkot", "varanasi", "benaras", "srinagar",
    "amritsar", "allahabad", "prayagraj", "ranchi", "howrah", "goa", "panaji", "margao",
    "kochi", "cochin", "thiruvananthapuram", "trivandrum", "chandigarh", "dehradun",
    "shimla", "bhubaneswar", "raipur", "gandhinagar", "guwahati", "imphal", "shillong",
    "aizawl", "kohima", "agartala", "itanagar", "gangtok", "ujjain", "gwalior",
    "jabalpur", "bilaspur", "rourkela", "cuttack", "siliguri", "asansol", "durgapur",
    "tirupati", "vijayawada", "warangal", "nellore", "guntur", "kakinada", "rajahmundry",
    "mysore", "mysuru", "mangalore", "mangaluru", "hubli", "dharwad", "belgaum", "belagavi",
    "tiruchirappalli", "trichy", "salem", "tirunelveli", "vellore", "erode", "tiruppur",
    "thanjavur", "dindigul", "kanchipuram", "pondicherry", "puducherry",
    "kozhikode", "calicut", "thrissur", "palakkad", "kollam", "alappuzha",
    "jodhpur", "bikaner", "udaipur", "kota", "ajmer", "bharatpur", "alwar",
    "aurangabad", "solapur", "kolhapur", "sangli", "nanded", "latur", "dhule", "akola",
    "amravati", "chandrapur", "jalgaon", "ahmednagar",
    "gorakhpur", "aligarh", "bareilly", "moradabad", "saharanpur", "firozabad",
    "mathura", "etawah", "jhansi", "muzaffarpur", "bhagalpur", "gaya", "darbhanga",
    "bokaro", "dhanbad", "hazaribagh", "jamshedpur", "deoghar",
    "manali", "dharamshala", "kullu", "mandi", "solan",
    "haridwar", "rishikesh", "roorkee", "haldwani", "nainital", "almora",
    "jammu", "leh", "kargil", "kathua", "udhampur",
    # extras
    "ooty", "udhagamandalam", "kodaikanal", "munnar", "shirdi", "darjeeling", "pahalgam",
    "port blair", "kavaratti", "daman", "silvassa", "ratnagiri", "alibag", "lonavala",
    "mahabaleshwar", "satara", "panvel", "navi mumbai", "noida", "gurgaon", "gurugram",
    "jamnagar", "bhavnagar", "junagadh", "bhuj", "digha", "puri", "konark", "paradip",
    "balasore", "berhampur", "sambalpur", "kanyakumari", "rameswaram", "tuticorin",
    "thoothukudi", "karaikal", "mahabalipuram", "hosur", "anantapur", "kurnool",
    "karimnagar", "nizamabad", "khammam", "ramagundam", "bellary", "ballari", "gulbarga",
    "kalaburagi", "udupi", "hassan", "shimoga", "shivamogga", "davangere", "tumkur",
    "bhilai", "korba", "ambala", "panipat", "karnal", "rohtak", "hisar", "sonipat",
]
# Old / alternate / mis-spelt names -> name sent to the weather API
ROMAN_ALIASES = {
    "bombay": "Mumbai", "madras": "Chennai", "poona": "Pune", "banglore": "Bangalore",
    "bengalooru": "Bengaluru", "dilli": "Delhi", "kolkatta": "Kolkata", "hydrabad": "Hyderabad",
    "ahmadabad": "Ahmedabad", "calcutta": "Kolkata", "trivandrum": "Thiruvananthapuram",
    "vizag": "Visakhapatnam", "gurgaon": "Gurugram", "cochin": "Kochi", "baroda": "Vadodara",
    "benaras": "Varanasi", "allahabad": "Prayagraj", "mysore": "Mysuru",
}
# Names written in Indian scripts -> English name  (starter list, please review)
INDIC_ALIASES = {
    # Devanagari (Hindi / Marathi)
    "मुंबई": "Mumbai", "मुम्बई": "Mumbai", "दिल्ली": "Delhi", "पुणे": "Pune", "पुना": "Pune", "पुण्यात": "Pune", "पुण्या": "Pune",
    "चेन्नई": "Chennai", "कोलकाता": "Kolkata", "कलकत्ता": "Kolkata", "बेंगलुरु": "Bengaluru",
    "बंगलौर": "Bangalore", "बेंगळुरू": "Bengaluru", "हैदराबाद": "Hyderabad", "अहमदाबाद": "Ahmedabad",
    "जयपुर": "Jaipur", "लखनऊ": "Lucknow", "नागपुर": "Nagpur", "नागपूर": "Nagpur", "नाशिक": "Nashik",
    "भोपाल": "Bhopal", "पटना": "Patna", "इंदौर": "Indore", "वाराणसी": "Varanasi", "बनारस": "Varanasi",
    "गोवा": "Goa", "सूरत": "Surat", "कानपुर": "Kanpur", "आगरा": "Agra", "चंडीगढ़": "Chandigarh",
    "औरंगाबाद": "Aurangabad", "कोल्हापूर": "Kolhapur", "कोल्हापुर": "Kolhapur", "सोलापूर": "Solapur",
    "शिमला": "Shimla", "मनाली": "Manali", "देहरादून": "Dehradun", "रांची": "Ranchi", "रायपुर": "Raipur",
    "भुवनेश्वर": "Bhubaneswar", "गुवाहाटी": "Guwahati", "श्रीनगर": "Srinagar", "अमृतसर": "Amritsar",
    # Bengali
    "কলকাতা": "Kolkata", "দিল্লি": "Delhi", "মুম্বই": "Mumbai", "চেন্নাই": "Chennai",
    "বেঙ্গালুরু": "Bengaluru", "হায়দ্রাবাদ": "Hyderabad", "শিলিগুড়ি": "Siliguri", "দার্জিলিং": "Darjeeling",
    "গুয়াহাটি": "Guwahati",
    # Tamil
    "சென்னை": "Chennai", "மதுரை": "Madurai", "கோயம்புத்தூர்": "Coimbatore", "திருச்சி": "Trichy",
    "பெங்களூர்": "Bengaluru", "மும்பை": "Mumbai", "டெல்லி": "Delhi", "சேலம்": "Salem",
    "திருநெல்வேலி": "Tirunelveli", "வேலூர்": "Vellore", "ஊட்டி": "Ooty", "கன்னியாகுமரி": "Kanyakumari",
    # Telugu
    "హైదరాబాద్": "Hyderabad", "విశాఖపట్నం": "Visakhapatnam", "విజయవాడ": "Vijayawada",
    "చెన్నై": "Chennai", "బెంగళూరు": "Bengaluru", "ముంబై": "Mumbai", "ఢిల్లీ": "Delhi",
    "తిరుపతి": "Tirupati", "వరంగల్": "Warangal", "గుంటూరు": "Guntur",
    # Kannada
    "ಬೆಂಗಳೂರು": "Bengaluru", "ಮೈಸೂರು": "Mysuru", "ಮಂಗಳೂರು": "Mangaluru", "ಹುಬ್ಬಳ್ಳಿ": "Hubli",
    "ಮುಂಬೈ": "Mumbai", "ದೆಹಲಿ": "Delhi", "ಬೆಳಗಾವಿ": "Belagavi", "ಹೈದರಾಬಾದ್": "Hyderabad",
    # Malayalam
    "കൊച്ചി": "Kochi", "തിരുവനന്തപുരം": "Thiruvananthapuram", "കോഴിക്കോട്": "Kozhikode",
    "തൃശ്ശൂർ": "Thrissur", "ചെന്നൈ": "Chennai", "മുംബൈ": "Mumbai", "ബെംഗളൂരു": "Bengaluru",
    # Gujarati
    "અમદાવાદ": "Ahmedabad", "સુરત": "Surat", "વડોદરા": "Vadodara", "રાજકોટ": "Rajkot",
    "મુંબઈ": "Mumbai", "દિલ્હી": "Delhi", "ગાંધીનગર": "Gandhinagar",
    # Punjabi (Gurmukhi)
    "ਅੰਮ੍ਰਿਤਸਰ": "Amritsar", "ਲੁਧਿਆਣਾ": "Ludhiana", "ਚੰਡੀਗੜ੍ਹ": "Chandigarh", "ਦਿੱਲੀ": "Delhi",
    "ਜਲੰਧਰ": "Jalandhar", "ਪਟਿਆਲਾ": "Patiala",
    # Odia
    "ଭୁବନେଶ୍ୱର": "Bhubaneswar", "କଟକ": "Cuttack", "ପୁରୀ": "Puri", "ଦିଲ୍ଲୀ": "Delhi",
}

_ALL_LATIN_NAMES = sorted(set(KNOWN_LOCATIONS) | set(ROMAN_ALIASES), key=len, reverse=True)
_LOC_RE = re.compile(r"(?<![a-z])(" + "|".join(re.escape(n) for n in _ALL_LATIN_NAMES) + r")(?![a-z])")
_SINGLE_NAMES = [n for n in _ALL_LATIN_NAMES if " " not in n and len(n) >= 5]

# Words that must never be mistaken for a place name
_NOT_PLACES = {
    # time
    "today", "tomorrow", "tonight", "yesterday", "now", "morning", "evening", "afternoon", "night",
    "week", "weekend", "month", "year", "day", "days", "next", "this", "last", "coming", "upcoming",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
    # weather
    "weather", "rain", "raining", "rainy", "rainfall", "snow", "wind", "windy", "fog", "foggy", "hot",
    "cold", "warm", "cool", "sunny", "cloudy", "storm", "thunder", "forecast", "temperature", "humidity",
    "climate", "heat", "heatwave", "cyclone", "flood", "alert", "alerts", "warning", "weather.",
    # filler
    "the", "my", "your", "our", "a", "an", "me", "you", "it", "is", "are", "will", "be", "there", "here",
    "please", "india", "indian", "city", "town", "village", "area", "place", "location", "region",
    "tell", "give", "show", "let", "ask", "send", "get", "know", "check", "need", "want", "what", "how",
    "when", "which", "can", "could", "should", "would", "do", "does", "any", "all", "and", "or", "for",
    "on", "at", "in", "of", "near", "around", "over", "with", "without", "from", "to", "about", "like",
    "and", "kal", "aaj", "parso", "abhi", "mein", "mai", "ka", "ki", "ke", "hai", "hoga", "hogi", "kya",
    "mausam", "barish", "garmi", "sardi", "thand", "hawa", "batao", "bataiye", "udya", "paus",
    "good", "bad", "best", "safe", "right", "sure", "okay", "ok", "yes", "no", "not", "thanks", "thank",
    "hello", "hi", "hey", "outside", "outdoor", "outdoors", "home", "office", "work", "school", "college",
    "sea", "beach", "coast", "farm", "field", "crop", "crops", "flight", "airport", "temp", "umbrella",
    "jacket", "sweater", "run", "walk", "help", "call", "text", "message", "remind", "notify", "inform", "update", "guide", "trip", "wedding", "party", "picnic", "event", "plants", "garden",
}
_PLACE_CUE = (r"(?:in|at|for|near|around|over|of|from|to|within|inside|nearby)")


def _clean_candidate(words):
    out = []
    for w in words:
        if w in _NOT_PLACES or len(w) < 3:
            break
        out.append(w)
        if len(out) == 2:
            break
    return " ".join(out)


def extract_locations(query: str) -> list:
    """All places mentioned, in the order written. Falls back to heuristics for unknown places."""
    q = unicodedata.normalize("NFC", query or "").lower()
    found = []   # (start, end, Name)
    # 1. known Latin names (longest first, non-overlapping)
    for m in _LOC_RE.finditer(q):
        raw = m.group(1)
        found.append((m.start(), m.end(), ROMAN_ALIASES.get(raw, raw.title())))
    # 2. Indic-script names
    for alias, name in sorted(INDIC_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        start = q.find(alias)
        while start != -1:
            end = start + len(alias)
            if not any(s < end and start < e for s, e, _ in found):
                found.append((start, end, name))
            start = q.find(alias, end)
    # 3. typo-tolerant match (e.g. "banglore", "ahmedbad", "hydrabad")
    for m in re.finditer(r"[a-z]{5,}", q):
        s, e = m.span()
        tok = m.group(0)
        if tok in _NOT_PLACES or any(fs < e and s < fe for fs, fe, _ in found):
            continue
        close = difflib.get_close_matches(tok, _SINGLE_NAMES, n=1, cutoff=0.86)
        if close:
            found.append((s, e, ROMAN_ALIASES.get(close[0], close[0].title())))
    # 4. unknown place after a cue word ("weather in ooty", "ooty mein barish")
    if not found:
        for m in re.finditer(r"\b" + _PLACE_CUE + r"\s+([a-z][a-z\-']+(?:\s+[a-z][a-z\-']+){0,2})", q):
            cand = _clean_candidate(m.group(1).split())
            if cand:
                found.append((m.start(1), m.end(1), cand.title()))
                break
    if not found and (set(re.findall(r"[a-z]+", q)) & _HINGLISH_STRONG):
        for m in re.finditer(r"\b([a-z]{3,20})\s+(?:mein|mai|me|ka|ki|ke)\b", q):
            cand = _clean_candidate([m.group(1)])
            if cand:
                found.append((m.start(1), m.end(1), cand.title()))
                break
    # 5. capitalised words in the original text ("Will it rain in Shirdi")
    if not found:
        skip = {w.title() for w in _NOT_PLACES}
        for m in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b", query or ""):
            if m.group(1) not in skip and m.group(1).split()[0] not in skip:
                found.append((m.start(), m.end(), m.group(1)))
                break
    found.sort(key=lambda x: x[0])
    names = []
    for _, _, n in found:
        if n not in names:
            names.append(n)
    return names


def extract_location(query: str) -> Optional[str]:
    """Backwards-compatible: first location mentioned (or None)."""
    locs = extract_locations(query)
    return locs[0] if locs else None


def _wants_gps(q: str) -> bool:
    return bool(re.search(
        r"\bnear me\b|\bmy location\b|\bmy area\b|\bhere\b|\bmy city\b|मेरे (?:यहाँ|यहां|शहर)|मेरी जगह|\bmere (?:yahan|shehar|sheher)\b|\byahan\b|इथे|माझ्या", q))


# ─────────────────────────────────────────────────────────────────────────────
# Time parsing
# ─────────────────────────────────────────────────────────────────────────────
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10, "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
              "panch": 5, "chhe": 6, "saat": 7, "das": 10, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5,
              "पाच": 5, "सात": 7, "दस": 10}
_NUM = r"(\d{1,3}|" + "|".join(sorted(_NUM_WORDS, key=len, reverse=True)) + r")"
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "somvar": 0, "mangalvar": 1, "budhvar": 2, "guruvar": 3, "brihaspatvar": 3, "shukravar": 4,
    "shanivar": 5, "ravivar": 6, "itwar": 6,
    "सोमवार": 0, "मंगलवार": 1, "बुधवार": 2, "गुरुवार": 3, "गुरूवार": 3, "शुक्रवार": 4,
    "शनिवार": 5, "रविवार": 6,
}
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}
_PAST_MARKERS = r"\b(?:thi|tha|the|hui|hua|huyi|hoti|gayi|gaya|beeta|pichhle|pichle|last night|was|were|did)\b|होती|थी|था|हुई|हुआ|पिछले"


def _num(tok: str) -> int:
    return int(tok) if tok.isdigit() else _NUM_WORDS.get(tok, 1)


def parse_time(query: str, today: Optional[date] = None) -> dict:
    """
    Returns {"label": str, "explicit": bool, "n": int|None, "month": int|None}
    label is one of: now, today, tonight, tomorrow, day_after_tomorrow, yesterday, weekend,
    this_week, next_week, next_N_days, in_N_days, date:YYYY-MM-DD, this_month, month:M,
    last_N_days / last_N_months / last_N_years.
    """
    q = normalize(query)
    today = today or date.today()

    def out(label, explicit=True, n=None, month=None):
        return {"label": label, "explicit": explicit, "n": n, "month": month}

    # past ranges -> climate
    m = re.search(r"\b(?:last|past|previous)\s+" + _NUM + r"?\s*(year|years|month|months|day|days|decade)\b", q)
    if m:
        n = _num(m.group(1)) if m.group(1) else 1
        unit = m.group(2)
        unit = "years" if unit.startswith("year") else "months" if unit.startswith("month") else "days"
        if m.group(2) == "decade":
            n, unit = 10, "years"
        return out(f"last_{n}_{unit}", n=n)
    m = re.search(r"(?:पिछले|पिछली|गेल्या|கடந்த)\s*(\d+)\s*(साल|वर्ष|वर्षां|वर्षे|ஆண்டு)", q)
    if m:
        return out(f"last_{int(m.group(1))}_years", n=int(m.group(1)))
    m = re.search(r"\b(?:pichhle|pichle|last|pichhla)\s*(\d+)\s*(?:saal|sal|varsh)\b", q)
    if m:
        return out(f"last_{int(m.group(1))}_years", n=int(m.group(1)))

    if re.search(r"\byesterday\b|\bbeeta hua kal\b", q) or (
            re.search(_B + r"(?:kal|कल)" + _E, q) and re.search(_PAST_MARKERS, q)):
        return out("yesterday")
    if re.search(r"day after tomorrow|day after$|\bparso\b|\bparson\b|परसों|परसो|परवा|ఎల్లుండి|நாளை மறுநாள்|ನಾಡಿದ್ದು", q):
        return out("day_after_tomorrow")
    if re.search(r"\btonight\b|\bis raat\b|\baaj raat\b|आज रात|आज रात्री|இன்று இரவு", q):
        return out("tonight")
    if re.search(r"\btomorrow\b|" + _B + r"kal" + _E + r"|\budya\b|" + _B + r"कल" + _E +
                 r"|उद्या|நாளை|రేపు|ನಾಳೆ|നാളെ|আগামীকাল|" + _B + r"কাল" + _E + r"|આવતીકાલે|કાલે|ਕੱਲ੍ਹ|ਕਲ|ଆସନ୍ତାକାଲି|\bnale\b|\bnaale\b|\bnalai\b|\brepu\b|\bnaaLe\b", q):
        return out("tomorrow")
    if re.search(r"\bweekend\b|saturday and sunday|सप्ताहांत|वीकेंड|शनिवार[- ]रविवार|weekend", q):
        return out("weekend")
    if re.search(r"\bnext week\b|agle hafte|agle week|अगले हफ्ते|अगले सप्ताह|पुढच्या आठवड्यात|पुढील आठवड्यात", q):
        return out("next_week")
    if re.search(r"\bthis week\b|\bis hafte\b|इस हफ्ते|इस सप्ताह|या आठवड्यात|ह्या आठवड्यात", q):
        return out("this_week")
    m = (re.search(r"\bnext\s+" + _NUM + r"\s*[- ]?days?\b", q)
         or re.search(r"\b" + _NUM + r"\s*[- ]?days?\s+(?:forecast|outlook|weather)\b", q)
         or re.search(r"\bfor\s+" + _NUM + r"\s*days?\b", q)
         or re.search(r"(?:agle|अगले|पुढील|पुढच्या)\s*" + _NUM + r"\s*(?:din|दिन|दिवस|दिवसांत)", q))
    if m:
        n = max(1, min(_num(m.group(1)), 16))
        return out(f"next_{n}_days", n=n)
    m = re.search(r"\bin\s+" + _NUM + r"\s*days?\b", q)
    if m:
        n = max(1, min(_num(m.group(1)), 16))
        return out(f"in_{n}_days", n=n)
    if re.search(r"\b(?:next|coming|upcoming)\s+(?:few\s+)?days\b|\bnext few days\b|\bcoming days\b|aane wale din|आने वाले दिन", q):
        return out("next_5_days", n=5)
    # weekday names -> concrete date
    for name, idx in sorted(_WEEKDAYS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b" if name.isascii() else re.escape(name), q):
            ahead = (idx - today.weekday()) % 7
            if re.search(r"\bnext\s+" + re.escape(name), q) and ahead < 7:
                ahead = ahead + 7 if ahead == 0 else ahead
            if ahead == 0:
                return out("today")
            return out(f"date:{(today + timedelta(days=ahead)).isoformat()}")
    if re.search(r"\bthis month\b|इस महीने|या महिन्यात", q):
        return out("this_month")
    m = re.search(r"\b(?:in|during|for|of)\s+(" + "|".join(_MONTHS) + r")\b", q) or \
        re.search(r"\b(" + "|".join(k for k in _MONTHS if len(k) > 3) + r")\b", q)
    if m:
        mo = _MONTHS[m.group(1)]
        return out(f"month:{mo}", month=mo)
    if re.search(r"\bright now\b|\bthis moment\b|\bat the moment\b|\bcurrently\b|\bnow\b|\babhi\b|अभी|आत्ता|இப்போது|ఇప్పుడు|ಈಗ|ഇപ്പോൾ|এখন|હમણાં|ਹੁਣ|ଏବେ", q):
        return out("now")
    if re.search(r"\btoday\b|\baaj\b|" + _B + r"आज" + _E + r"|இன்று|ఈరోజు|ఇవాళ్|ఇవాళ|ಇಂದು|ഇന്ന്|" + _B + r"আজ" + _E + r"|આજે|ਅੱਜ|ଆଜି", q):
        return out("today")
    return out("today", explicit=False)


_MORNING_RE = r"\bmorning\b|\bsubah\b|सुबह|सकाळ| सकाळी|பாலைய|ఉదయం|ಬೆಳಗ್ಗೆ|രാവിലെ|સવારે|ਸਵੇਰ|ସକାଳ|\\bfajr\\b"
_AFTERNOON_RE = r"\bafternoon\b|\bdopahar\b|दोपहर|दुपार|மதியம்|మధ్యాహ్నం|ಮಧ್ಯಾಹ್ನ|ഉച്ചയ്ക്ക്|બપોરે|ਦੁਪਹਿਰ|ମଧ୍ୟାହ୍ନ"
_EVENING_RE = r"\bevening\b|\bshaam\b|\bsandhya\b|शाम|सांज|संध्या| evening|సాయంత్రం|சாயந்திரம்|ಸಂಜೆ|വൈകുന്നേരം|સાંજ|ਸ਼ਾਮ|ସନ୍ଧାନ"
_NIGHT_RE = r"\bat night\b|\bonight\b|\broz raat\b|रात|रात्री|இரவு|రాత్రి|ರಾತ್ರಿ|രാത്രി|રાત|ਰਾਤ|ରାତି"


def detect_tod(query: str) -> Optional[str]:
    q = normalize(query)
    if re.search(_MORNING_RE, q):   return "morning"
    if re.search(_AFTERNOON_RE, q): return "afternoon"
    if re.search(_EVENING_RE, q):   return "evening"
    if re.search(_NIGHT_RE, q):     return "night"
    return None


_TOD_HOURS = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22), "night": (22, 5)}


def tod_window(tod: Optional[str]):
    return _TOD_HOURS.get(tod) if tod else None


def extract_time_range(query: str) -> str:
    """Backwards-compatible: just the label."""
    return parse_time(query)["label"]


# ─────────────────────────────────────────────────────────────────────────────
# Intent rules (ordered — most specific first). Patterns are matched on the
# normalised text. Non-English keywords sit in the same lists.
# ─────────────────────────────────────────────────────────────────────────────
INTENT_RULES = [
    ("explain", [r"\bexplain\b", r"what does .* mean", r"what .*\bmean\b", r"kya matlab|क्या मतलब|म्हणजे काय|என்ன அர்த்தம்|ఏమంటే",
                 r"means? what|matlab kya|what is meant"]),
    ("crop_calendar", [r"\bcrop\b", r"\bcrops\b", r"wheat|gehu|गेहूं", r"tomato|tamatar|टमाटर", r"cotton|kapas|कपास",
                        r"onion|pyaz|कांदा", r"soybean|soya", r"sugarcane|ganna|ऊस",
                        r"flowering stage|grain filling|tillering|fruit set|boll|pod fill|nursery|transplant",
                        r"frost risk|any frost", r"crop stage|फसल|पीक|पिक|పంట|பயிர்"],),
    ("health_index", [r"health index|comfort index|humidex|heat index", r"air quality|\baqi\b|pollution|प्रदूषण|वायू गुणवत्ता",
                       r"asthma|allergy|allergies|pollen|shwas|दम|एलर्जी", r"dehydration|heat stress|hydration|water intake",
                       r"outdoor workout safe|air.*breath"]),
    ("compare", [r"\bcompar(?:e|ison)\b", r"\bvs\b", r"versus", r"hotter than|colder than|wetter than|drier than|cooler than",
                  r"more rain|less rain|higher temp", r"than last (?:year|month|october|november|week)", r"तुलना|तुलना"],),
    ("travel", [r"\b(?:from)\b.*\b(?:to)\b.*(weather|rain|fog|drive|travel|commute)", r"route weather",
                r" commute ", r"driving to", r"trip to", r"travel to", r"departure", r"best time to (?:leave|start|drive|travel|commute)",
                r"traffic.*(rain|weather)", r"highway.*(rain|fog|weather)", r"सफर|प्रवास|मुक्काम|ప్రయాణ|பயண"],),
    ("activity_plan", [r"(?:can i|should i|is it (?:ok|okay|good|fine|safe)(?:ly)? to|good time to|best time to|worth)\b.{0,30}"
                       r"(cycling|cycle|run|jog|walk|trek|hike|camp|picnic|swim|play|match|event|wedding|party|"
                       r"dry clothes|laundry|wash|spray|sow|harvest|fish|solar|photograph|kite|paragliding|marathon|cricket|football)",
                       r"(?:go cycling|dry clothes|best time.*dry|time to wash)",
                       r"सायकल|सायकलिंग|कपडे सुकव|चालण्या|जॉग"],),
    ("alerts_personal", [r"alert me|notify me|warn me|send me (?:an )?alert|my alert|mujhe bata(?:na|o)|मुझे बताना|मला सांगा|सूचित करा|सूचित करो",
                          r"if wind exceeds|if temp(?:erature)? (?:crosses|above|goes above)|if rain between|when .* (?:exceeds|crosses)",
                          r"alert if|notify if|warn if|remind me if"],),
    ("uv_index", [r"\buv\b", r"uv index", r"ultraviolet", r"sunburn", r"sun.*safe", r"सनबर्न|धूप.*तेज"]),
    ("humidity", [r"\bhumid", r"muggy", r"sticky", r"moisture", r"\bdamp\b", r"\bsweat(?:y|ing)?\b", r"नमी|उमस|आर्द्रता|दमट|ஈரப்பதம்|తేమ|ಆರ್ದ್ರತೆ|ഈർപ്പം|ભેજ|ਨਮੀ|ଆର୍ଦ୍ରତା"]),
    ("feels_like", [r"feel.*like", r"feels? (?:hotter|colder|warmer|cooler)", r"(?:hotter|colder|warmer|cooler).*\bfeel\b", r"कितनी (?:गर्मी|ठंड) लगेगी", r"feels.*outside", r"how.*\bhot\b", r"how.*\bcold\b",
                    r"heat.*index", r"apparent.*temp"]),
    ("fog", [r"\bfog\b", r"foggy", r"\bmist\b", r"misty", r"visibility", r"\bkohra\b|कोहरा|धुंध|धुके|धुकं|কুয়াশা|மூடுபனி|పొగమంచు|ಮಂಜು|മൂടൽമഞ്ഞ്|ધુમ્મસ|ਧੁੰਦ|କୁହୁଡ଼ି"]),
    ("snow", [r"\bsnow", r"\bbarf(?:bari)?\b", r"\bole\b", r"blizzard", r"\bice\b", r"\bfrost\b", r"\bhail", r"बर्फ|हिमवर्षा|बर्फबारी|ओले|বরফ|பனி|మంచు|ಹಿಮ|മഞ്ഞ്|બરફ"]),
    ("heatwave", [r"heat ?wave", r"heat (?:alert|warning|advisory)", r"heat.*stroke", r"too hot", r"extreme.*heat", r"लू चल|लू लग|उष्णतेची लाट|उष्ण लहर|हीटवेव|तीव्र गर्मी|\bloo chal"]),
    ("cold_wave", [r"cold ?wave", r"cold (?:alert|warning|advisory)", r"\bfreez(?:e|ing)\b", r"cold.*spell", r"too cold", r"chilly", r"freezing cold", r"शीतलहर|शीत लहर|थंडीची लाट|कड़ाके की ठंड|\bsheet ?lahar\b"]),
    ("alerts", [r"(?:warning|alert|चेतावनी|इशारा|\\bchetavani\\b).*(?:storm|cyclone|तूफान|वादळ|toofan)",
                r"(?:storm|cyclone|तूफान|वादळ|toofan).*(?:warning|alert|चेतावनी|इशारा|chetavani)"]),
    ("thunder", [r"thunder", r"lightning", r"\bstorm", r"बादल गरज|गरजेंगे|\bbadal garaj|\btoofan\b|\btufan\b|\bbijli\b|तूफान|तूफ़ान|वादळ|बिजली|वीज|মেঘ গর্জন|বজ্র|இடி|மின்னல்|పిడుగు|ಸಿಡಿಲು|ഇടിമിന്നൽ|વીજળી|ਬਿਜਲੀ|ବଜ୍ର"]),
    ("wind", [r"\bwind", r"\bgale\b", r"\bbreeze\b", r"\bgust", r"\bhawa\b|\btez hawa\b|हवा(?![\u0900-\u097F])|वारा|वाऱ्याचा|বাতাস|காற்று|గాలి|ಗಾಳಿ|കാറ്റ്|પવન|ਹਵਾ|ପବନ"]),
    ("umbrella", [r"umbrella", r"\bchh?ata\b|\bchh?atri\b|छाता|छत्री|குடை|గొడుగు|ಛತ್ರಿ|കുട|છત્રી|ਛੱਤਰੀ|ছাতা|ଛତା"]),
    ("advisory", [r"chance.*flood|flooding", r"should i (?:spray|sow|harvest|irrigat)", r"water.*(?:crop|field|farm)", r"spray", r"\bsowing\b|\bsow\b",
                  r"\bharvest", r"irrigat", r"\bpesticide", r"safe.*fish", r"go.*\bsea\b", r"go.*fishing",
                  r"\bfishing\b", r"flight.*safe", r"safe.*flight", r"safe.*\bfly\b", r"\bfly\b", r"\bflying\b",
                  r"\bflight", r"waterlog", r"flood.*risk", r"risk.*flood",
                  r"छिड़काव|बुवाई|सिंचाई|कटाई|फसल|मछली पकड़|फवारणी|पेरणी|सिंचन|\bkheti\b|\bfasal\b"]),
    ("outdoor", [r"picnic", r"wedding", r"\bevent\b", r"\bparty\b", r"\bouting\b",
                 r"\btrip\b", r"\bhike\b", r"\btrek", r"camping",
                 r"play outside", r"kids.*outside", r"good.*weather.*for", r"match\b.*(?:play|today)", r"शादी|पिकनिक|सहल|लग्न"]),
    ("jogging", [r"\bjog", r"\bdaud|दौड़|टहलने|chalne ke liye|सैर", r"\brun\b", r"running", r"exercise.*outside",
                 r"morning.*walk", r"cycling", r"walk.*outside", r"best time.*exercise", r"\bgym outdoors\b"]),
    ("commute", [r"commut", r"\btravel", r"\bdrive\b", r"\bdriving\b", r"\broad\b",
                 r"going.*office", r"on the way", r"\bjourney\b", r"safar|सफर|यात्रा|प्रवास"]),
    ("clothing", [r"\bwear\b", r"\bcloth", r"\bdress\b", r"\bjacket\b", r"\bsweater\b",
                  r"what.*wear", r"should.*wear", r"कपड़े|स्वेटर|जैकेट"]),
    ("plants", [r"water.*plant", r"\bplants?\b", r"\bgarden", r"पौधे|बगीचा|बाग"]),
    ("alerts", [r"\balerts?\b", r"warning\b", r"\bcyclone\b", r"\bflood", r"disaster", r"severe.*weather",
                r"emergency", r"red alert", r"orange alert", r"yellow alert", r"\btsunami\b",
                r"चेतावनी|चक्रवात|बाढ़|बाढ|इशारा|अलर्ट|चेतावणी|\bchetavani\b|\bchakravat\b|\bbaadh\b|সতর্কতা|எச்சரிக்கை|హెచ్చరిక|ಎಚ್ಚರಿಕೆ|മുന്നറിയിപ്പ്|ચેતવણી|ਚੇਤਾਵਨੀ|ସତର୍କ"]),
    ("climate", [r"histor", r"(?:last|past) \d+ (?:year|month)", r"\btrend", r"anomal", r"compare.*year",
                 r"annual", r"\bclimate\b", r"average.*year", r"long.*term", r"normals?\b",
                 r"\bavg\b.*(?:year|month)", r"itihas|इतिहास|पिछले.*साल|गेल्या.*वर्ष|\bpichhle\b.*\bsaal\b"]),
    ("rain", [r"\brain", r"\bshower", r"drizzle", r"monsoon", r"downpour", r"precipitation", r"chance of rain",
              r"\bbarish\b|\bbarsat\b|\bbarsaat\b|\bpaus\b|\bmazhai\b|\bvarsham\b|\bvrishti\b|\bbristi\b|\bmohalu\b|\bpaani gir|बारिश|बरसात|पाऊस|पावसाची|मानसून|मान्सून|বৃষ্টি|மழை|వర్షం|వాన\b|ಮಳೆ|മഴ|વરસાદ|ਮੀਂਹ|ਬਾਰਿਸ਼|ବର୍ଷା"]),
    ("forecast", [r"forecast", r"आने वाले दिन|aane wale din|agle (?:kuch )?din", r"next \d+ day", r"this week",
                  r"next week", r"weekend", r"will it be", r"going to be",
                  r"next few days", r"coming days", r"upcoming", r"in \d+ day",
                  r"purvanuman|पूर्वानुमान|अनुमान|अंदाज|\bandaaz\b|\bandaz\b|পূর্বাভাস|முன்னறிவிப்பு|సూచన|ಮುನ್ಸೂಚನೆ|പ്രവചനം|આગાહી|ਪੇਸ਼ਗੋਈ|ପୂର୍ବାନୁମାନ"]),
    ("current", [r"current", r"right now", r"at the moment", r"today.*weather",
                 r"weather.*today", r"temperature", r"\btemp\b", r"weather", r"how.*weather", r"what.*weather",
                 r"is it hot", r"is it cold", r"\bhot\b", r"\bcold\b",
                 r"\bmausam\b|\btaapman\b|\btemperature\b|\bgarmi\b|\bsardi\b|\bthand\b|मौसम|तापमान|गर्मी|सर्दी|ठंड|थंडी|हवामान|तापमान|আবহাওয়া|তাপমাত্রা|வானிலை|வெப்பநிலை|వాతావరణం|ఉష్ణోగ్రత|ಹವಾಮಾನ|ತಾಪಮಾನ|കാലാവസ്ഥ|താപനില|હવામાન|તાપમાન|ਮੌਸਮ|ਤਾਪਮਾਨ|ପାଣିପାଗ|ତାପମାତ୍ରା"]),
]

SOCIAL_RULES = [
    ("thanks", [r"\bthanks?\b", r"thank you", r"\bthx\b", r"\bdhanyavaad?\b", r"\bdhanyawad\b", r"\bshukriya\b",
                r"धन्यवाद|शुक्रिया|आभार|நன்றி|ధన్యవాదాలు|ಧನ್ಯವಾದ|നന്ദി|ধন্যবাদ|આભાર|ਧੰਨਵਾਦ|ଧନ୍ୟବାଦ"]),
    ("bye", [r"\bbye\b", r"goodbye", r"see you", r"\balvida\b", r"\btata\b", r"\bgood night\b",
             r"अलविदा|फिर मिलेंगे|निरोप|पुन्हा भेटू"]),
    ("greeting", [r"^(?:hi+|hello|hey|namaste|namaskar|helo|yo)\b", r"good (?:morning|evening|afternoon)",
                  r"what can you (?:do|help)", r"how (?:do you work|are you)", r"\bwho are you\b",
                  r"\bwhat are you\b", r"\bhelp\b", r"^नमस्ते|^नमस्कार|^वणक्कम்|^வணக்கம்|^నమస్కారం|^ನಮಸ್ಕಾರ|^നമസ്കാരം|^নমস্কার|^ਸਤ ਸ੍ਰੀ ਅਕਾਲ|^કેમ છો|^ନମସ୍କାର"]),
]

_NEEDS_NO_LOCATION = {"greeting", "thanks", "bye", "fallback"}

DOMAIN_RULES = [
    ("agriculture", [r"crop", r"farm", r"\bsow", r"irrigat", r"pesticide", r"spray",
                     r"harvest", r"\bfield\b", r"kisan", r"cotton", r"wheat",
                     r"\brice\b", r"paddy", r"sugarcane", r"maize", r"\bsoybean", r"\bfasal\b", r"\bkheti\b",
                     r"किसान|फसल|खेती|खेत|शेती|पीक|छिड़काव|बुवाई|सिंचाई|पेरणी"]),
    ("aviation", [r"flight", r"pilot", r"aircraft", r"airport", r"aviation",
                  r"\bfly\b", r"\bflying\b", r"airspace", r"turbulence", r"\bmetar\b", r"\btaf\b", r"उड़ान|विमान|हवाई अड्डा"]),
    ("marine", [r"\bfish", r"\bsea\b", r"ocean", r"\bwaves?\b", r"coast", r"\bboat",
                r"vessel", r"sailor", r"trawler", r"marine", r"मछली|समुद्र|सागर|मच्छीमार|समुद्रात"]),
    ("urban", [r"\bcity\b", r"waterlog", r"\bdrain", r"\bward\b",
               r"commut", r"flood.*city", r"urban", r"\btraffic\b"]),
]

ACTIVITY_RULES = [
    ("spray",   [r"spray", r"pesticide", r"छिड़काव|फवारणी"]),
    ("sow",     [r"\bsow", r"\bsowing", r"\bplant(?:ing)? (?:seed|crop)", r"बुवाई|पेरणी"]),
    ("irrigate", [r"irrigat", r"water.*(?:crop|field|farm)", r"सिंचाई|सिंचन"]),
    ("harvest", [r"harvest", r"कटाई|कापणी"]),
    ("fish",    [r"\bfish", r"go.*\bsea\b", r"trawler", r"\bboat", r"मछली|मच्छीमार|समुद्र"]),
    ("fly",     [r"\bfly\b", r"\bflying\b", r"flight", r"\bairport", r"उड़ान|विमान"]),
    ("flood",   [r"flood", r"waterlog", r"बाढ़|बाढ"]),
]


_ACTIVITY_PATTERNS = [
    ("cycling", r"cycl|bike ride|सायकल"),
    ("running", r"run(?:ning)?\b|jog|मैराथन|जॉग|दौड"),
    ("laundry", r"dry clothes|laundry|wash.*cloth|कपडे सुकव|कपड़े.*सुक|धुलाई|బట్టలు|உடல்"),
    ("spraying", r"spray|pesticide|कीटनाशक|फवारणी|छिड़काव|तपाणें"),
    ("picnic", r"picnic"),
    ("event", r"event|wedding|party|function|कार्यक्रम|समारोह|लग्न"),
    ("cricket", r"cricket|football|match|खेल|स्पोर्ट्स"),
    ("fishing", r"fishing|boat|मासे|मछली"),
    ("trekking", r"trek|hike"),
    ("walking", r"walk|stroll|टहल|चालण्या"),
    ("swimming", r"swim"),
    ("solar", r"solar"),
    ("photography", r"photograph"),
    ("camping", r"camp\b"),
]


def _first_rule(q: str, rules) -> Optional[str]:
    for name, patterns in rules:
        for p in patterns:
            if re.search(p, q):
                return name
    return None


def detect_intent(query: str) -> str:
    """Backwards-compatible: best intent, 'fallback' if nothing recognised."""
    q = normalize(query)
    return (_first_rule(q, INTENT_RULES) or _first_rule(q, SOCIAL_RULES)
            or ("current" if extract_locations(query) else "fallback"))


def detect_domain(query: str) -> str:
    return _first_rule(normalize(query), DOMAIN_RULES) or "general"


def detect_activity(query: str) -> Optional[str]:
    return _first_rule(normalize(query), ACTIVITY_RULES)


# ─────────────────────────────────────────────────────────────────────────────
# parse_query
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_plan(intent: str, time_label: str, activity: Optional[str]) -> list:
    if intent in _NEEDS_NO_LOCATION:
        return []
    if intent == "alerts":
        return ["alerts", "current"]
    if intent == "climate":
        return ["climate"]
    future = time_label not in ("now", "today", "tonight")
    plan = []
    if intent in ("forecast", "rain"):
        plan.append("forecast")
        if not future:
            plan.append("current")
    elif future:
        plan.append("forecast")
    else:
        plan.append("current")
    if intent == "advisory" and activity == "flood":
        plan.append("alerts")
    return plan


def parse_query(query: str, context: Optional[dict] = None) -> dict:
    """
    Turn a user message into a structured query.

    context (optional) is the dict returned by update_context() for the same chat
    session. With it, follow-ups such as "and tomorrow?" or "what about Mumbai?" work.
    """
    ctx = context or {}
    q = normalize(query)
    lang = detect_language(query)
    locations = extract_locations(query)
    tinfo = parse_time(query)
    domain = detect_domain(query)
    activity = detect_activity(query)
    use_gps = _wants_gps(q) and not locations

    intent = _first_rule(q, INTENT_RULES)
    confidence = 0.9 if intent else 0.0
    source = "rules" if intent else None
    ml_top = None
    context_used = False

    if intent is None:
        social = _first_rule(q, SOCIAL_RULES)
        if social:
            intent, confidence, source = social, 0.9, "rules"
    short = len(q.split()) <= 6
    followup = bool(ctx.get("intent") and (locations or tinfo["explicit"]) and short)
    if intent is None:
        # trained classifier as backup for phrasings the rules do not know
        ml_top = _ml_predict(query, locations)
        if ml_top:
            top, p = ml_top[0]
            threshold = 0.8 if followup else ML_CONFIDENCE_THRESHOLD
            if p >= threshold and not (top == "fallback" and (locations or use_gps)):
                intent, confidence, source = top, round(p, 3), "model"
    if intent is None:
        if followup:
            intent, confidence, context_used, source = ctx["intent"], 0.6, True, "context"
        elif locations or use_gps:
            intent, confidence, source = "current", 0.6, "default"
        else:
            intent, source = "fallback", "none"

    # climate ranges override a plain intent
    label = tinfo["label"]
    if intent == "current" and re.match(r"next_\d+_days$|this_week$|next_week$|weekend$", label):
        intent = "forecast"
    if label.startswith("last_") or label.startswith("month:"):
        if intent in ("current", "forecast", "rain", "humidity", "wind", "feels_like", "heatwave", "cold_wave"):
            intent = "climate"

    # ── feature extractors: travel route, activity, crop + stage ──────────
    extra_route = None
    if intent == "travel":
        m = re.search(r"([a-z\u0900-\u0DFF]{2,25})\s+to\s+([a-z\u0900-\u0DFF]{2,25})", q)
        if m:
            a, b = m.group(1), m.group(2)
            stop = {"the", "my", "going", "driving", "from", "travel", "tomorrow", "today"}
            if a not in stop and b not in stop:
                extra_route = [a, b]
    activity_key = None
    if intent == "activity_plan":
        for key, pat in _ACTIVITY_PATTERNS:
            if re.search(pat, q):
                activity_key = key
                break
        activity_key = activity_key or "general"
    crop_key = stage_key = None
    if _crops is not None:
        crop_key = _crops.find_crop(q)
        stage_key = _crops.find_stage(q)
    if intent == "crop_calendar" and not crop_key and ctx.get("crop"):
        crop_key = ctx["crop"]
        context_used = True
    if intent == "crop_calendar" and not stage_key and ctx.get("crop_stage"):
        stage_key = ctx["crop_stage"]

    # inherit location / time from the conversation
    if intent not in _NEEDS_NO_LOCATION and not locations and not use_gps and ctx.get("location"):
        locations = [ctx["location"]]
        context_used = True
    if context_used and ctx.get("time_range") and not tinfo["explicit"] and intent == ctx.get("intent"):
        label = ctx["time_range"]
    if intent == "advisory" and activity == "fly" and domain == "general":
        domain = "aviation"
    if intent == "advisory" and activity == "fish" and domain == "general":
        domain = "marine"
    if intent == "advisory" and activity in ("spray", "sow", "irrigate", "harvest") and domain == "general":
        domain = "agriculture"

    needs_location = intent not in _NEEDS_NO_LOCATION and not locations and not use_gps
    route = None
    if len(locations) >= 2 and re.search(r"\bfrom\b.*\bto\b|\bto\b.*\bfrom\b|\bvia\b|\broute\b|से.*तक", q):
        route = (locations[0], locations[1])
    elif extra_route:
        route = tuple(extra_route)

    return {
        "intent":       intent,
        "location":     locations[0] if locations else None,
        "locations":    locations,
        "route":        route,
        "use_gps":      use_gps,
        "time_range":   label,
        "domain":       domain,
        "activity":     activity,
        "language":     lang,
        "confidence":   confidence,
        "intent_source": source,
        "ml_alternatives": ml_top,
        "needs_location": needs_location,
        "context_used": context_used,
        "fetch":        _fetch_plan(intent, label, activity),
        "tod":          detect_tod(query) or (ctx.get("tod") if context_used else None),
        "route_names":  extra_route,
        "activity_key": activity_key,
        "crop":         crop_key or (ctx.get("crop") if context_used else None),
        "crop_stage":   stage_key or (ctx.get("crop_stage") if context_used else None),
        "compare_month": tinfo.get("month"),
        "raw_query":    query,
        "normalized":   q,
    }


def update_context(context: Optional[dict], parsed: dict) -> dict:
    """Call after each turn and store the result in your session (e.g. MongoDB conversations)."""
    ctx = dict(context or {})
    ctx["language"] = parsed.get("language", ctx.get("language", "en"))
    if parsed.get("intent") not in _NEEDS_NO_LOCATION:
        ctx["intent"] = parsed["intent"]
        if parsed.get("location"):
            ctx["location"] = parsed["location"]
        ctx["time_range"] = parsed.get("time_range", "today")
    for k in ("tod", "activity_key", "crop", "crop_stage", "route_names"):
        if parsed.get(k):
            ctx[k] = parsed[k]
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Helper formatters
# ─────────────────────────────────────────────────────────────────────────────
def _heat_index(temp_c: float, humidity: float) -> float:
    """Rothfusz regression. Only meaningful from ~27°C; below that we return the air temperature."""
    if temp_c is None or humidity is None:
        return temp_c
    if temp_c < 27:
        return float(temp_c)
    T = temp_c * 9 / 5 + 32
    RH = humidity
    HI = (-42.379 + 2.04901523 * T + 10.14333127 * RH
          - 0.22475541 * T * RH - 6.83783e-3 * T ** 2
          - 5.481717e-2 * RH ** 2 + 1.22874e-3 * T ** 2 * RH
          + 8.5282e-4 * T * RH ** 2 - 1.99e-6 * T ** 2 * RH ** 2)
    return round((HI - 32) * 5 / 9, 1)


def _discomfort(temp, humidity) -> str:
    if temp is None or humidity is None:
        return "unknown"
    try:
        hi = _heat_index(temp, humidity)
    except Exception:
        return "unknown"
    if hi < 27:   return "comfortable"
    if hi < 32:   return "slightly uncomfortable"
    if hi < 38:   return "uncomfortable — humid and hot"
    if hi < 46:   return "very uncomfortable — heat exhaustion risk"
    return "dangerous — heat stroke risk 🚨"


def _rain_label(mm) -> str:
    mm = mm or 0
    if mm == 0:     return "no rainfall"
    if mm < 2.5:    return f"very light rain ({mm:.1f} mm)"
    if mm < 7.5:    return f"light rain ({mm:.1f} mm)"
    if mm < 35.5:   return f"moderate rain ({mm:.1f} mm)"
    if mm < 64.5:   return f"rather heavy rain ({mm:.1f} mm)"
    if mm < 115.6:  return f"heavy rain ({mm:.1f} mm) ⚠️"
    if mm < 204.5:  return f"very heavy rain ({mm:.1f} mm) ⚠️"
    return f"extremely heavy rain ({mm:.1f} mm) 🚨"


def _wind_label(kmh) -> str:
    kmh = kmh or 0
    if kmh < 2:    return f"calm ({kmh:.0f} km/h)"
    if kmh < 6:    return f"light air ({kmh:.0f} km/h)"
    if kmh < 12:   return f"light breeze ({kmh:.0f} km/h)"
    if kmh < 20:   return f"gentle breeze ({kmh:.0f} km/h)"
    if kmh < 29:   return f"moderate breeze ({kmh:.0f} km/h)"
    if kmh < 39:   return f"fresh breeze ({kmh:.0f} km/h)"
    if kmh < 50:   return f"strong breeze ({kmh:.0f} km/h)"
    if kmh < 62:   return f"near gale ({kmh:.0f} km/h) — secure loose objects ⚠️"
    if kmh < 75:   return f"gale ({kmh:.0f} km/h) — avoid outdoors ⚠️"
    if kmh < 89:   return f"strong gale ({kmh:.0f} km/h) 🚨 stay indoors"
    return f"storm-force wind ({kmh:.0f} km/h) 🚨 stay indoors"


def _temp_feel(temp) -> str:
    if temp is None: return "unknown"
    if temp < 5:   return "very cold — heavy winter clothing needed"
    if temp < 12:  return "cold — wear a warm jacket"
    if temp < 18:  return "cool — light jacket recommended"
    if temp < 24:  return "comfortable — light clothing is fine"
    if temp < 30:  return "warm — light and breathable clothes"
    if temp < 36:  return "hot — stay hydrated, wear light cotton"
    return "very hot — avoid outdoor midday exposure, drink lots of water"


def _rain_umbrella(rain_mm, desc: str, prob=None) -> str:
    rain_mm = rain_mm or 0
    desc = desc or ""
    if rain_mm > 1 or any(w in desc for w in ["rain", "drizzle", "shower", "thunder"]) or (prob or 0) >= 60:
        return "✅ Yes, carry an umbrella — rain is likely."
    if any(w in desc for w in ["cloud", "overcast"]) or (prob or 0) >= 30:
        return "🌂 Maybe carry one — skies are cloudy, rain is possible."
    return "☀️ No umbrella needed — no rain expected."


def _clothing_advice(temp, rain, wind_kmh, desc: str) -> str:
    temp = 25 if temp is None else temp
    rain = rain or 0
    wind_kmh = wind_kmh or 0
    desc = desc or ""
    items = []
    if temp < 10:      items += ["heavy jacket", "warm layers", "gloves", "muffler"]
    elif temp < 18:    items += ["light jacket or sweater"]
    elif temp < 26:    items += ["light clothing — T-shirt or shirt"]
    else:              items += ["light breathable cotton", "light colours"]
    if rain > 1 or "rain" in desc:
        items.append("waterproof jacket or umbrella")
    if wind_kmh > 30:
        items.append("windproof outer layer")
    if temp > 33:
        items.append("carry water — heat is high")
    return "Suggested: " + ", ".join(items) + "."


def _outdoor_verdict(rain, wind_kmh, temp, desc: str) -> str:
    rain = rain or 0
    wind_kmh = wind_kmh or 0
    temp = 25 if temp is None else temp
    desc = desc or ""
    issues = []
    if rain > 10:           issues.append("heavy rain expected")
    elif rain > 1:          issues.append("light rain possible")
    if wind_kmh > 50:       issues.append("strong winds")
    if temp > 40:           issues.append("extreme heat")
    if temp < 5:            issues.append("very cold")
    if "thunder" in desc:   issues.append("thunderstorms")
    if not issues:          return "✅ Great conditions for outdoor activities!"
    if len(issues) == 1 and rain < 5 and wind_kmh < 40:
        return f"⚠️ Mostly okay but note: {issues[0]}. Plan accordingly."
    return f"❌ Not ideal — {', '.join(issues)}. Consider rescheduling."


def _emoji_for(desc: str) -> str:
    desc = desc or ""
    if "thunder" in desc:                                      return "⛈"
    if "rain" in desc or "drizzle" in desc or "shower" in desc: return "🌧"
    if "snow" in desc:                                         return "❄️"
    if "fog" in desc or "mist" in desc:                        return "🌫"
    if "clear" in desc or "sunny" in desc:                     return "☀️"
    if "cloud" in desc or "overcast" in desc:                  return "⛅"
    return "🌦"


# ─────────────────────────────────────────────────────────────────────────────
# Weather-data normalisation
# One flat dict "w" is used by every response function:
#   loc, temp, temp_min, feels, hum, wind_kmh, desc, rain, prob, pres, vis, src, kind, label, days
# ─────────────────────────────────────────────────────────────────────────────
def _wind_kmh_from_forecast(v) -> float:
    v = v or 0
    return v if WIND_MAX_UNIT == "kmh" else v * 3.6


def _norm_current(c: dict) -> dict:
    c = c or {}
    return {
        "loc": c.get("location"), "temp": c.get("temperature"), "temp_min": None,
        "feels": c.get("feels_like"), "hum": c.get("humidity"),
        "wind_kmh": (c.get("wind_speed") or 0) * 3.6,
        "desc": (c.get("description") or "").lower(), "rain": c.get("rainfall_1h") or 0,
        "prob": None, "pres": c.get("pressure"), "vis": c.get("visibility"),
        "src": c.get("source", "OpenWeatherMap"), "kind": "now", "label": "", "days": 0,
        "empty": not c or "error" in c,
    }


def _norm_days(days: list, loc, src, label: str) -> dict:
    tmax = [d.get("temp_max") for d in days if d.get("temp_max") is not None]
    tmin = [d.get("temp_min") for d in days if d.get("temp_min") is not None]
    rain = [d.get("precipitation") or 0 for d in days]
    probs = [d.get("precipitation_probability_max") for d in days if d.get("precipitation_probability_max") is not None]
    hums = [d.get("humidity_mean") for d in days if d.get("humidity_mean") is not None]
    codes = [d.get("weather_code") or 0 for d in days]
    worst = max(codes) if codes else 0
    return {
        "loc": loc, "temp": max(tmax) if tmax else None, "temp_min": min(tmin) if tmin else None,
        "feels": None, "hum": (sum(hums) / len(hums)) if hums else None,
        "wind_kmh": max((_wind_kmh_from_forecast(d.get("wind_max")) for d in days), default=0),
        "desc": WMO.get(worst, ""), "rain": max(rain) if rain else 0,
        "prob": max(probs) if probs else None, "pres": None, "vis": None,
        "src": src or "Open-Meteo", "kind": "forecast", "label": label, "days": len(days),
        "empty": not days,
    }


_PERIOD_TEXT = {
    "now": "right now", "today": "today", "tonight": "tonight", "tomorrow": "tomorrow",
    "day_after_tomorrow": "the day after tomorrow", "weekend": "this weekend",
    "this_week": "this week", "next_week": "next week", "yesterday": "yesterday",
}


def _period_text(tr: str) -> str:
    if tr in _PERIOD_TEXT:
        return _PERIOD_TEXT[tr]
    m = re.match(r"next_(\d+)_days", tr)
    if m:
        return f"the next {m.group(1)} days"
    m = re.match(r"in_(\d+)_days", tr)
    if m:
        return f"{m.group(1)} days from now"
    if tr.startswith("date:"):
        try:
            return date.fromisoformat(tr[5:]).strftime("%A, %d %b")
        except Exception:
            return tr[5:]
    return tr


def _select_days(fc: list, tr: str):
    """Pick the forecast days that answer the time range. Returns (days, human_label)."""
    label = _period_text(tr)
    if not fc:
        return [], label
    if tr in ("now", "today", "tonight"):
        return fc[:1], label
    if tr == "tomorrow":
        return fc[1:2], label
    if tr == "day_after_tomorrow":
        return fc[2:3], label
    if tr == "weekend":
        out = []
        for d in fc:
            try:
                if date.fromisoformat(d["date"]).weekday() >= 5:
                    out.append(d)
            except Exception:
                pass
        return out[:2], label
    if tr == "this_week":
        return fc[:7], label
    if tr == "next_week":
        return fc[7:14], label
    m = re.match(r"next_(\d+)_days", tr)
    if m:
        return fc[:int(m.group(1))], label
    m = re.match(r"in_(\d+)_days", tr)
    if m:
        n = int(m.group(1))
        return fc[n:n + 1], label
    if tr.startswith("date:"):
        return [d for d in fc if d.get("date") == tr[5:]], label
    if tr == "this_month":
        return fc[:7], "the coming week"
    return [], label


def _resolve(parsed: dict, weather_data: dict):
    """
    Returns (w, note). w is the flat weather dict for the requested time.
    note is a short line to append when we had to fall back to other data.
    """
    tr = parsed.get("time_range", "today")
    cur = (weather_data or {}).get("current") or {}
    fcd = (weather_data or {}).get("forecast") or {}
    fc = fcd.get("forecast") or []
    if tr in ("now", "today", "tonight") and cur and "error" not in cur:
        w = _norm_current(cur)
        w["label"] = _period_text(tr)
        return w, ""
    days, label = _select_days(fc, tr)
    if days:
        return _norm_days(days, fcd.get("location") or cur.get("location"), fcd.get("source"), label), ""
    if cur and "error" not in cur:
        w = _norm_current(cur)
        note = ""
        if tr not in ("now", "today", "tonight"):
            note = f"ℹ️  I couldn't load the forecast for {label}, so this shows current conditions."
        w["label"] = "right now"
        return w, note
    return _norm_current({}), ""


def _unavailable(location: str) -> str:
    return f"Sorry, I couldn't retrieve weather data for {location}. Please check the place name and try again."


def _extra_locations_hint(parsed: dict) -> str:
    locs = parsed.get("locations") or []
    if len(locs) > 1:
        others = ", ".join(locs[1:])
        return f"\n💡  You also mentioned {others}. Ask me about it separately to compare."
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Response generators
# ─────────────────────────────────────────────────────────────────────────────
def _greeting_response(query: str, lang: str = "en") -> str:
    q = (query or "").lower()
    if any(w in q for w in ["who are you", "what are you", "what can you", "how do you", "help"]):
        return (
            "I'm WeatherGPT — your weather assistant for India. 🌦\n\n"
            "Here's what I can help you with:\n"
            "• Current weather for any city\n"
            "• 7-day forecasts and rain chances\n"
            "• Fog, heatwave and cold wave checks\n"
            "• Umbrella and clothing advice\n"
            "• Agriculture, aviation and marine advisories\n"
            "• Climate history and trends\n"
            "• Active weather alerts\n\n"
            "Try asking:\n"
            "  'Will it rain in Mumbai tomorrow?'\n"
            "  'Should I carry an umbrella in Delhi today?'\n"
            "  'Is it safe to go fishing in Goa?'\n"
            "You can also ask in Hindi, Marathi and other Indian languages."
        )
    g = _msg("greeting", lang)
    return random.choice(g) if isinstance(g, list) else g


def _current_response(w: dict, location: str, domain: str, intent: str, parsed: dict, note: str = "") -> str:
    if w["empty"]:
        return _unavailable(location)

    loc, temp, feels, hum = w["loc"] or location, w["temp"], w["feels"], w["hum"]
    wind_kmh, desc, rain, pres = w["wind_kmh"], w["desc"], w["rain"], w["pres"]
    is_now = w["kind"] == "now"
    emoji = _emoji_for(desc)

    if is_now and (w["label"] in ("right now", "today", "") or note):
        head = f"{emoji} Current weather in {loc}:\n"
    else:
        head = f"{emoji} Weather in {loc} for {w['label']}:\n"
    lines = [head]
    if temp is not None:
        if is_now:
            lines.append(f"🌡  Temperature : {temp}°C" + (f" (feels like {feels}°C)" if feels is not None else ""))
        else:
            rng = f"{w['temp_min']}°C – {temp}°C" if w["temp_min"] is not None else f"up to {temp}°C"
            lines.append(f"🌡  Temperature : {rng}")
    lines.append(f"🌤  Condition   : {desc.capitalize() or 'N/A'}")
    if hum is not None:
        lines.append(f"💧  Humidity    : {hum:.0f}%")
    lines.append(f"💨  Wind        : {_wind_label(wind_kmh)}")
    if pres:
        lines.append(f"🔵  Pressure    : {pres} hPa")
    if rain:
        lines.append(f"🌧  Rain ({'1h' if is_now else 'peak day'}) : {rain} mm")
    if w["prob"] is not None:
        lines.append(f"☔  Rain chance : {w['prob']:.0f}%")
    if temp is not None and hum is not None:
        lines.append(f"😓  Comfort     : {_discomfort(temp, hum)}")

    # Intent-specific extras
    if intent == "umbrella":
        lines.append(f"\n{_rain_umbrella(rain, desc, w['prob'])}")
    elif intent == "clothing":
        lines.append(f"\n👕 {_clothing_advice(temp, rain, wind_kmh, desc)}")
    elif intent == "feels_like":
        lines.append(f"\n🌡  How it feels: {_temp_feel(feels if feels is not None else temp)}")
    elif intent == "humidity":
        if hum is None:
            lines.append("\n💦  Humidity data isn't available for that period.")
        else:
            lines.append(f"\n💦  Humidity {hum:.0f}% — {_discomfort(temp, hum)}")
    elif intent == "wind":
        lines.append(f"\n💨  Wind detail: {_wind_label(wind_kmh)}")
    elif intent == "fog":
        if "fog" in desc or "mist" in desc:
            lines.append("\n🌫  Fog/mist reported. Drive carefully and use low-beam headlights.")
        else:
            lines.append("\n✅  No fog or mist reported.")
    elif intent in ("outdoor", "jogging"):
        lines.append(f"\n{_outdoor_verdict(rain, wind_kmh, temp, desc)}")
    elif intent == "commute":
        if rain > 5 or wind_kmh > 50:
            lines.append("\n🚗  Commute: Allow extra time — rain or strong winds expected.")
        else:
            lines.append("\n🚗  Commute looks fine — no severe weather on the roads.")
    elif intent == "plants":
        if rain > 2:
            lines.append("\n🌿  Plants: Rain present — no need to water.")
        else:
            lines.append("\n🌿  Plants: No significant rain — water your plants if needed.")

    # Domain advice
    if domain == "agriculture":
        if rain > 0:
            lines.append("\n🌾  Farm advisory: Rain present — avoid spraying. Wait for dry conditions.")
        elif wind_kmh > 20:
            lines.append("\n🌾  Farm advisory: Winds too high for pesticide spraying.")
        elif wind_kmh < 15:
            lines.append("\n🌾  Farm advisory: Good conditions for spraying or fieldwork.")
        else:
            lines.append("\n🌾  Farm advisory: Moderate wind — spray only in calm spells, early morning is best.")
    elif domain == "marine":
        if wind_kmh < 30 and "thunder" not in desc:
            lines.append("\n🚢  Marine: Conditions appear manageable. Always verify with the coast guard.")
        else:
            lines.append("\n🚢  Marine: Strong winds or storms — avoid going out to sea.")
    elif domain == "aviation":
        lines.append("\n✈️   Aviation: Verify METAR/TAF at the airport before any flight.")

    if note:
        lines.append(f"\n{note}")
    lines.append(_extra_locations_hint(parsed))
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(l for l in lines if l is not None)


def _forecast_response(fdata: dict, location: str, time_range: str, domain: str, parsed: dict = None) -> str:
    fc = (fdata or {}).get("forecast") or []
    if not fdata or not fc:
        return f"Sorry, I couldn't retrieve forecast data for {location}."

    loc = fdata.get("location", location)
    src = fdata.get("source", "Open-Meteo")
    days, label = _select_days(fc, time_range)

    if not days:
        if time_range == "yesterday" or time_range.startswith("last_"):
            return "I show forecasts and climate summaries. For past weather, ask for a range like 'rainfall in Pune last 7 days'."
        return (f"I don't have forecast data for {label}. My forecast covers the next {len(fc)} days — "
                f"try asking for 'this week' or 'next {min(len(fc), 7)} days'.")

    if time_range in ("today", "now"):
        title = f"Today's forecast for {loc}"
    elif time_range == "tonight":
        title = f"Tonight's forecast for {loc}"
    elif time_range == "tomorrow":
        title = f"Tomorrow's forecast for {loc}"
    elif time_range == "day_after_tomorrow":
        title = f"Day-after-tomorrow forecast for {loc}"
    elif time_range == "weekend":
        title = f"Weekend forecast for {loc}"
    else:
        title = f"Forecast for {loc} — {label}" if len(days) == 1 else f"{len(days)}-day forecast for {loc} ({label})"

    lines = [f"📅 {title}:\n"]
    for day in days:
        d = day.get("date", "")
        tmax = day.get("temp_max", "N/A")
        tmin = day.get("temp_min", "N/A")
        rain = day.get("precipitation", 0) or 0
        wind = _wind_kmh_from_forecast(day.get("wind_max"))
        code = day.get("weather_code", 0)
        prob = day.get("precipitation_probability_max")
        wdesc = WMO.get(code, "")
        emoji = WMO_EMOJI.get(code, "🌡")
        try:
            day_label = date.fromisoformat(d).strftime("%A, %d %b")
        except Exception:
            day_label = d
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"📅 {day_label}")
        lines.append(f"   {emoji} {wdesc.capitalize()}")
        lines.append(f"   🌡 {tmax}°C / {tmin}°C")
        lines.append(f"   🌧 {_rain_label(rain)}" + (f" — chance {prob:.0f}%" if prob is not None else ""))
        lines.append(f"   💨 Wind max: {_wind_label(wind)}")
    lines.append("━━━━━━━━━━━━━━━")

    rain0 = max((d.get("precipitation") or 0) for d in days)
    wind0 = max(_wind_kmh_from_forecast(d.get("wind_max")) for d in days)
    if domain == "agriculture":
        if rain0 > 10:
            lines.append("\n🌾  Farming: Rain expected — delay spraying and harvesting.")
        elif wind0 > 30:
            lines.append("\n🌾  Farming: High winds — avoid spraying pesticides.")
        else:
            lines.append("\n🌾  Farming: Conditions look suitable for fieldwork.")
    elif domain == "marine":
        if wind0 > 40:
            lines.append("\n🚢  Marine: Avoid going out — strong winds in forecast.")
        else:
            lines.append("\n🚢  Marine: Conditions appear manageable. Verify with coast guard.")
    elif domain == "aviation":
        lines.append("\n✈️   Aviation: Check official METAR/TAF before flight.")

    if parsed:
        lines.append(_extra_locations_hint(parsed))
    lines.append(f"\n📡  Source: {src}")
    return "\n".join(lines)


def _rain_response(w: dict, note: str, location: str, parsed: dict) -> str:
    """Direct yes/no answer to 'will it rain ...?'."""
    if w["empty"]:
        return _unavailable(location)
    loc = w["loc"] or location
    rain, prob, desc = w["rain"], w["prob"], w["desc"]
    rainy_desc = any(k in desc for k in ("rain", "drizzle", "shower", "thunder"))
    if rain >= 1 or rainy_desc or (prob or 0) >= 60:
        head = f"🌧  Yes — rain is likely in {loc} {w['label']}."
    elif (prob or 0) >= 30 or rain > 0:
        head = f"🌦  There is a chance of some rain in {loc} {w['label']}."
    else:
        head = f"☀️  No significant rain is expected in {loc} {w['label']}."
    lines = [head, ""]
    lines.append(f"   {_rain_label(rain)}" + (" (peak day)" if w["kind"] == "forecast" and w["days"] > 1 else ""))
    if prob is not None:
        lines.append(f"   ☔ Chance of rain: {prob:.0f}%")
    if desc:
        lines.append(f"   🌤 Conditions: {desc.capitalize()}")
    if rain >= 1 or rainy_desc:
        lines.append(f"\n{_rain_umbrella(rain, desc, prob)}")
    if note:
        lines.append(f"\n{note}")
    lines.append(_extra_locations_hint(parsed))
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _alerts_response(alerts: list, location: str) -> str:
    has_loc = bool(location) and location != "your location"
    loc_str = f" near {location}" if has_loc else ""
    if not alerts:
        return f"✅  No active weather alerts{loc_str} at this time.\n\nStay safe and check back for updates."
    lines = [f"⚠️  Active weather alerts{loc_str}:\n"]
    sev_map = {"low": "🟡", "medium": "🟠", "high": "🔴", "extreme": "🟣"}
    for a in alerts[:5]:
        sev = a.get("severity", "medium")
        haz = a.get("hazard_type", "Alert")
        msg = a.get("message", "")
        src = a.get("source", "")
        lines.append(f"{sev_map.get(sev, '⚠️')} [{sev.upper()}] {haz}")
        lines.append(f"   {msg}")
        if src:
            lines.append(f"   📡 Source: {src}")
        lines.append("")
    lines.append("Always follow instructions from your local disaster management authority.")
    return "\n".join(lines)


def _climate_response(data: dict, location: str, parsed: dict = None) -> str:
    records = (data or {}).get("records", [])
    if not records:
        return (f"No historical climate data available for {location}. "
                f"Try a range such as 'last 5 years' or 'last 30 days'.")
    temps_max = [r["temp_max"] for r in records if r.get("temp_max") is not None]
    temps_min = [r["temp_min"] for r in records if r.get("temp_min") is not None]
    rain_vals = [r["precipitation"] for r in records if r.get("precipitation") is not None]
    total_rain = sum(rain_vals)
    avg_max = sum(temps_max) / len(temps_max) if temps_max else 0
    avg_min = sum(temps_min) / len(temps_min) if temps_min else 0
    max_temp = max(temps_max) if temps_max else 0
    min_temp = min(temps_min) if temps_min else 0
    rainy_days = sum(1 for r in rain_vals if r > 1)
    from_date, to_date = data.get("from", ""), data.get("to", "")
    src = data.get("source", "Open-Meteo Archive")

    lines = [f"📊  Climate summary for {location} ({from_date} → {to_date}):\n"]
    lines.append(f"🌡  Average high  : {avg_max:.1f}°C")
    lines.append(f"🌡  Average low   : {avg_min:.1f}°C")
    lines.append(f"🔥  Peak temp     : {max_temp:.1f}°C")
    lines.append(f"❄️   Lowest temp   : {min_temp:.1f}°C")
    lines.append(f"🌧  Total rainfall: {total_rain:.1f} mm over {len(records)} days")
    lines.append(f"☔  Rainy days    : {rainy_days} days")
    lines.append(f"📈  Avg daily rain: {total_rain / len(records):.1f} mm/day")
    if len(records) > 365:
        lines.append(f"📆  Avg yearly rain: {total_rain / (len(records) / 365.25):.0f} mm/year")
    lines.append(f"\n📡  Source: {src}")
    return "\n".join(lines)


def _heatwave_response(w: dict, location: str) -> str:
    temp = w["temp"]
    if w["empty"] or temp is None:
        return f"Unable to retrieve temperature data for {location}."
    lines = []
    if temp >= 40:
        lines.append(f"🔥  HEATWAVE CONDITIONS in {location} ({w['label']}): {temp}°C\n")
        lines += ["Heat safety tips:",
                  "• Stay indoors during 11 AM – 4 PM",
                  "• Drink at least 3–4 litres of water daily",
                  "• Wear light, loose, light-coloured cotton clothes",
                  "• Never leave children or pets in parked vehicles",
                  "• Watch for heatstroke: confusion, no sweating, very high body temp"]
    elif temp >= 35:
        lines.append(f"🌡  Hot in {location} ({w['label']}): {temp}°C — heatwave threshold approaching.")
        lines.append("Stay hydrated and avoid prolonged sun exposure.")
    else:
        lines.append(f"✅  No heatwave in {location} ({w['label']}). Temperature is {temp}°C.")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _cold_wave_response(w: dict, location: str) -> str:
    temp = w["temp_min"] if (w["kind"] == "forecast" and w["temp_min"] is not None) else w["temp"]
    if w["empty"] or temp is None:
        return f"Unable to retrieve temperature data for {location}."
    lines = []
    if temp <= 5:
        lines.append(f"🥶  COLD WAVE CONDITIONS in {location} ({w['label']}): {temp}°C\n")
        lines += ["Cold wave safety tips:",
                  "• Wear multiple layers — wool/fleece inner + windproof outer",
                  "• Keep elderly and infants warm — extra blankets at night",
                  "• Avoid alcohol — it lowers core body temperature",
                  "• Watch for hypothermia: shivering, slurred speech, drowsiness"]
    elif temp <= 10:
        lines.append(f"🌡  Cold in {location} ({w['label']}): {temp}°C — dress warmly.")
    else:
        lines.append(f"✅  No cold wave in {location} ({w['label']}). Temperature is {temp}°C.")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _thunder_response(w: dict, location: str) -> str:
    if w["empty"]:
        return _unavailable(location)
    desc = w["desc"]
    lines = []
    if "thunder" in desc or "storm" in desc:
        lines.append(f"⛈  Thunderstorm activity expected in {location} ({w['label']})!\n")
        lines += ["Lightning safety:",
                  "• Stay indoors, away from windows and metal objects",
                  "• Unplug electronics",
                  "• Avoid open fields, hilltops, tall trees",
                  "• If caught outside, crouch low — do not lie flat on the ground",
                  "• Avoid water bodies and metal fences"]
    else:
        lines.append(f"✅  No thunderstorm expected in {location} ({w['label']}).")
        lines.append(f"   Conditions: {desc.capitalize() or 'N/A'}")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _wind_response(w: dict, location: str) -> str:
    if w["empty"]:
        return f"Unable to retrieve wind data for {location}."
    kmh = w["wind_kmh"]
    lines = [f"💨  Wind conditions in {location} ({w['label']}):\n", f"   {_wind_label(kmh)}"]
    if kmh > 62:
        lines.append("\n⚠️  Dangerous winds — stay indoors and secure loose outdoor objects.")
    elif kmh > 40:
        lines.append("\nStrong winds — be cautious if driving high-sided vehicles.")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _snow_response(w: dict, location: str) -> str:
    if w["empty"]:
        return _unavailable(location)
    desc, temp = w["desc"], (w["temp_min"] if w["kind"] == "forecast" and w["temp_min"] is not None else w["temp"])
    lines = []
    if "snow" in desc or "blizzard" in desc or "sleet" in desc:
        lines.append(f"❄️  Snow/ice conditions in {location} ({w['label']})!")
        lines += ["• Drive slowly — roads may be icy",
                  "• Wear waterproof boots and warm layers",
                  "• Avoid unnecessary travel during heavy snowfall"]
    elif temp is not None and temp <= 2:
        lines.append(f"🌡  Near-freezing in {location} ({temp}°C). Frost possible — drive carefully.")
    else:
        lines.append(f"✅  No snow or ice expected in {location} ({w['label']}).")
        if temp is not None:
            lines.append(f"   Temperature: {temp}°C")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _fog_response(w: dict, location: str) -> str:
    if w["empty"]:
        return _unavailable(location)
    desc, vis = w["desc"], w["vis"]
    lines = []
    if "fog" in desc or "mist" in desc:
        lines.append(f"🌫  Fog/mist expected in {location} ({w['label']})!")
        if vis is not None:
            lines.append(f"   Visibility: {vis / 1000:.1f} km")
        lines += ["\nFog driving tips:",
                  "• Use low-beam headlights and fog lights",
                  "• Reduce speed and increase following distance",
                  "• Do not use high beams — they reflect off fog",
                  "• Pull over if visibility drops below 50 metres"]
    else:
        lines.append(f"✅  No fog or mist expected in {location} ({w['label']}).")
        if vis is not None:
            lines.append(f"   Visibility: {vis / 1000:.1f} km — clear.")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _uv_response(w: dict, location: str) -> str:
    if w["empty"]:
        return _unavailable(location)
    desc = w["desc"]
    lines = [f"☀️  UV advisory for {location} ({w['label']}):\n"]
    if "clear" in desc or "sunny" in desc:
        lines.append("Sky is clear — UV levels are likely moderate to high.")
        lines.append("• Apply SPF 30+ sunscreen if outdoors for >20 min")
        lines.append("• Wear sunglasses and a hat between 10 AM and 4 PM")
    elif "cloud" in desc or "overcast" in desc:
        lines.append("Cloud reduces UV but does not remove it — moderate protection is still advised.")
    else:
        lines.append("UV index data is not directly available. Use sun protection on clear days.")
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


def _advisory_response(w: dict, location: str, parsed: dict, alerts: list, note: str = "") -> str:
    """Activity-specific advice: spray / sow / irrigate / harvest / fish / fly / flood."""
    if w["empty"]:
        return _unavailable(location)
    act = parsed.get("activity")
    rain, wind, temp, desc, prob = w["rain"], w["wind_kmh"], w["temp"], w["desc"], w["prob"]
    thunder = "thunder" in desc
    when = w["label"]
    lines = []

    if act == "spray":
        lines.append(f"🌾  Spraying in {location} ({when}):")
        if rain > 0 or (prob or 0) >= 50:
            lines.append("❌  Not recommended — rain is likely and will wash the spray off. Wait for a dry spell.")
        elif wind > 20:
            lines.append(f"❌  Not recommended — wind is {wind:.0f} km/h, spray will drift.")
        elif wind > 15:
            lines.append(f"⚠️  Marginal — wind is {wind:.0f} km/h. Spray only in calm spells.")
        else:
            lines.append("✅  Good conditions — low wind and no rain expected.")
        lines.append("   Tip: early morning or late evening is best; avoid midday heat.")
    elif act == "sow":
        lines.append(f"🌱  Sowing in {location} ({when}):")
        if rain > 25:
            lines.append("❌  Postpone — heavy rain can wash away seed and waterlog the field.")
        elif temp is not None and temp > 40:
            lines.append("⚠️  Very hot — seedlings may suffer heat stress. Sow in the cooler evening or wait.")
        elif 2 <= rain <= 25:
            lines.append("✅  Good — light to moderate rain gives soil moisture for germination.")
        else:
            lines.append("✅  Suitable if the soil has enough moisture; plan irrigation if it stays dry.")
        lines.append("   Tip: check the crop's recommended sowing window for your region.")
    elif act == "irrigate":
        lines.append(f"💧  Irrigation in {location} ({when}):")
        if rain > 5 or (prob or 0) >= 60:
            lines.append("⏸  Skip or delay — rain is expected and will supply water.")
        elif temp is not None and temp > 35:
            lines.append("✅  Irrigate — it is hot. Water in the early morning or evening to cut evaporation.")
        else:
            lines.append("✅  No rain expected — irrigate as per crop need.")
    elif act == "harvest":
        lines.append(f"🌾  Harvesting in {location} ({when}):")
        if rain > 0 or (prob or 0) >= 40 or thunder:
            lines.append("❌  Postpone if possible — rain can damage the crop and delay drying.")
        else:
            lines.append("✅  Dry weather — good time to harvest and dry the produce.")
    elif act == "fish":
        lines.append(f"🚢  Going to sea near {location} ({when}):")
        if thunder or wind >= 40:
            lines.append(f"❌  Not safe — {'thunderstorms' if thunder else f'strong winds ({wind:.0f} km/h)'} expected.")
        elif wind >= 30:
            lines.append(f"⚠️  Caution — wind {wind:.0f} km/h. Small boats should stay close to shore.")
        else:
            lines.append(f"✅  Conditions look manageable (wind {wind:.0f} km/h).")
        lines.append("   Always check the coast guard / fisheries department warning before sailing.")
    elif act == "fly":
        lines.append(f"✈️   Flying conditions at {location} ({when}):")
        vis_km = (w["vis"] or 10000) / 1000
        problems = []
        if thunder:       problems.append("thunderstorms")
        if wind >= 40:    problems.append(f"strong surface winds ({wind:.0f} km/h)")
        if "fog" in desc or vis_km < 5:
            problems.append("low visibility / fog")
        if problems:
            lines.append(f"⚠️  Possible delays or hazards: {', '.join(problems)}.")
        else:
            lines.append("✅  No major weather hazards seen in the surface forecast.")
        lines.append("   This is general guidance only. Get the official METAR/TAF and a briefing before any flight.")
    elif act == "flood":
        lines.append(f"🌊  Flood / waterlogging risk in {location} ({when}):")
        if rain >= 115:
            lines.append(f"🚨  HIGH — very heavy rain forecast ({rain:.0f} mm). Avoid low-lying areas and follow official advice.")
        elif rain >= 64.5:
            lines.append(f"⚠️  ELEVATED — heavy rain ({rain:.0f} mm). Waterlogging is possible in low-lying areas.")
        elif rain >= 20:
            lines.append(f"🟡  MODERATE — {rain:.0f} mm expected. Watch drains and underpasses.")
        else:
            lines.append("✅  LOW — rainfall is not heavy enough to cause flooding.")
        if alerts:
            lines.append(f"\n   There are {len(alerts)} active alert(s) — ask me 'weather alerts' for details.")
        lines.append("   Based on rainfall only. Rivers and dams depend on upstream rain — check official flood bulletins.")
    else:
        return _current_response(w, location, parsed.get("domain", "general"), "advisory", parsed, note)

    if note:
        lines.append(f"\n{note}")
    lines.append(_extra_locations_hint(parsed))
    lines.append(f"\n📡  Source: {w['src']}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Localised replies (Hindi / Hinglish / Marathi) — text lives in i18n_replies.py
# ─────────────────────────────────────────────────────────────────────────────
LOCAL_INTENTS = {"current", "rain", "umbrella", "forecast", "wind", "humidity", "feels_like", "alerts"}
_T = {"mod": None, "tried": False}


def _i18n():
    if not _T["tried"]:
        _T["tried"] = True
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            if here not in sys.path:
                sys.path.insert(0, here)
            import i18n_replies
            _T["mod"] = i18n_replies
        except Exception:
            _T["mod"] = None
    return _T["mod"]


def _local_response(intent: str, parsed: dict, weather_data: dict, lang: str) -> Optional[str]:
    """Reply in the user's language for the most common intents. None = use the English reply."""
    T = _i18n()
    if T is None or lang not in T.SUPPORTED or intent not in LOCAL_INTENTS:
        return None
    tr = parsed.get("time_range", "today")
    loc = parsed.get("location") or T.s(lang, "your_place")
    has_loc = bool(parsed.get("location"))
    more = ""
    locs = parsed.get("locations") or []
    if len(locs) > 1:
        more = "\n" + T.s(lang, "more_places", others=", ".join(locs[1:]))

    if intent == "alerts":
        alerts = weather_data.get("alerts") or []
        if not alerts:
            return T.s(lang, "alert_none" if has_loc else "alert_none_noloc", loc=loc)
        lines = [T.s(lang, "alert_head" if has_loc else "alert_head_noloc", loc=loc), ""]
        icons = {"low": "🟡", "medium": "🟠", "high": "🔴", "extreme": "🟣"}
        for a in alerts[:5]:
            sev = a.get("severity", "medium")
            lines.append(f"{icons.get(sev, '⚠️')} [{T.STRINGS[lang]['sev'].get(sev, sev)}] {a.get('hazard_type', '')}")
            if a.get("message"):
                lines.append(f"   {a['message']}")
            if a.get("source"):
                lines.append(T.s(lang, "alert_source", src=a["source"]))
            lines.append("")
        lines.append(T.s(lang, "alert_foot"))
        return "\n".join(lines)

    if intent == "forecast":
        fdata = weather_data.get("forecast") or {}
        fc = fdata.get("forecast") or []
        if not fc:
            return T.s(lang, "fc_nodata", loc=loc)
        days, _ = _select_days(fc, tr)
        period = T.period_text(tr, lang)
        if not days:
            return T.s(lang, "fc_none", period=period, n=len(fc))
        title = T.s(lang, "fc_title_one" if len(days) == 1 else "fc_title_many", loc=fdata.get("location", loc),
                    period=period, n=len(days))
        lines = [title, ""]
        for d in days:
            wdesc = WMO.get(d.get("weather_code", 0), "")
            lines.append(T.s(lang, "fc_day", day=T.day_label(d.get("date", ""), lang),
                             emoji=WMO_EMOJI.get(d.get("weather_code", 0), "🌡"), d=T.desc_local(wdesc, lang)))
            lines.append(T.s(lang, "fc_day2", tmax=d.get("temp_max", "–"), tmin=d.get("temp_min", "–"),
                             r=T.rain_label(d.get("precipitation") or 0, lang),
                             w=T.wind_label(_wind_kmh_from_forecast(d.get("wind_max")), lang)))
        lines.append("")
        lines.append(T.s(lang, "source", src=fdata.get("source", "Open-Meteo")))
        return "\n".join(lines) + more

    w, note = _resolve(parsed, weather_data)
    if w["empty"]:
        return T.s(lang, "unavailable", loc=loc)
    loc = w["loc"] or loc
    period = T.period_text("now" if note else tr, lang)
    desc, rain, prob = w["desc"], w["rain"], w["prob"]
    is_now = w["kind"] == "now"
    out = []

    if intent == "rain":
        rainy = any(k in desc for k in ("rain", "drizzle", "shower", "thunder"))
        if rain >= 1 or rainy or (prob or 0) >= 60:
            out.append(T.s(lang, "rain_yes", loc=loc, period=period))
        elif (prob or 0) >= 30 or rain > 0:
            out.append(T.s(lang, "rain_maybe", loc=loc, period=period))
        else:
            out.append(T.s(lang, "rain_no", loc=loc, period=period))
        out.append("")
        amount = T.rain_label(rain, lang)
        out.append("   " + (T.s(lang, "rain_amount_peak", r=amount) if (w["kind"] == "forecast" and w["days"] > 1) else amount))
        if prob is not None:
            out.append("   " + T.s(lang, "prob", p=f"{prob:.0f}"))
        if desc:
            out.append("   " + T.s(lang, "cond", d=T.desc_local(desc, lang)))
    elif intent == "umbrella":
        out.append(T.s(lang, "title_current", emoji=_emoji_for(desc), loc=loc, period=period))
        out.append("")
        if rain > 1 or any(k in desc for k in ("rain", "drizzle", "shower", "thunder")) or (prob or 0) >= 60:
            out.append(T.s(lang, "umb_yes"))
        elif any(k in desc for k in ("cloud", "overcast")) or (prob or 0) >= 30:
            out.append(T.s(lang, "umb_maybe"))
        else:
            out.append(T.s(lang, "umb_no"))
        if prob is not None:
            out.append(T.s(lang, "prob", p=f"{prob:.0f}"))
    elif intent == "wind":
        out.append(T.s(lang, "title_wind", loc=loc, period=period))
        out.append("")
        out.append("   " + T.wind_label(w["wind_kmh"], lang))
    else:   # current, humidity, feels_like
        out.append(T.s(lang, "title_current", emoji=_emoji_for(desc), loc=loc, period=period))
        out.append("")
        if w["temp"] is not None:
            if is_now:
                out.append(T.s(lang, "temp_feels", t=w["temp"], f=w["feels"]) if w["feels"] is not None
                           else T.s(lang, "temp", t=w["temp"]))
            elif w["temp_min"] is not None:
                out.append(T.s(lang, "temp_range", tmin=w["temp_min"], tmax=w["temp"]))
            else:
                out.append(T.s(lang, "temp_upto", tmax=w["temp"]))
        out.append(T.s(lang, "cond", d=T.desc_local(desc, lang)))
        if w["hum"] is not None:
            out.append(T.s(lang, "hum", h=f"{w['hum']:.0f}"))
        out.append(T.s(lang, "wind", w=T.wind_label(w["wind_kmh"], lang)))
        if rain:
            out.append(T.s(lang, "rain_now", mm=rain) if is_now else T.s(lang, "rain_peak", r=T.rain_label(rain, lang)))
        if prob is not None:
            out.append(T.s(lang, "prob", p=f"{prob:.0f}"))
        if intent == "humidity":
            out.append("")
            out.append(T.s(lang, "hum_line", h=f"{w['hum']:.0f}") if w["hum"] is not None else T.s(lang, "hum_none"))

    if note:
        out.append("")
        out.append(T.s(lang, "fallback_note"))
    out.append(more)
    out.append("")
    out.append(T.s(lang, "source", src=w["src"]))
    return "\n".join(x for x in out if x is not None)


# ─────────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────────────────────────────────────
def _shorten(text: str) -> str:
    """Feature 9 — WhatsApp/SMS-style concise answer."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    keep = []
    for l in lines:
        low = l.lower()
        if any(k in low for k in ("source:", "📡", "tip:", "ℹ️", "always follow",
                                   "based on rainfall only")):
            continue
        keep.append(l)
    head = keep[0] if keep else text.split(".")[0]
    body = ""
    import re as _re
    for l in keep[1:]:
        m = _re.search(r"(suitability \d+/100[^\n]*|Best slot[^\n]*|departure window[^\n]*|"
                       r"IRRIGATE[^—\n]*|Rain window[^\n]*|FROST RISK[^\n]*|AQI \d+[^\n]*)", l, _re.I)
        if m:
            body = m.group(1)
            break
    out = head.rstrip(".")
    if body:
        out += ". " + body.rstrip(".") + "."
    return out[:300]


def generate_response(intent: str, parsed: dict, weather_data: dict, alerts: Optional[list] = None,
                      short_mode: bool = False, crop: Optional[str] = None,
                      crop_stage: Optional[str] = None, prefs: Optional[dict] = None) -> str:
    weather_data = weather_data or {}
    lang = parsed.get("language", "en")
    location = parsed.get("location") or "your location"
    domain = parsed.get("domain", "general")
    time_range = parsed.get("time_range", "today")

    # ── new feature engines (activity planner, travel, crops, explain, compare, health) ──
    try:
        from services import features as _F
    except Exception:
        try:
            import features as _F
        except Exception:
            _F = None
    if _F is not None and intent in getattr(_F, "HANDLERS", {}):
        kw = {"crop": crop, "stage": crop_stage} if intent == "crop_calendar" else {}
        txt = _F.HANDLERS[intent](parsed, weather_data, location,
                                  (parsed.get("note") or "").strip(), **kw)
        return _shorten(txt) if short_mode else txt

    # social / non-weather intents
    if intent == "greeting":
        return _greeting_response(parsed.get("raw_query", ""), lang)
    if intent == "thanks":
        return _msg("thanks", lang)
    if intent == "bye":
        return _msg("bye", lang)
    if intent == "fallback":
        return _msg("fallback", lang)

    # ask for a place when we have neither a place nor any data
    has_data = any(weather_data.get(k) for k in ("current", "forecast", "alerts", "climate"))
    if parsed.get("needs_location") and not has_data:
        return _msg("ask_location", lang)

    # Hindi / Hinglish / Marathi replies for the most common intents (see i18n_replies.py)
    local = _local_response(intent, parsed, weather_data, lang)
    if local is not None:
        return local

    english = _generate_english(intent, parsed, weather_data, location, domain, time_range)
    if short_mode:
        return _shorten(english)
    T = _i18n()
    if T is not None and lang in T.SUPPORTED:
        english += "\n\n" + T.s(lang, "english_only")
    return english


def _generate_english(intent, parsed, weather_data, location, domain, time_range):
    if intent == "forecast":
        out = _forecast_response(weather_data.get("forecast", {}), location, time_range, domain, parsed)
        # if only "current" was loaded for a today-type question, still answer
        if out.startswith("Sorry") and weather_data.get("current"):
            w, note = _resolve(parsed, weather_data)
            return _current_response(w, location, domain, "current", parsed, note)
        return out
    if intent == "alerts":
        return _alerts_response(weather_data.get("alerts", []), location if parsed.get("location") else "")
    if intent == "climate":
        return _climate_response(weather_data.get("climate", {}), location, parsed)

    w, note = _resolve(parsed, weather_data)
    if intent == "rain":
        return _rain_response(w, note, location, parsed)
    if intent == "heatwave":
        return _heatwave_response(w, location)
    if intent == "cold_wave":
        return _cold_wave_response(w, location)
    if intent == "thunder":
        return _thunder_response(w, location)
    if intent == "wind":
        return _wind_response(w, location)
    if intent == "snow":
        return _snow_response(w, location)
    if intent == "fog":
        return _fog_response(w, location)
    if intent == "uv_index":
        return _uv_response(w, location)
    if intent == "advisory":
        return _advisory_response(w, location, parsed, weather_data.get("alerts", []), note)
    # current, umbrella, clothing, feels_like, humidity, outdoor, jogging, commute, plants
    return _current_response(w, location, domain, intent, parsed, note)


# ─────────────────────────────────────────────────────────────────────────────
# Quick command-line check:   python nlp.py "kal Pune mein barish hogi kya?"
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys
    text = " ".join(sys.argv[1:]) or "Will it rain in Mumbai tomorrow?"
    print(json.dumps(parse_query(text), indent=2, ensure_ascii=False))
