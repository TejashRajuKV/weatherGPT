"""
Step 1b — Text Normalization
Pipeline:
  1. Unicode NFC
  2. Indic digits → ASCII digits
  3. Lowercase
  4. Collapse repeated letters  (baaarish → barish, sooooo → so)
  5. Remove punctuation (keep hyphens inside words, keep ?)
  6. Expand contractions
  7. Synonym replacement via data/synonyms.json
  8. Strip extra whitespace

Returns the normalized string ready for intent + entity matching.
"""

import re
import unicodedata
import json
from pathlib import Path
from functools import lru_cache

_DATA_DIR = Path(__file__).parent.parent / "data"

# ── Indic digit maps ─────────────────────────────────────────────────────────
# Maps Unicode Indic digit → ASCII digit for each script
_INDIC_DIGIT_MAPS = {
    # Devanagari (Hindi, Marathi)
    "\u0966": "0", "\u0967": "1", "\u0968": "2", "\u0969": "3",
    "\u096A": "4", "\u096B": "5", "\u096C": "6", "\u096D": "7",
    "\u096E": "8", "\u096F": "9",
    # Bengali
    "\u09E6": "0", "\u09E7": "1", "\u09E8": "2", "\u09E9": "3",
    "\u09EA": "4", "\u09EB": "5", "\u09EC": "6", "\u09ED": "7",
    "\u09EE": "8", "\u09EF": "9",
    # Gujarati
    "\u0AE6": "0", "\u0AE7": "1", "\u0AE8": "2", "\u0AE9": "3",
    "\u0AEA": "4", "\u0AEB": "5", "\u0AEC": "6", "\u0AED": "7",
    "\u0AEE": "8", "\u0AEF": "9",
    # Gurmukhi (Punjabi)
    "\u0A66": "0", "\u0A67": "1", "\u0A68": "2", "\u0A69": "3",
    "\u0A6A": "4", "\u0A6B": "5", "\u0A6C": "6", "\u0A6D": "7",
    "\u0A6E": "8", "\u0A6F": "9",
    # Tamil
    "\u0BE6": "0", "\u0BE7": "1", "\u0BE8": "2", "\u0BE9": "3",
    "\u0BEA": "4", "\u0BEB": "5", "\u0BEC": "6", "\u0BED": "7",
    "\u0BEE": "8", "\u0BEF": "9",
    # Telugu
    "\u0C66": "0", "\u0C67": "1", "\u0C68": "2", "\u0C69": "3",
    "\u0C6A": "4", "\u0C6B": "5", "\u0C6C": "6", "\u0C6D": "7",
    "\u0C6E": "8", "\u0C6F": "9",
    # Kannada
    "\u0CE6": "0", "\u0CE7": "1", "\u0CE8": "2", "\u0CE9": "3",
    "\u0CEA": "4", "\u0CEB": "5", "\u0CEC": "6", "\u0CED": "7",
    "\u0CEE": "8", "\u0CEF": "9",
    # Malayalam
    "\u0D66": "0", "\u0D67": "1", "\u0D68": "2", "\u0D69": "3",
    "\u0D6A": "4", "\u0D6B": "5", "\u0D6C": "6", "\u0D6D": "7",
    "\u0D6E": "8", "\u0D6F": "9",
    # Odia
    "\u0B66": "0", "\u0B67": "1", "\u0B68": "2", "\u0B69": "3",
    "\u0B6A": "4", "\u0B6B": "5", "\u0B6C": "6", "\u0B6D": "7",
    "\u0B6E": "8", "\u0B6F": "9",
}
_DIGIT_TRANS = str.maketrans(_INDIC_DIGIT_MAPS)

# ── Contractions ─────────────────────────────────────────────────────────────
_CONTRACTIONS = {
    "won't": "will not", "can't": "cannot", "it's": "it is",
    "isn't": "is not",   "aren't": "are not", "wasn't": "was not",
    "what's": "what is", "how's": "how is",   "there's": "there is",
    "i'll": "i will",    "i'm": "i am",       "i'd": "i would",
    "you'll": "you will","they'll": "they will","we'll": "we will",
    "don't": "do not",   "doesn't": "does not","didn't": "did not",
    "shouldn't": "should not", "wouldn't": "would not",
    "couldn't": "could not",
}

# ── Filler words to strip ─────────────────────────────────────────────────────
_FILLERS = re.compile(
    r'\b(um+|uh+|hmm+|err+|like|you know|i mean|actually|basically|'
    r'please|kindly|bhai|yaar|boss|sir|madam|dude|buddy|re\b)\b',
    re.IGNORECASE
)

# ── Load synonym table ────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_synonyms() -> dict:
    """Returns {surface_form: canonical_english_token}."""
    try:
        with open(_DATA_DIR / "synonyms.json", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    mapping = {}
    for canonical, variants in raw.items():
        if canonical.startswith("_"):
            continue
        for v in variants:
            mapping[v.lower()] = canonical
    return mapping


def _apply_synonyms(text: str) -> str:
    """Replace known synonym variants with their canonical English form."""
    synonyms = _load_synonyms()
    # Sort by length descending so longer phrases match before shorter subsets
    for variant in sorted(synonyms, key=len, reverse=True):
        if variant in text:
            text = text.replace(variant, synonyms[variant])
    return text


# ── Repeated-letter collapser ─────────────────────────────────────────────────
# Keeps max 2 of any repeated character (sooo→so, baaarish→barish)
_REPEAT = re.compile(r'(.)\1{2,}')


def _collapse_repeats(text: str) -> str:
    return _REPEAT.sub(r'\1\1', text)


# ── Main normalizer ───────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """
    Full normalization pipeline.
    Input : raw user message (any supported language/script)
    Output: cleaned, lowercased, synonym-mapped string for NLU
    """
    if not text:
        return ""

    # 1. Unicode NFC (canonical composition — consistent code points)
    text = unicodedata.normalize("NFC", text)

    # 2. Indic digits → ASCII
    text = text.translate(_DIGIT_TRANS)

    # 3. Lowercase
    text = text.lower()

    # 4. Expand contractions (English)
    for contraction, expansion in _CONTRACTIONS.items():
        text = text.replace(contraction, expansion)

    # 5. Collapse repeated letters
    text = _collapse_repeats(text)

    # 6. Synonym replacement  (before punctuation strip so multi-word forms work)
    text = _apply_synonyms(text)

    # 7. Remove punctuation — keep hyphens inside words, keep digits
    #    Keep Indic characters intact (don't strip non-ASCII blindly)
    text = re.sub(r'[^\w\s\u0900-\u0D7F\u0A00-\u0A7F\u0980-\u09FF-]', ' ', text)

    # 8. Remove filler words (Latin only — won't affect Indic scripts)
    text = _FILLERS.sub(' ', text)

    # 9. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text
