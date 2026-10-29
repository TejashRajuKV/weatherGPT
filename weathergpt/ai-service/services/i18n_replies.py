"""
WeatherGPT localised reply text  (Hindi, Hinglish, Marathi)
===========================================================
Pure data + tiny helpers. No imports from nlp.py, so a translator can review or
extend this file without touching any logic.

  * Languages: "hi" (Hindi, Devanagari), "hi-Latn" (Hinglish), "mr" (Marathi, Devanagari)
  * Covered replies: current weather, rain, umbrella, forecast, wind, humidity, alerts
  * Everything else still answers in English, with a one-line note in the user's language.

PLEASE HAVE A NATIVE SPEAKER REVIEW EVERY STRING. They are written in plain, everyday
language, but have not been checked by a native speaker. To add a language, copy one
block in STRINGS / PERIODS / WEEKDAYS / DESC / RAIN / WIND and translate it.
"""
import re
from datetime import date

SUPPORTED = ("hi", "hi-Latn", "mr")

# ── Fixed sentences ──────────────────────────────────────────────────────────
STRINGS = {
    "hi": {
        "your_place": "आपकी जगह",
        "title_current": "{emoji} {loc} का मौसम — {period}:",
        "title_wind": "💨 {loc} में हवा — {period}:",
        "temp": "🌡  तापमान   : {t}°C",
        "temp_feels": "🌡  तापमान   : {t}°C (महसूस: {f}°C)",
        "temp_range": "🌡  तापमान   : {tmin}°C – {tmax}°C",
        "temp_upto": "🌡  तापमान   : अधिकतम {tmax}°C",
        "cond": "🌤  स्थिति    : {d}",
        "hum": "💧  नमी       : {h}%",
        "wind": "💨  हवा       : {w}",
        "rain_now": "🌧  बारिश (1 घंटा) : {mm} मिमी",
        "rain_peak": "🌧  बारिश     : {r}",
        "prob": "☔  बारिश की संभावना : {p}%",
        "source": "📡  स्रोत: {src}",
        "unavailable": "माफ़ कीजिए, {loc} का मौसम डेटा नहीं मिल सका। कृपया जगह का नाम जाँचकर दोबारा पूछें।",
        "fallback_note": "ℹ️  इस समय का पूर्वानुमान उपलब्ध नहीं था, इसलिए अभी की स्थिति दिखाई गई है।",
        "english_only": "ℹ️  इस सवाल का पूरा जवाब अभी सिर्फ़ अंग्रेज़ी में उपलब्ध है।",
        "more_places": "💡  आपने {others} का भी ज़िक्र किया। उसके लिए अलग से पूछें।",
        "rain_yes": "🌧  हाँ, {loc} में {period} बारिश की संभावना है।",
        "rain_maybe": "🌦  {loc} में {period} थोड़ी बारिश हो सकती है।",
        "rain_no": "☀️  {loc} में {period} बारिश की कोई खास संभावना नहीं है।",
        "rain_amount_peak": "{r} (सबसे ज़्यादा वाले दिन)",
        "umb_yes": "✅ हाँ, छाता साथ रखें — बारिश की संभावना है।",
        "umb_maybe": "🌂 शायद छाता रख लें — आसमान में बादल हैं।",
        "umb_no": "☀️ छाते की ज़रूरत नहीं — बारिश की उम्मीद नहीं है।",
        "hum_line": "💦  नमी {h}% है।",
        "hum_none": "💦  इस अवधि के लिए नमी का डेटा उपलब्ध नहीं है।",
        "fc_title_one": "📅 {loc} का पूर्वानुमान — {period}:",
        "fc_title_many": "📅 {loc} का पूर्वानुमान — {period}:",
        "fc_none": "माफ़ कीजिए, {period} के लिए पूर्वानुमान उपलब्ध नहीं है। {n} दिन तक का पूर्वानुमान देख सकते हैं।",
        "fc_nodata": "माफ़ कीजिए, {loc} का पूर्वानुमान नहीं मिल सका।",
        "fc_day": "📅 {day}  {emoji} {d}",
        "fc_day2": "     🌡 {tmax}°C / {tmin}°C   🌧 {r}   💨 {w}",
        "alert_none": "✅  {loc} के पास अभी कोई सक्रिय मौसम चेतावनी नहीं है।\n\nसुरक्षित रहें और बीच-बीच में अपडेट देखते रहें।",
        "alert_none_noloc": "✅  अभी कोई सक्रिय मौसम चेतावनी नहीं है।\n\nसुरक्षित रहें और बीच-बीच में अपडेट देखते रहें।",
        "alert_head": "⚠️  {loc} के पास सक्रिय मौसम चेतावनियाँ:",
        "alert_head_noloc": "⚠️  सक्रिय मौसम चेतावनियाँ:",
        "alert_source": "   📡 स्रोत: {src}",
        "alert_foot": "हमेशा अपने स्थानीय आपदा प्रबंधन प्राधिकरण के निर्देशों का पालन करें।",
        "sev": {"low": "कम", "medium": "मध्यम", "high": "उच्च", "extreme": "अत्यधिक"},
    },
    "hi-Latn": {
        "your_place": "aapki jagah",
        "title_current": "{emoji} {loc} ka mausam — {period}:",
        "title_wind": "💨 {loc} mein hawa — {period}:",
        "temp": "🌡  Tapman     : {t}°C",
        "temp_feels": "🌡  Tapman     : {t}°C (mehsoos: {f}°C)",
        "temp_range": "🌡  Tapman     : {tmin}°C – {tmax}°C",
        "temp_upto": "🌡  Tapman     : adhiktam {tmax}°C",
        "cond": "🌤  Sthiti     : {d}",
        "hum": "💧  Nami       : {h}%",
        "wind": "💨  Hawa       : {w}",
        "rain_now": "🌧  Barish (1 ghanta) : {mm} mm",
        "rain_peak": "🌧  Barish     : {r}",
        "prob": "☔  Barish ki sambhavna : {p}%",
        "source": "📡  Source: {src}",
        "unavailable": "Maaf kijiye, {loc} ka mausam data nahi mil saka. Kripya jagah ka naam check karke dobara poochiye.",
        "fallback_note": "ℹ️  Is samay ka forecast uplabdh nahi tha, isliye abhi ki sthiti dikhayi gayi hai.",
        "english_only": "ℹ️  Is sawaal ka poora jawab abhi sirf English mein uplabdh hai.",
        "more_places": "💡  Aapne {others} ka bhi zikr kiya. Uske liye alag se poochiye.",
        "rain_yes": "🌧  Haan, {loc} mein {period} barish ki sambhavna hai.",
        "rain_maybe": "🌦  {loc} mein {period} thodi barish ho sakti hai.",
        "rain_no": "☀️  {loc} mein {period} barish ki koi khaas sambhavna nahi hai.",
        "rain_amount_peak": "{r} (sabse zyada wale din)",
        "umb_yes": "✅ Haan, chhata saath rakhein — barish ki sambhavna hai.",
        "umb_maybe": "🌂 Shayad chhata rakh lein — aasman mein badal hain.",
        "umb_no": "☀️ Chhate ki zaroorat nahi — barish ki ummeed nahi hai.",
        "hum_line": "💦  Nami {h}% hai.",
        "hum_none": "💦  Is avadhi ke liye nami ka data uplabdh nahi hai.",
        "fc_title_one": "📅 {loc} ka forecast — {period}:",
        "fc_title_many": "📅 {loc} ka forecast — {period}:",
        "fc_none": "Maaf kijiye, {period} ke liye forecast uplabdh nahi hai. {n} din tak ka forecast dekh sakte hain.",
        "fc_nodata": "Maaf kijiye, {loc} ka forecast nahi mil saka.",
        "fc_day": "📅 {day}  {emoji} {d}",
        "fc_day2": "     🌡 {tmax}°C / {tmin}°C   🌧 {r}   💨 {w}",
        "alert_none": "✅  {loc} ke paas abhi koi active mausam chetavani nahi hai.\n\nSurakshit rahiye aur beech-beech mein update dekhte rahiye.",
        "alert_none_noloc": "✅  Abhi koi active mausam chetavani nahi hai.\n\nSurakshit rahiye aur beech-beech mein update dekhte rahiye.",
        "alert_head": "⚠️  {loc} ke paas active mausam chetavaniyan:",
        "alert_head_noloc": "⚠️  Active mausam chetavaniyan:",
        "alert_source": "   📡 Source: {src}",
        "alert_foot": "Hamesha apne local aapda prabandhan adhikaran ke nirdeshon ka palan karein.",
        "sev": {"low": "kam", "medium": "madhyam", "high": "ucch", "extreme": "atyadhik"},
    },
    "mr": {
        "your_place": "तुमचे ठिकाण",
        "title_current": "{emoji} {loc} चे हवामान — {period}:",
        "title_wind": "💨 {loc} मध्ये वारा — {period}:",
        "temp": "🌡  तापमान   : {t}°C",
        "temp_feels": "🌡  तापमान   : {t}°C (जाणवणारे: {f}°C)",
        "temp_range": "🌡  तापमान   : {tmin}°C – {tmax}°C",
        "temp_upto": "🌡  तापमान   : कमाल {tmax}°C",
        "cond": "🌤  स्थिती    : {d}",
        "hum": "💧  आर्द्रता  : {h}%",
        "wind": "💨  वारा      : {w}",
        "rain_now": "🌧  पाऊस (1 तास) : {mm} मिमी",
        "rain_peak": "🌧  पाऊस     : {r}",
        "prob": "☔  पावसाची शक्यता : {p}%",
        "source": "📡  स्रोत: {src}",
        "unavailable": "क्षमस्व, {loc} चा हवामान डेटा मिळू शकला नाही. कृपया ठिकाणाचे नाव तपासून पुन्हा विचारा.",
        "fallback_note": "ℹ️  त्या वेळेचा अंदाज उपलब्ध नव्हता, म्हणून सध्याची स्थिती दाखवली आहे.",
        "english_only": "ℹ️  या प्रश्नाचे पूर्ण उत्तर सध्या फक्त इंग्रजीत उपलब्ध आहे.",
        "more_places": "💡  तुम्ही {others} चाही उल्लेख केला. त्यासाठी वेगळे विचारा.",
        "rain_yes": "🌧  होय, {loc} मध्ये {period} पावसाची शक्यता आहे.",
        "rain_maybe": "🌦  {loc} मध्ये {period} थोडा पाऊस पडू शकतो.",
        "rain_no": "☀️  {loc} मध्ये {period} पावसाची विशेष शक्यता नाही.",
        "rain_amount_peak": "{r} (सर्वाधिक पावसाच्या दिवशी)",
        "umb_yes": "✅ होय, छत्री सोबत ठेवा — पावसाची शक्यता आहे.",
        "umb_maybe": "🌂 कदाचित छत्री घ्या — आकाशात ढग आहेत.",
        "umb_no": "☀️ छत्रीची गरज नाही — पावसाची अपेक्षा नाही.",
        "hum_line": "💦  आर्द्रता {h}% आहे.",
        "hum_none": "💦  या कालावधीसाठी आर्द्रतेचा डेटा उपलब्ध नाही.",
        "fc_title_one": "📅 {loc} चा अंदाज — {period}:",
        "fc_title_many": "📅 {loc} चा अंदाज — {period}:",
        "fc_none": "क्षमस्व, {period} साठी अंदाज उपलब्ध नाही. {n} दिवसांपर्यंतचा अंदाज पाहता येईल.",
        "fc_nodata": "क्षमस्व, {loc} चा अंदाज मिळू शकला नाही.",
        "fc_day": "📅 {day}  {emoji} {d}",
        "fc_day2": "     🌡 {tmax}°C / {tmin}°C   🌧 {r}   💨 {w}",
        "alert_none": "✅  {loc} जवळ सध्या कोणताही सक्रिय हवामान इशारा नाही.\n\nसुरक्षित राहा आणि अधूनमधून अपडेट पाहत राहा.",
        "alert_none_noloc": "✅  सध्या कोणताही सक्रिय हवामान इशारा नाही.\n\nसुरक्षित राहा आणि अधूनमधून अपडेट पाहत राहा.",
        "alert_head": "⚠️  {loc} जवळचे सक्रिय हवामान इशारे:",
        "alert_head_noloc": "⚠️  सक्रिय हवामान इशारे:",
        "alert_source": "   📡 स्रोत: {src}",
        "alert_foot": "नेहमी तुमच्या स्थानिक आपत्ती व्यवस्थापन प्राधिकरणाच्या सूचनांचे पालन करा.",
        "sev": {"low": "कमी", "medium": "मध्यम", "high": "उच्च", "extreme": "अत्यंत उच्च"},
    },
}

