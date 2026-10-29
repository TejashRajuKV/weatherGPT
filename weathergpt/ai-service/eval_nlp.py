#!/usr/bin/env python3
"""
WeatherGPT NLU evaluation
=========================
Scores nlp.parse_query() on a labelled question set: intent, place, time range and
language detection, per language, with and without the trained intent model.

    python eval_nlp.py                 # rules + model (if models/intent_model.joblib exists)
    python eval_nlp.py --no-model      # rules only
    python eval_nlp.py --compare       # both, side by side
    python eval_nlp.py --failures      # also list every miss
    python eval_nlp.py --csv my_questions.csv   # evaluate your own set (see format below)

Each test is (question, expected intent(s), expected place, expected time, expected language).
Use None for "don't check". An intent may be a list when several answers are acceptable
(for example "current" and "forecast" give the same reply once a day is given).

CSV format for --csv:  text,language,intent,location,time_range   (last two optional)

Add real questions from real users here — that is what makes the numbers trustworthy.
The built-in set below was written by hand, separately from the training data, but by
the same author, so treat it as a smoke test rather than a final score.
"""
import argparse
import csv
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nlp  # noqa: E402

CUR_FC = ["current", "forecast"]

# (question, intent or [intents], place, time_range, language)
TESTS = [
    # ── English ────────────────────────────────────────────────────────────
    ("What's the weather like in Mumbai today?", "current", "Mumbai", "today", "en"),
    ("Will it rain in Delhi tomorrow?", "rain", "Delhi", "tomorrow", "en"),
    ("Is it going to rain this weekend in Pune", "rain", "Pune", "weekend", "en"),
    ("7 day forecast for Chennai", "forecast", "Chennai", "next_7_days", "en"),
    ("Do I need an umbrella in Kolkata today", "umbrella", "Kolkata", "today", "en"),
    ("how windy is it in Jaipur", "wind", "Jaipur", "today", "en"),
    ("humidity in Lucknow tomorrow", "humidity", "Lucknow", "tomorrow", "en"),
    ("Is there a cyclone warning for Odisha", "alerts", "Odisha", None, "en"),
    ("Should I spray my crops in Nashik tomorrow", "advisory", "Nashik", "tomorrow", "en"),
    ("is it safe to go fishing in Goa today", "advisory", "Goa", "today", "en"),
    ("will it snow in Manali tomorrow", "snow", "Manali", "tomorrow", "en"),
    ("heatwave in Nagpur", "heatwave", "Nagpur", None, "en"),
    ("is there fog in Delhi tomorrow morning", "fog", "Delhi", "tomorrow", "en"),
    ("what should I wear in Shimla tonight", "clothing", "Shimla", "tonight", "en"),
    ("average rainfall in Mumbai last 10 years", "climate", "Mumbai", "last_10_years", "en"),
    ("any weather alerts for Kochi", "alerts", "Kochi", None, "en"),
    ("thunderstorm in Hyderabad tonight", "thunder", "Hyderabad", "tonight", "en"),
    ("what is the UV index in Bangalore", "uv_index", "Bangalore", None, "en"),
    ("good morning", "greeting", None, None, "en"),
    ("thanks a lot", "thanks", None, None, "en"),
    ("goodbye", "bye", None, None, "en"),
    ("tell me a joke", "fallback", None, None, "en"),
    ("weather in Ooty in 3 days", CUR_FC, "Ooty", "in_3_days", "en"),
    ("can I go jogging in Pune tomorrow morning", "jogging", "Pune", "tomorrow", "en"),
    ("should I water my plants in Bhopal today", "plants", "Bhopal", "today", "en"),
    ("how hot will it be in Jaipur next week", ["feels_like", "forecast", "current"], "Jaipur", "next_week", "en"),
    ("is it a good day for a picnic in Goa this weekend", "outdoor", "Goa", "weekend", "en"),
    ("will it be hot in Chennai day after tomorrow", CUR_FC + ["feels_like"], "Chennai", "day_after_tomorrow", "en"),
    ("weather near me", "current", None, "today", "en"),
    ("Is it raining in Bangalore right now", "rain", "Bangalore", "now", "en"),
    ("pune weather", "current", "Pune", None, "en"),
    ("Mumbai", "current", "Mumbai", None, "en"),
    ("will it rain in Delhi and Mumbai tomorrow", "rain", "Delhi", "tomorrow", "en"),
    ("what is the temperature in Amritsar tonight", "current", "Amritsar", "tonight", "en"),
    ("cold wave in Srinagar", "cold_wave", "Srinagar", None, "en"),
    ("flood risk in Patna", "advisory", "Patna", None, "en"),
    ("should I sow wheat in Ludhiana this week", "advisory", "Ludhiana", "this_week", "en"),
    ("is it safe to fly from Delhi to Mumbai today", "advisory", "Delhi", "today", "en"),
    ("who are you", "greeting", None, None, "en"),
    ("what's the weather tomorow in hydrabad", "current", "Hyderabad", "tomorrow", "en"),
    ("any chance of flooding near Chennai this week", ["advisory", "alerts"], "Chennai", "this_week", "en"),
    ("will I need a jacket in Dehradun tomorrow", "clothing", "Dehradun", "tomorrow", "en"),
    # ── Hinglish ───────────────────────────────────────────────────────────
    ("kal pune mein barish hogi kya", "rain", "Pune", "tomorrow", "hi-Latn"),
    ("aaj mumbai ka mausam kaisa hai", "current", "Mumbai", "today", "hi-Latn"),
    ("delhi mein abhi kitni garmi hai", ["current", "feels_like"], "Delhi", "now", "hi-Latn"),
    ("kya mujhe kal chhata le jana chahiye", "umbrella", None, "tomorrow", "hi-Latn"),
    ("jaipur mein tez hawa chalegi kya", "wind", "Jaipur", None, "hi-Latn"),
    ("lucknow mein kohra hai kya", "fog", "Lucknow", None, "hi-Latn"),
    ("agle 5 din ka mausam nagpur", "forecast", "Nagpur", "next_5_days", "hi-Latn"),
    ("is hafte patna mein barish hogi kya", "rain", "Patna", "this_week", "hi-Latn"),
    ("chennai mein chakravat ki chetavani hai kya", "alerts", "Chennai", None, "hi-Latn"),
    ("kal kolkata mein mausam kaisa rahega", CUR_FC, "Kolkata", "tomorrow", "hi-Latn"),
    ("indore mein humidity kitni hai", "humidity", "Indore", None, "hi-Latn"),
    ("kya aaj bhopal mein fasal par spray kar sakte hain", "advisory", "Bhopal", "today", "hi-Latn"),
    ("namaste", "greeting", None, None, "hi-Latn"),
    ("dhanyavad", "thanks", None, None, "hi-Latn"),
    ("alvida", "bye", None, None, "hi-Latn"),
    ("mujhe gaana sunao", "fallback", None, None, "hi-Latn"),
    ("manali mein barf giregi kya", "snow", "Manali", None, "hi-Latn"),
    ("parso goa mein barish hogi kya", "rain", "Goa", "day_after_tomorrow", "hi-Latn"),
    ("nashik mein aaj bijli girne ka khatra hai kya", "thunder", "Nashik", "today", "hi-Latn"),
    ("pichhle 10 saal ki barish ka record pune", "climate", "Pune", "last_10_years", "hi-Latn"),
    ("aaj raat surat mein barish hogi kya", "rain", "Surat", "tonight", "hi-Latn"),
    ("ooty mein kal barish hogi", "rain", "Ooty", "tomorrow", "hi-Latn"),
    ("kal subah daudne ke liye mausam kaisa hai pune", "jogging", "Pune", "tomorrow", "hi-Latn"),
    ("mausam", "current", None, None, "hi-Latn"),
    ("shimla mein bahut thand hai kya aaj", ["feels_like", "cold_wave", "current"], "Shimla", "today", "hi-Latn"),
    # ── Hindi (Devanagari) ────────────────────────────────────────────────
    ("आज मुंबई का मौसम कैसा है", "current", "Mumbai", "today", "hi"),
    ("कल दिल्ली में बारिश होगी क्या", "rain", "Delhi", "tomorrow", "hi"),
    ("पुणे में तेज हवा चलेगी क्या", "wind", "Pune", None, "hi"),
    ("क्या मुझे कल छाता ले जाना चाहिए", "umbrella", None, "tomorrow", "hi"),
    ("जयपुर में कोहरा है क्या", "fog", "Jaipur", None, "hi"),
    ("अगले 5 दिन का मौसम लखनऊ", "forecast", "Lucknow", "next_5_days", "hi"),
    ("चेन्नई में चक्रवात की चेतावनी है क्या", "alerts", "Chennai", None, "hi"),
    ("मनाली में बर्फबारी होगी क्या", "snow", "Manali", None, "hi"),
    ("आज भोपाल में उमस कितनी है", "humidity", "Bhopal", "today", "hi"),
    ("क्या कल नागपुर में फसल पर छिड़काव करना ठीक रहेगा", "advisory", "Nagpur", "tomorrow", "hi"),
    ("नमस्ते", "greeting", None, None, "hi"),
    ("धन्यवाद", "thanks", None, None, "hi"),
    ("अलविदा", "bye", None, None, "hi"),
    ("मुझे एक चुटकुला सुनाओ", "fallback", None, None, "hi"),
    ("शिमला में शीतलहर है क्या", "cold_wave", "Shimla", None, "hi"),
    ("दिल्ली में लू चल रही है क्या", "heatwave", "Delhi", None, "hi"),
    ("आज रात पटना में बिजली गिरने का खतरा है क्या", "thunder", "Patna", "tonight", "hi"),
    ("पिछले 10 साल की बारिश का रिकॉर्ड पुणे", "climate", "Pune", "last_10_years", "hi"),
    ("परसों कोलकाता में बारिश होगी क्या", "rain", "Kolkata", "day_after_tomorrow", "hi"),
    ("अभी इंदौर में तापमान कितना है", "current", "Indore", "now", "hi"),
    # ── Marathi ────────────────────────────────────────────────────────────
    ("उद्या पुण्यात पाऊस पडेल का", "rain", "Pune", "tomorrow", "mr"),
    ("आज मुंबईचे हवामान कसे आहे", "current", "Mumbai", "today", "mr"),
    ("नाशिक मध्ये आज वारा किती आहे", "wind", "Nashik", "today", "mr"),
    ("उद्या छत्री घ्यावी का", "umbrella", None, "tomorrow", "mr"),
    ("कोल्हापूर मध्ये धुके आहे का", "fog", "Kolhapur", None, "mr"),
    ("नागपूर साठी चक्रीवादळाचा इशारा आहे का", "alerts", "Nagpur", None, "mr"),
    ("नमस्कार", "greeting", None, None, None),   # script alone cannot tell Hindi from Marathi,
    ("धन्यवाद", "thanks", None, None, None),   # identical in Hindi and Marathi
    ("गेल्या 10 वर्षांचा पाऊस पुणे", "climate", "Pune", "last_10_years", "mr"),
    ("सोलापूर मध्ये आज दमट हवामान आहे का", "humidity", "Solapur", "today", "mr"),
    ("उद्या औरंगाबाद मध्ये फवारणी करावी का", "advisory", "Aurangabad", "tomorrow", "mr"),
    ("कोल्हापूर मध्ये आज वादळ येईल का", "thunder", "Kolhapur", "today", "mr"),
    # ── Other Indian languages ────────────────────────────────────────────
    ("சென்னையில் இன்று மழை பெய்யுமா", "rain", "Chennai", "today", "ta"),
    ("மதுரை வானிலை எப்படி", "current", "Madurai", None, "ta"),
    ("హైదరాబాద్ లో రేపు వర్షం పడుతుందా", "rain", "Hyderabad", "tomorrow", "te"),
    ("విజయవాడ వాతావరణం ఎలా ఉంది", "current", "Vijayawada", None, "te"),
    ("আজ কলকাতায় বৃষ্টি হবে?", "rain", "Kolkata", "today", "bn"),
    ("কলকাতার আবহাওয়া কেমন", "current", "Kolkata", None, "bn"),
    ("ಬೆಂಗಳೂರು ನಾಳೆ ಮಳೆ", "rain", "Bengaluru", "tomorrow", "kn"),
    ("ಮೈಸೂರು ಹವಾಮಾನ ಹೇಗಿದೆ", "current", "Mysuru", None, "kn"),
    ("കൊച്ചി നാളെ മഴ", "rain", "Kochi", "tomorrow", "ml"),
    ("કાલે અમદાવાદમાં વરસાદ", "rain", "Ahmedabad", "tomorrow", "gu"),
    ("સુરત હવામાન", "current", "Surat", None, "gu"),
]


