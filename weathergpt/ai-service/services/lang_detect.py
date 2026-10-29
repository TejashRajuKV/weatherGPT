"""
Step 1a — Language Detection
Uses Unicode script block ranges + Hinglish stopword check.
No external API. Returns (language_code, confidence, script).

Supported codes:
  en  — English
  hi  — Hindi (Devanagari)
  hi-Latn — Hinglish (Hindi in Latin script)
  mr  — Marathi (Devanagari, distinguished by stopwords)
  bn  — Bengali
  ta  — Tamil
  te  — Telugu
  kn  — Kannada
  ml  — Malayalam
  gu  — Gujarati
  pa  — Punjabi / Gurmukhi
  or  — Odia

Mixed scripts: dominant language wins; mixed flag is set so
the caller still runs entity extraction on all parts.
"""

import re
import unicodedata
import json
from pathlib import Path
from typing import Tuple

# ── Unicode script ranges ────────────────────────────────────────────────────
# Each entry: (start_codepoint, end_codepoint, language_code, script_name)
SCRIPT_RANGES = [
    (0x0900, 0x097F, "hi",    "Devanagari"),   # Hindi / Marathi share script
    (0x0980, 0x09FF, "bn",    "Bengali"),
    (0x0A00, 0x0A7F, "pa",    "Gurmukhi"),
    (0x0A80, 0x0AFF, "gu",    "Gujarati"),
    (0x0B00, 0x0B7F, "or",    "Odia"),
    (0x0B80, 0x0BFF, "ta",    "Tamil"),
    (0x0C00, 0x0C7F, "te",    "Telugu"),
    (0x0C80, 0x0CFF, "kn",    "Kannada"),
    (0x0D00, 0x0D7F, "ml",    "Malayalam"),
]

# ── Marathi-specific Devanagari stopwords (not common in Hindi) ──────────────
MARATHI_MARKERS = {
    "आहे","आहेत","आहे","नाही","आज","उद्या","पाऊस","वारा","ढग","पाणी",
    "हवामान","तापमान","थंडी","उन्हाळा","पावसाळा","हिवाळा","झाले","असेल",
    "सांगा","काय","कधी","कुठे","किती","कसे","कसा","कशी","होईल","होणार",
}

HINDI_MARKERS = {
    "है","हैं","हो","था","थी","थे","का","की","के","में","और","या","लेकिन",
    "कल","आज","अभी","कैसा","कैसी","कहां","कितना","बारिश","गर्मी","ठंडी",
    "मौसम","तापमान","हवा","धुंध","बादल","तूफान","बाढ़","चक्रवात",
}

# ── Load Hinglish stopwords ──────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent / "data"

def _load_hinglish_words() -> set:
    try:
        with open(_DATA_DIR / "stopwords_hinglish.json", encoding="utf-8") as f:
            return set(json.load(f).get("words", []))
    except Exception:
        return {"kya","hai","kal","aaj","barish","mausam","garmi","thandi","hawa"}

HINGLISH_WORDS = _load_hinglish_words()

# ── Script character counter ─────────────────────────────────────────────────

def _script_counts(text: str) -> dict:
    """Count characters per script range."""
    counts = {}
    for ch in text:
        cp = ord(ch)
        for start, end, lang, _ in SCRIPT_RANGES:
            if start <= cp <= end:
                counts[lang] = counts.get(lang, 0) + 1
                break
    return counts


def _latin_char_count(text: str) -> int:
    return sum(1 for ch in text if "LATIN" in unicodedata.name(ch, ""))


# ── Hinglish detector ────────────────────────────────────────────────────────

def _hinglish_score(text: str) -> float:
    """Return fraction of words that are Hinglish stopwords."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in HINGLISH_WORDS)
    return hits / len(words)


def _marathi_vs_hindi(text: str) -> Tuple[str, float]:
    """Disambiguate Devanagari text between Marathi and Hindi."""
    mr_hits = sum(1 for w in text.split() if w in MARATHI_MARKERS)
    hi_hits = sum(1 for w in text.split() if w in HINDI_MARKERS)
    if mr_hits > hi_hits:
        conf = min(0.95, 0.6 + 0.1 * mr_hits)
        return "mr", conf
    if hi_hits > mr_hits:
        conf = min(0.95, 0.6 + 0.1 * hi_hits)
        return "hi", conf
    # Default to Hindi when ambiguous — more common
    return "hi", 0.55


# ── Public API ───────────────────────────────────────────────────────────────

def detect_language(text: str) -> dict:
    """
    Returns:
    {
      "lang": "en" | "hi" | "hi-Latn" | "mr" | "bn" | "ta" | "te" |
              "kn" | "ml" | "gu" | "pa" | "or",
      "confidence": float 0-1,
      "script": "Latin" | "Devanagari" | ...,
      "is_mixed": bool,
      "details": {lang: char_count, ...}
    }
    """
    if not text or not text.strip():
        return {"lang": "en", "confidence": 0.5, "script": "Latin",
                "is_mixed": False, "details": {}}

    script_counts = _script_counts(text)
    latin_count   = _latin_char_count(text)
    total_alpha   = sum(script_counts.values()) + latin_count

    if total_alpha == 0:
        return {"lang": "en", "confidence": 0.5, "script": "Latin",
                "is_mixed": False, "details": {}}

    is_mixed = len(script_counts) > 1 or (script_counts and latin_count > 3)

    # ── Dominant Indic script ────────────────────────────────────────────────
    if script_counts:
        dominant_lang = max(script_counts, key=script_counts.get)
        dominant_count = script_counts[dominant_lang]
        dominant_fraction = dominant_count / total_alpha

        if dominant_lang == "hi":
            # Disambiguate Hindi vs Marathi
            lang, conf = _marathi_vs_hindi(text)
            return {
                "lang": lang,
                "confidence": round(conf * dominant_fraction + 0.3, 3),
                "script": "Devanagari",
                "is_mixed": is_mixed,
                "details": script_counts,
            }

        script_name = next(
            (s for start, end, l, s in SCRIPT_RANGES if l == dominant_lang), "Indic"
        )
        conf = min(0.98, 0.55 + 0.45 * dominant_fraction)
        return {
            "lang": dominant_lang,
            "confidence": round(conf, 3),
            "script": script_name,
            "is_mixed": is_mixed,
            "details": script_counts,
        }

    # ── Pure Latin script — English vs Hinglish ──────────────────────────────
    hi_score = _hinglish_score(text)

    if hi_score >= 0.35:
        return {
            "lang": "hi-Latn",
            "confidence": round(min(0.92, 0.55 + hi_score), 3),
            "script": "Latin",
            "is_mixed": False,
            "details": {"hinglish_word_ratio": round(hi_score, 3)},
        }

    return {
        "lang": "en",
        "confidence": round(min(0.98, 0.6 + (1 - hi_score) * 0.38), 3),
        "script": "Latin",
        "is_mixed": False,
        "details": {},
    }