# ── Time phrases (fit into "{loc} में {period} बारिश ...") ───────────────────
PERIODS = {
    "hi": {"now": "अभी", "today": "आज", "tonight": "आज रात", "tomorrow": "कल", "day_after_tomorrow": "परसों",
           "weekend": "इस सप्ताहांत", "this_week": "इस हफ्ते", "next_week": "अगले हफ्ते", "yesterday": "बीते कल",
           "this_month": "आने वाले दिनों में", "next_n": "अगले {n} दिन", "in_n": "{n} दिन बाद", "date": "{wd} ({d}/{m})"},
    "hi-Latn": {"now": "abhi", "today": "aaj", "tonight": "aaj raat", "tomorrow": "kal", "day_after_tomorrow": "parso",
                "weekend": "is weekend", "this_week": "is hafte", "next_week": "agle hafte", "yesterday": "beete kal",
                "this_month": "aane wale dinon mein", "next_n": "agle {n} din", "in_n": "{n} din baad", "date": "{wd} ({d}/{m})"},
    "mr": {"now": "आत्ता", "today": "आज", "tonight": "आज रात्री", "tomorrow": "उद्या", "day_after_tomorrow": "परवा",
           "weekend": "या आठवड्याच्या शेवटी", "this_week": "या आठवड्यात", "next_week": "पुढच्या आठवड्यात",
           "yesterday": "काल", "this_month": "येत्या दिवसांत", "next_n": "पुढील {n} दिवस", "in_n": "{n} दिवसांनी",
           "date": "{wd} ({d}/{m})"},
}
WEEKDAYS = {   # Monday first
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
    "hi-Latn": ["Somvar", "Mangalvar", "Budhvar", "Guruvar", "Shukravar", "Shanivar", "Ravivar"],
    "mr": ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
}