def load_csv(path):
    tests = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tests.append(((r.get("text") or "").strip(), (r.get("intent") or "").strip(),
                          (r.get("location") or "").strip() or None,
                          (r.get("time_range") or "").strip() or None,
                          (r.get("language") or "").strip() or None))
    return [t for t in tests if t[0] and t[1]]


def _ok_intent(got, exp):
    return got in exp if isinstance(exp, (list, tuple)) else got == exp


def _ok_time(got, exp):
    if exp is None:
        return True
    return got.startswith("date:") if exp == "date" else got == exp


def run(tests, use_model: bool):
    nlp._ML.update({"tried": not use_model, "clf": None})
    stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))   # lang -> metric -> [ok, n]
    fails = []
    t0 = time.perf_counter()
    for q, exp_i, exp_loc, exp_t, exp_lang in tests:
        p = nlp.parse_query(q)
        lang = exp_lang or "?"
        checks = {"intent": _ok_intent(p["intent"], exp_i)}
        if exp_loc is not None:
            checks["place"] = p["location"] == exp_loc
        if exp_t is not None:
            checks["time"] = _ok_time(p["time_range"], exp_t)
        if exp_lang is not None:
            checks["language"] = p["language"] == exp_lang
        for k, ok in checks.items():
            for key in (lang, "ALL"):
                stats[key][k][0] += int(ok)
                stats[key][k][1] += 1
        if not all(checks.values()):
            fails.append((q, exp_i, exp_loc, exp_t, exp_lang, p, [k for k, v in checks.items() if not v]))
    ms = (time.perf_counter() - t0) * 1000 / max(len(tests), 1)
    return stats, fails, ms