# ── Sky description (matched against the English description, first match wins) ──
DESC = {
    "hi": [("thunder", "गरज के साथ बारिश"), ("snow", "बर्फबारी"), ("heavy rain|violent", "भारी बारिश"),
           ("moderate rain", "मध्यम बारिश"), ("light rain", "हल्की बारिश"), ("drizzle", "फुहारें"),
           ("shower", "बौछारें"), ("rain", "बारिश"), ("fog", "कोहरा"), ("mist|haze|smoke", "धुंध"),
           ("overcast", "घने बादल"), ("partly|scattered|few clouds", "आंशिक रूप से बादल"), ("broken|cloud", "बादल छाए हैं"),
           ("mainly clear", "लगभग साफ़ आसमान"), ("clear|sunny", "साफ़ आसमान")],
    "hi-Latn": [("thunder", "garaj ke saath barish"), ("snow", "barfbari"), ("heavy rain|violent", "bhaari barish"),
                ("moderate rain", "madhyam barish"), ("light rain", "halki barish"), ("drizzle", "phuhaarein"),
                ("shower", "bauchhaarein"), ("rain", "barish"), ("fog", "kohra"), ("mist|haze|smoke", "dhund"),
                ("overcast", "ghane badal"), ("partly|scattered|few clouds", "aanshik roop se badal"),
                ("broken|cloud", "badal chhaye hain"), ("mainly clear", "lagbhag saaf aasman"), ("clear|sunny", "saaf aasman")],
    "mr": [("thunder", "गडगडाटासह पाऊस"), ("snow", "बर्फवृष्टी"), ("heavy rain|violent", "मुसळधार पाऊस"),
           ("moderate rain", "मध्यम पाऊस"), ("light rain", "हलका पाऊस"), ("drizzle", "रिमझिम पाऊस"),
           ("shower", "पावसाच्या सरी"), ("rain", "पाऊस"), ("fog", "धुके"), ("mist|haze|smoke", "धुके / धुरकट"),
           ("overcast", "पूर्णपणे ढगाळ"), ("partly|scattered|few clouds", "अंशतः ढगाळ"), ("broken|cloud", "ढगाळ"),
           ("mainly clear", "जवळजवळ निरभ्र"), ("clear|sunny", "निरभ्र आकाश")],
}