def _pct(c):
    return f"{c[0] / c[1]:6.1%}" if c[1] else "   -  "


def report(title, stats, ms, n):
    print(f"\n{title}   ({n} questions, {ms:.1f} ms per question)")
    print(f"  {'language':9} {'intent':>8} {'place':>8} {'time':>8} {'language':>9}   n")
    order = ["en", "hi-Latn", "hi", "mr", "ta", "te", "bn", "kn", "ml", "gu"]
    keys = [k for k in order if k in stats] + [k for k in stats if k not in order and k != "ALL"] + ["ALL"]
    for k in keys:
        s = stats[k]
        print(f"  {k:9} {_pct(s['intent']):>8} {_pct(s['place']):>8} {_pct(s['time']):>8} {_pct(s['language']):>9}   {s['intent'][1]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true", help="rules only")
    ap.add_argument("--compare", action="store_true", help="rules-only vs rules+model")
    ap.add_argument("--failures", action="store_true", help="list every failing question")
    ap.add_argument("--csv", help="evaluate your own labelled CSV instead of the built-in set")
    args = ap.parse_args()

    tests = load_csv(args.csv) if args.csv else TESTS
    modes = [("Rules only", False), ("Rules + trained model", True)] if args.compare else \
            [("Rules only", False)] if args.no_model else [("Rules + trained model", True)]
    last_fails = []
    for title, use_model in modes:
        stats, fails, ms = run(tests, use_model)
        if use_model and nlp._ml_predict("test") is None:
            title += "  [model file not found — rules only]"
        report(title, stats, ms, len(tests))
        last_fails = fails
    if args.failures:
        print(f"\nFailures ({len(last_fails)}):")
        for q, ei, el, et, elang, p, bad in last_fails:
            print(f"  ✗ {q}")
            print(f"      failed: {', '.join(bad)}")
            print(f"      expected intent={ei} place={el} time={et} lang={elang}")
            print(f"      got      intent={p['intent']} ({p['intent_source']}) place={p['location']} time={p['time_range']} lang={p['language']}")


if __name__ == "__main__":
    main()