# ── Rain amount (mm) and wind speed (km/h) labels ───────────────────────────
RAIN = {   # (upper limit mm, text) — {mm} is filled in
    "hi": [(0.0001, "कोई बारिश नहीं"), (2.5, "बहुत हल्की बारिश ({mm} मिमी)"), (7.5, "हल्की बारिश ({mm} मिमी)"),
           (35.5, "मध्यम बारिश ({mm} मिमी)"), (115.6, "भारी बारिश ({mm} मिमी) ⚠️"), (1e9, "बहुत भारी बारिश ({mm} मिमी) 🚨")],
    "hi-Latn": [(0.0001, "koi barish nahi"), (2.5, "bahut halki barish ({mm} mm)"), (7.5, "halki barish ({mm} mm)"),
                (35.5, "madhyam barish ({mm} mm)"), (115.6, "bhaari barish ({mm} mm) ⚠️"),
                (1e9, "bahut bhaari barish ({mm} mm) 🚨")],
    "mr": [(0.0001, "पाऊस नाही"), (2.5, "अगदी हलका पाऊस ({mm} मिमी)"), (7.5, "हलका पाऊस ({mm} मिमी)"),
           (35.5, "मध्यम पाऊस ({mm} मिमी)"), (115.6, "जोरदार पाऊस ({mm} मिमी) ⚠️"),
           (1e9, "अतिमुसळधार पाऊस ({mm} मिमी) 🚨")],
}
WIND = {   # (upper limit km/h, text) — {kmh} is filled in
    "hi": [(2, "शांत ({kmh} किमी/घंटा)"), (12, "हल्की हवा ({kmh} किमी/घंटा)"), (29, "मध्यम हवा ({kmh} किमी/घंटा)"),
           (50, "तेज हवा ({kmh} किमी/घंटा)"), (75, "बहुत तेज हवा ({kmh} किमी/घंटा) ⚠️"),
           (1e9, "तूफानी हवा ({kmh} किमी/घंटा) 🚨 घर के अंदर रहें")],
    "hi-Latn": [(2, "shaant ({kmh} km/h)"), (12, "halki hawa ({kmh} km/h)"), (29, "madhyam hawa ({kmh} km/h)"),
                (50, "tez hawa ({kmh} km/h)"), (75, "bahut tez hawa ({kmh} km/h) ⚠️"),
                (1e9, "toofani hawa ({kmh} km/h) 🚨 ghar ke andar rahein")],
    "mr": [(2, "शांत ({kmh} किमी/तास)"), (12, "हलका वारा ({kmh} किमी/तास)"), (29, "मध्यम वारा ({kmh} किमी/तास)"),
           (50, "जोरदार वारा ({kmh} किमी/तास)"), (75, "अतिशय जोरदार वारा ({kmh} किमी/तास) ⚠️"),
           (1e9, "वादळी वारा ({kmh} किमी/तास) 🚨 घरातच राहा")],
}


# ── helpers ──────────────────────────────────────────────────────────────────
def s(lang: str, key: str, **kw):
    text = STRINGS[lang][key]
    return text.format(**kw) if kw else text


def desc_local(desc_en: str, lang: str) -> str:
    d = (desc_en or "").lower()
    for pattern, text in DESC[lang]:
        if re.search(pattern, d):
            return text
    return (desc_en or "").capitalize() or "—"


def rain_label(mm, lang: str) -> str:
    mm = mm or 0
    for limit, text in RAIN[lang]:
        if mm < limit:
            return text.format(mm=f"{mm:.1f}")
    return text.format(mm=f"{mm:.1f}")


def wind_label(kmh, lang: str) -> str:
    kmh = kmh or 0
    for limit, text in WIND[lang]:
        if kmh < limit:
            return text.format(kmh=f"{kmh:.0f}")
    return text.format(kmh=f"{kmh:.0f}")


def weekday_name(d: date, lang: str) -> str:
    return WEEKDAYS[lang][d.weekday()]


def period_text(time_range: str, lang: str) -> str:
    P = PERIODS[lang]
    if time_range in P:
        return P[time_range]
    m = re.match(r"next_(\d+)_days", time_range or "")
    if m:
        return P["next_n"].format(n=m.group(1))
    m = re.match(r"in_(\d+)_days", time_range or "")
    if m:
        return P["in_n"].format(n=m.group(1))
    if (time_range or "").startswith("date:"):
        try:
            d = date.fromisoformat(time_range[5:])
            return P["date"].format(wd=weekday_name(d, lang), d=f"{d.day:02d}", m=f"{d.month:02d}")
        except ValueError:
            pass
    return P["today"]


def day_label(iso: str, lang: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{weekday_name(d, lang)}, {d.day:02d}/{d.month:02d}"
    except Exception:
        return iso or ""
