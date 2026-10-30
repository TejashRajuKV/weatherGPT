"""
WeatherGPT feature handlers for the new intents (features 1-7, 9).
Imported by nlp.generate_response; keeps nlp.py itself untouched beyond dispatch.

Every handler signature:  handle(intent, parsed, weather_data, location, note="", **kw) -> str
Handlers degrade gracefully when data is missing.
"""
from datetime import date, timedelta

try:
    from services import scoring as _S
    from services import crops as _C
    from services import explainer as _X
except Exception:
    try:
        import scoring as _S
        import crops as _C
        import explainer as _X
    except Exception:
        _S = _C = _X = None


def _hours_of(data):
    """Extract hourly list from a forecast payload (data-service shape)."""
    fc = (data or {}).get("forecast") or {}
    daily = fc.get("daily") or {}
    if isinstance(daily, dict) and "time" in daily:
        return fc.get("hourly") or [], daily["time"]
    # alternate flat shape {"current":..., "hourly":[...], "daily":{"dates":[...]}}
    fc2 = data or {}
    return fc2.get("hourly") or [], ((fc2.get("daily") or {}).get("dates")
                                     or (fc2.get("daily") or {}).get("time") or [])


def _day_hours(hours, day):
    return [h for h in hours or [] if (h.get("time") or "").startswith(day)]


def _today_str():
    return date.today().isoformat()


def _fmt_time(t):
    try:
        hh, mm = t[11:13], t[14:16]
        h = int(hh)
        ampm = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{mm} {ampm}"
    except Exception:
        return t


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 — activity planner
# ─────────────────────────────────────────────────────────────────────────────
def activity_plan(parsed, weather_data, location, note=""):
    if _S is None:
        return "Activity planning is unavailable right now."
    hours, days = _hours_of(weather_data)
    if not hours:
        return (f"⚠️ I couldn't load hourly data to plan '{parsed.get('activity_key') or 'the activity'}' "
                f"for {location}. Please try again in a moment.")
    tr = parsed.get("time_range", "today")
    tod = parsed.get("tod")
    act = parsed.get("activity_key") or "general"

    # pick target day(s)
    if tr == "today" or tr == "tonight":
        target_days = [_today_str()]
    elif tr == "tomorrow":
        target_days = [(date.today() + timedelta(days=1)).isoformat()]
    elif tr == "day_after_tomorrow":
        target_days = [(date.today() + timedelta(days=2)).isoformat()]
    elif tr.startswith("date:"):
        target_days = [tr.split(":", 1)[1]]
    elif tr in ("this_week", "next_5_days", "weekend"):
        target_days = days[:5]
    else:
        target_days = days[:2]
    target_days = [d for d in target_days if d] or [_today_str()]

    window = None
    if tod == "morning":   window = (5, 12)
    elif tod == "afternoon": window = (12, 17)
    elif tod == "evening":   window = (17, 22)
    elif tod == "night":     window = (20, 24)

    prof = _S.ACTIVITY_PROFILES.get(act, _S.ACTIVITY_PROFILES["general"])
    lines = []
    best_all = None
    for d in target_days:
        dh = _day_hours(hours, d)
        if not dh:
            continue
        plan = _S.plan_activity(dh, d, act, window_hours=window)
        label = d if len(target_days) > 1 else ""
        score = plan["overall"]
        icon = "✅" if score >= 65 else ("⚠️" if score >= 50 else "❌")
        head = f"{plan['emoji']}  {prof['label']} on {d}" + ("" if len(target_days) == 1 else "")
        lines.append(f"{head}: {icon} suitability {score}/100 — {plan['verdict']}")
        for b in plan["best"]:
            bits = []
            if b["temp"] is not None: bits.append(f"{b['temp']:.0f}°C")
            if b["rain_prob"] is not None: bits.append(f"rain {b['rain_prob']:.0f}%")
            if b["wind"] is not None: bits.append(f"wind {b['wind']:.0f} km/h")
            if b["uv"] is not None: bits.append(f"UV {b['uv']:.0f}")
            lines.append(f"   • {b['hour']} ({', '.join(bits)}) — score {b['score']}/100")
        if best_all is None or score > best_all[0]:
            best_all = (score, d, plan)
    if not lines:
        return f"⚠️ No forecast hours available for {location}."
    # headline verdict
    out = []
    if best_all:
        sc, d, plan = best_all
        if sc >= 65:
            first = plan["best"][0]["hour"] if plan["best"] else "the preferred window"
            out.append(f"👍 Yes — {prof['label'].lower()} near {location} looks good ({plan['verdict'].split('—')[0].strip()}). Best slot around {first}.")
        elif sc >= 50:
            out.append(f"🤔 Marginal — {prof['label'].lower()} near {location} is doable with caveats. Pick one of the slots below.")
        else:
            out.append(f"❌ I'd skip it — {prof['label'].lower()} near {location} has poor conditions in this window.")
    out.append("")
    out.extend(lines)
    # quick reason line
    warn = []
    if prof["prob_max"] <= 25: warn.append(f"rain probability must stay under ~{prof['prob_max']}%")
    if act == "spraying": warn.append("spray drift risk above ~15 km/h wind")
    if act == "laundry": warn.append("needs humidity under ~70% and no rain")
    if warn:
        out.append(f"\nℹ️ Scoring uses rain probability, temperature, wind, humidity and UV — key limits: {'; '.join(warn)}.")
    if note:
        out.append(f"\n{note}")
    out.append(f"\n📡  Source: {(weather_data.get('current') or {}).get('source', 'Open-Meteo')}")
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2 — travel / commute weather
# ─────────────────────────────────────────────────────────────────────────────
def travel(parsed, weather_data, location, note=""):
    if _S is None:
        return "Travel weather is unavailable right now."
    route = parsed.get("route") or parsed.get("route_names")
    origin = route[0] if route else (location or "origin")
    dest = route[1] if route and len(route) > 1 else "destination"
    multi = weather_data.get("multi") or {}
    src_a = multi.get(origin) or weather_data.get("forecast") or {}
    src_b = multi.get(dest) or {}
    hours_a, days_a = _hours_of({"forecast": src_a} if "forecast" not in src_a else src_a)
    if not hours_a and weather_data.get("forecast"):
        hours_a, days_a = _hours_of(weather_data)
    hours_b, days_b = _hours_of({"forecast": src_b})
    if not hours_b and src_b.get("hourly"):
        hours_b, days_b = _hours_of(src_b)

    if not hours_a:
        return f"⚠️ Could not fetch route weather for {origin} → {dest}. Try naming both places as real cities."

    tr = parsed.get("time_range", "today")
    tod = parsed.get("tod")
    if tr == "tomorrow":
        target = (date.today() + timedelta(days=1)).isoformat()
    elif tr == "day_after_tomorrow":
        target = (date.today() + timedelta(days=2)).isoformat()
    elif tr.startswith("date:"):
        target = tr.split(":", 1)[1]
    else:
        target = _today_str()
    win = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22), "night": (20, 24)}.get(tod) \
          or (16, 21 if "evening" == tod else 24)

    ha = [h for h in _day_hours(hours_a, target) if h.get("time")]
    hb = [h for h in _day_hours(hours_b, target) if h.get("time")]
    if win:
        ha_w = [h for h in ha if win[0] <= int((h.get("time") or "T12")[11:13]) < win[1]]
        ha_eval = ha_w or ha
    else:
        ha_eval = ha
    if not ha_eval:
        ha_eval = ha[:12]

    def agg(hs):
        if not hs:
            return {}
        def avg(k):
            vs = [h.get(k) for h in hs if h.get(k) is not None]
            return sum(vs) / len(vs) if vs else None
        return {
            "rain_mm": sum(h.get("precipitation") or 0 for h in hs),
            "prob": max((h.get("precipitation_probability") or 0) for h in hs) if any(h.get("precipitation_probability") is not None for h in hs) else None,
            "vis": min([h.get("visibility") for h in hs if h.get("visibility") is not None], default=None),
            "wind": max([h.get("windspeed_10m") or 0 for h in hs], default=None),
            "temp": avg("temperature_2m"),
            "code": max((h.get("weather_code") or 0) for h in hs),
        }
    A, B = agg(ha_eval), agg(hb)

    lines = [f"🛣  Route weather: {origin.title()} → {dest.title()} ({target}"
             + (f", {tod}" if tod else "") + ")"]
    if not B:
        lines.append(f"   (No separate data for {dest.title()}; showing origin corridor.)")

    def leg(name, x):
        if not x:
            return f"   {name}: no data"
        vr = _S.visibility_risk(x.get("vis"))
        rain_s = "dry" if (x.get("rain_mm") or 0) < 0.2 else f"{x['rain_mm']:.1f} mm"
        fog = vr[1] if vr else "unknown visibility"
        storm = " ⛈ thunder possible" if (x.get("code") or 0) >= 95 else ""
        return (f"   {name}: rain {rain_s}"
                + (f" (peak prob {x['prob']:.0f}%)" if x.get("prob") is not None else "")
                + f", wind up to {x['wind']:.0f} km/h, visibility {fog}{storm}")
    lines.append("")
    lines.append(leg("Origin ", A))
    if B:
        lines.append(leg("Dest.  ", B))

    # rain timing along the way
    wet = [h for h in ha_eval if (h.get("precipitation") or 0) >= 0.5 or (h.get("precipitation_probability") or 0) >= 60]
    if wet:
        first_wet = _fmt_time(wet[0]["time"])
        last_wet = _fmt_time(wet[-1]["time"])
        lines.append(f"\n☔ Rain window on this stretch: roughly {first_wet} – {last_wet}.")
    else:
        lines.append("\n☔ No meaningful rain expected during the evaluated window.")

    # fog check for morning commutes
    if tod == "morning":
        lowvis = [h for h in ha_eval if (h.get("visibility") or 20000) < 4000]
        if lowvis:
            worst = min(lowvis, key=lambda h: h.get("visibility") or 9e9)
            lines.append(f"🌫 Fog risk: visibility drops to ~{(worst['visibility'] or 0)/1000:.1f} km around {_fmt_time(worst['time'])}. Leave earlier and use headlights.")
        else:
            lines.append("🌫 No significant fog signal for the morning window.")

    # best departure window: lowest combined rain+low-vis score
    scored = []
    for h in ha_eval:
        r = (h.get("precipitation_probability") or 0) + (h.get("precipitation") or 0) * 40
        vpen = 30 if (h.get("visibility") or 99999) < 2000 else 0
        scored.append((r + vpen, h))
    if scored:
        scored.sort(key=lambda x: x[0])
        bh = scored[0][1]
        lines.append(f"🕐 Best departure window: around {_fmt_time(bh['time'])} "
                     f"(lowest rain/visibility risk on the corridor).")
    if note:
        lines.append(f"\n{note}")
    lines.append("\nℹ️ Route estimate compares origin/destination forecasts — actual conditions between towns may vary. Check official IMD warnings before long highway trips.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3 — crop calendar
# ─────────────────────────────────────────────────────────────────────────────
def crop_calendar(parsed, weather_data, location, note="", crop=None, stage=None):
    if _C is None:
        return "Crop advisory is unavailable right now."
    ck = crop or parsed.get("crop")
    sk = stage or parsed.get("crop_stage")
    hours, days = _hours_of(weather_data)
    if not ck:
        return ("Tell me the crop and growth stage — e.g. \"my wheat is at flowering stage; any frost risk?\" "
                "Supported: wheat, tomato, cotton, onion, soybean, rice, sugarcane.")
    if not hours:
        return f"⚠️ No forecast data available for {location} to assess the {ck} crop."
    a = _C.assess_crop(ck, sk, hours, days_ahead=min(7, len(days) or 7))
    lines = [f"{a['emoji']}  Crop weather advisory — {a['label']} near {location}"]
    if a.get("note"):
        lines.append(f"   📖 {a['note']}")

    f = a["frost"]
    if f:
        if f["risk"]:
            evs = "; ".join(f"{e['date']} ~{e['at']} ({e['temp_min']}°C ≤ critical {e['critical']}°C)" for e in f["events"])
            lines.append(f"\n❄️ FROST RISK: {evs}")
            lines.append("   Mitigation: evening micro-sprinkling, smoke screens/hai, mulching; delay harvest of sensitive produce.")
        else:
            thr = f["threshold"]
            lines.append(f"\n✅ Frost: no night below the {thr}°C critical threshold for this stage in the next {min(7,len(days))} days.")

    hst = a["heat"]
    if hst:
        if hst["risk"]:
            evs = "; ".join(f"{e['date']} up to {e['temp_max']}°C ({e['hot_hours']} hot hrs)" for e in hst["events"])
            lines.append(f"🌡 HEAT STRESS (> {hst['threshold']}°C at this stage): {evs}")
        else:
            lines.append(f"🌡 Heat stress: none above {hst['threshold']}°C expected.")

    irr = a["irrigation"] or {}
    need_map = {"urgent": "💧 IRRIGATE NOW", "light": "💧 Light irrigation in 1–2 days",
                "ok": "💧 Irrigation: soil balance OK for now", "skip": "💧 Skip irrigation"}
    lines.append(f"{need_map.get(irr.get('need'), '💧 Irrigation: —')} — {irr.get('reason','')}")

    sw = a["spray_windows"]
    if sw:
        lines.append("\n🚿 Good spraying windows (calm, dry, 8-h rain-free gap):")
        for w in sw:
            rp = f", rain prob {w['rain_prob']:.0f}%" if w.get("rain_prob") is not None else ""
            lines.append(f"   • {w['time'][:10]} {_fmt_time(w['time'])} — {w['temp']}°C, wind {w['wind']} km/h{rp}")
    else:
        lines.append("\n🚿 No reliable spraying window in the next 3 days — wait for calmer/drier spells.")

    if a["disease"]:
        lines.append("\n🦠 Disease pressure:")
        for d in a["disease"]:
            until = f" (conditions persist past {str(d['until'])[:16].replace('T',' ')})" if d.get("until") else ""
            lines.append(f"   • {d['name'].title()}: {d['level']} risk — {d['hours']} h of favourable temp/humidity{until}")
    else:
        lines.append("\n🦠 Disease risk: no prolonged favourable conditions detected for tracked diseases.")

    if note:
        lines.append(f"\n{note}")
    lines.append("\n⚠️ Threshold-based advisory from forecast data; confirm with your local agricultural extension officer.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 4 — personalized alert profiles (draft generation from NL)
# ─────────────────────────────────────────────────────────────────────────────
def alerts_personal(parsed, weather_data, location, note=""):
    import re
    q = parsed.get("normalized", "")
    draft = None
    m = re.search(r"wind.*?(?:exceeds|above|crosses|>\s*)\s*(\d{1,3})", q) or \
        re.search(r"(?:if )?wind (?:is |goes )?above\s*(\d{1,3})", q)
    if m:
        draft = {"metric": "wind_speed_kmh", "op": ">", "value": float(m.group(1)),
                 "duration_hours": 1, "window_start_hour": None, "window_end_hour": None}
    m = re.search(r"temp(?:erature)?.*?(?:crosses|above|exceeds|>\s*)\s*(\d{1,2}(?:\.\d)?)", q)
    if not draft and m:
        days = 2 if re.search(r"two days|2 days|दो दिन|दोन दिवस", q) else 1
        draft = {"metric": "temperature_c", "op": ">", "value": float(m.group(1)),
                 "duration_hours": 24 * days, "window_start_hour": None, "window_end_hour": None}
    m = re.search(r"heavy rain.*?(\d{1,2})\s*(?:pm|am)?[^-\d]*?(?:to|and|-)\s*(\d{1,2})\s*(pm|am)", q)
    if not draft and m:
        s, e, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        sh = s + (12 if ap == "pm" and s < 12 else 0)
        eh = e + (12 if ap == "pm" and e < 12 else 0)
        draft = {"metric": "rain_mm", "op": ">=", "value": 20.0, "duration_hours": 1,
                 "window_start_hour": sh, "window_end_hour": eh}
    if not draft:
        m2 = re.search(r"rain.*?(\d{1,2})\s*(pm|am).*?(?:to|-|and).*?(\d{1,2})\s*(pm|am)", q)
        if m2:
            s, sa, e, ea = int(m2.group(1)), m2.group(2), int(m2.group(3)), m2.group(4)
            sh = s + (12 if sa == "pm" and s < 12 else 0)
            eh = e + (12 if ea == "pm" and e < 12 else 0)
            draft = {"metric": "rain_mm", "op": ">=", "value": 20.0, "duration_hours": 1,
                     "window_start_hour": sh, "window_end_hour": eh}

    if not draft:
        return ("I can set personal thresholds like:\n"
                "• \"Alert me if wind exceeds 40 km/h at my farm\"\n"
                "• \"Notify me if temperature crosses 38°C for two days\"\n"
                "• \"Warn me before heavy rain between 6 PM and 10 PM\"\n"
                "Tell me metric, threshold, and (optionally) time window & location.")

    loc = location if location and location != "your location" else None
    human = {
        "wind_speed_kmh": f"wind speed over {draft['value']:.0f} km/h",
        "temperature_c":  f"temperature above {draft['value']:.0f}°C for ≥{draft['duration_hours']} h",
        "rain_mm":        f"heavy rain (≥{draft['value']:.0f} mm/h)"
                          + (f" between {draft['window_start_hour']}:00–{draft['window_end_hour']}:00"
                             if draft.get("window_start_hour") is not None else ""),
    }[draft["metric"]]
    return (f"🔔 Personal alert ready for {loc or 'your saved location'}:\n\n"
            f"   “Alert me when {human}.”\n\n"
            f"Save it on the Alerts page (it will be checked against the live forecast every few minutes) "
            f"or send it with short_mode chat. The engine only fires once per crossing episode and auto-clears "
            f"when conditions drop back below the threshold.")


# ─────────────────────────────────────────────────────────────────────────────
# Feature 5 — explain this forecast
# ─────────────────────────────────────────────────────────────────────────────
def explain(parsed, weather_data, location, note=""):
    if _X is None:
        return "Explainer unavailable."
    cur = {}
    fc = weather_data.get("forecast") or {}
    c = fc.get("current") or weather_data.get("current") or {}
    cur = {"temperature": c.get("temperature_2m") or c.get("temperature"),
           "feels_like": c.get("apparent_temperature") or c.get("feels_like"),
           "humidity": c.get("relative_humidity_2m") or c.get("humidity"),
           "wind_speed": c.get("wind_speed_10m") or c.get("wind_speed"),
           "pressure": c.get("surface_pressure") or c.get("pressure"),
           "uv_index": c.get("uv_index"),
           "visibility": c.get("visibility"),
           "dew_point": c.get("dew_point_2m") or c.get("dew_point"),
           "precipitation_probability": ((fc.get("hourly") or [{}])[0]).get("precipitation_probability")}
    txt = _X.explain_query(parsed.get("raw_query", ""), {"current": cur})
    tail = ""
    if location and location != "your location" and (c or fc):
        tail = f"\n\n📍 Current values near {location}: " + ", ".join(
            filter(None, [
                f"{cur['temperature']:.0f}°C" if cur.get("temperature") is not None else "",
                f"humidity {cur['humidity']:.0f}%" if cur.get("humidity") is not None else "",
                f"wind {cur['wind_speed']:.0f} km/h" if cur.get("wind_speed") is not None else "",
            ]))
    return txt + tail + ("\n" + note if note else "")


# ─────────────────────────────────────────────────────────────────────────────
# Feature 6 — weather comparison
# ─────────────────────────────────────────────────────────────────────────────
def compare(parsed, weather_data, location, note=""):
    multi = weather_data.get("multi") or {}
    climate = weather_data.get("climate") or {}
    locs = list(multi.keys())
    tr = parsed.get("time_range", "")

    def week_stats(fc):
        daily = (fc or {}).get("daily") or {}
        times = daily.get("time") or daily.get("dates") or []
        rain = daily.get("rain_sum") or daily.get("precipitation_sum") or []
        tmax = daily.get("temperature_2m_max") or daily.get("temp_max") or []
        out = []
        for i, t in enumerate(times[:7]):
            out.append({"date": t,
                        "rain": (rain[i] if i < len(rain) else None),
                        "tmax": (tmax[i] if i < len(tmax) else None)})
        return out

    # year/month-over-year historical comparison for same location
    if tr.startswith("last_") and climate.get("records"):
        recs = climate["records"]
        mon = parsed.get("compare_month")
        today = date.today()
        if mon is None:
            mon = today.month
        prev_year = [r for r in recs if int(r["date"][:4]) == today.year - 1 and int(r["date"][5:7]) == mon]
        cur_fc = week_stats(multi.get(locs[0]) if locs else weather_data.get("forecast"))
        # current-month-to-date from archive too (same month previous years aside)
        cmtd = [r for r in recs if int(r["date"][:4]) == today.year and int(r["date"][5:7]) == mon]
        ref = prev_year or cmtd
        which = "last year" if prev_year else "this month"
        if not ref:
            return f"No archive records found for month {mon} near {locs[0] if locs else location}."
        tot = sum(r.get("precipitation") or 0 for r in ref)
        mxs = [r.get("temp_max") for r in ref if r.get("temp_max") is not None]
        avg_mx = sum(mxs) / len(mxs) if mxs else None
        rainy = sum(1 for r in ref if (r.get("precipitation") or 0) > 1)
        mname = [None, "January","February","March","April","May","June","July","August",
                 "September","October","November","December"][mon]
        yr = (today.year - 1) if prev_year else today.year
        lines = [f"📊 {locs[0] if locs else location.title()} — {mname} {yr} recap ({which} reference):"]
        lines.append(f"   Total rainfall : {tot:.0f} mm over {len(ref)} days ({rainy} rainy days)")
        if avg_mx is not None:
            lines.append(f"   Avg daily high : {avg_mx:.1f}°C")
        if cmtd and prev_year:
            ctot = sum(r.get("precipitation") or 0 for r in cmtd)
            cmxs = [r.get("temp_max") for r in cmtd if r.get("temp_max") is not None]
            camx = sum(cmxs) / len(cmxs) if cmxs else None
            lines.append(f"\n   Same month this year so far: {ctot:.0f} mm, avg high {camx:.1f}°C" if camx else f"   Same month this year so far: {ctot:.0f} mm")
            if camx and avg_mx:
                diff = camx - avg_mx
                verdict = "hotter" if diff > 0.5 else "cooler" if diff < -0.5 else "about the same"
                lines.append(f"   ➡ This {mname} is {abs(diff):.1f}°C {verdict} than {yr}'s {mname}.")
        lines.append(f"\n📡 Source: {climate.get('source', 'Open-Meteo Archive')}")
        return "\n".join(lines)

    if len(locs) < 2:
        return ("Name two places, e.g. \"compare Nashik and Pune rainfall this week\" or "
                "\"is this October hotter than last October in Nagpur\".")
    a, b = locs[0], locs[1]
    sa, sb = week_stats(multi[a]), week_stats(multi[b])
    ra = sum(x["rain"] or 0 for x in sa)
    rb = sum(x["rain"] or 0 for x in sb)
    ta = [x["tmax"] for x in sa if x["tmax"] is not None]
    tb = [x["tmax"] for x in sb if x["tmax"] is not None]
    ma = sum(ta) / len(ta) if ta else None
    mb = sum(tb) / len(tb) if tb else None
    rainy_a = sum(1 for x in sa if (x["rain"] or 0) > 1)
    rainy_b = sum(1 for x in sb if (x["rain"] or 0) > 1)

    lines = [f"⚖️  Next 7 days — {a.title()} vs {b.title()}"]
    lines.append(f"\n   🌧 Rain total : {a.title()} {ra:.1f} mm ({rainy_a} rainy days)  |  {b.title()} {rb:.1f} mm ({rainy_b} rainy days)")
    if ma is not None and mb is not None:
        lines.append(f"   🌡 Avg high   : {a.title()} {ma:.1f}°C  |  {b.title()} {mb:.1f}°C")
    winner = a if ra > rb else b if rb > ra else None
    if winner:
        lines.append(f"\n   ➡ {winner.title()} looks wetter this week (difference {abs(ra-rb):.1f} mm).")
    else:
        lines.append("\n   ➡ Both places look similarly dry/wet this week.")
    lines.append("\n   Day-by-day rainfall:")
    lines.append(f"   {'Date':<12}{a.title():>14}{'':>4}{b.title():>14}")
    for i in range(max(len(sa), len(sb))):
        da = sa[i] if i < len(sa) else {}
        db = sb[i] if i < len(sb) else {}
        d = (da.get("date") or db.get("date") or "")[5:]
        va = f"{da.get('rain'):.1f} mm" if da.get("rain") is not None else "—"
        vb = f"{db.get('rain'):.1f} mm" if db.get("rain") is not None else "—"
        lines.append(f"   {d:<12}{va:>14}{'':>4}{vb:>14}")
    if note:
        lines.append(f"\n{note}")
    lines.append(f"\n📡 Source: Open-Meteo forecast API")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Feature 7 — health & comfort index
# ─────────────────────────────────────────────────────────────────────────────
def health_index(parsed, weather_data, location, note=""):
    if _S is None:
        return "Health index unavailable."
    hours, days = _hours_of(weather_data)
    fc = weather_data.get("forecast") or {}
    cur = fc.get("current") or weather_data.get("current") or {}
    temp = cur.get("temperature_2m") or cur.get("temperature")
    rh = cur.get("relative_humidity_2m") or cur.get("humidity")
    uv = cur.get("uv_index")
    wind = cur.get("wind_speed_10m") or cur.get("wind_speed")
    vis = cur.get("visibility")
    aq = fc.get("air_quality") or weather_data.get("air_quality") or {}
    aqi = None
    pm25 = None
    pollen = None
    if aq:
        aqi = aq.get("us_aqi") or aq.get("eu_aqi")
        pm25 = aq.get("pm2_5")
        pollen = (aq.get("pollen_larrea") or aq.get("tree_pollen")
                  or aq.get("grass_pollen") or aq.get("mould_spores"))
    day_now = _today_str()
    todays = [h for h in hours if (h.get("time") or "").startswith(day_now)] or hours[:24]
    temps = [h.get("temperature_2m") for h in todays if h.get("temperature_2m") is not None]
    uvs = [h.get("uv_index") for h in todays if h.get("uv_index") is not None]
    max_uv = max(uvs) if uvs else uv
    hi_noon = None
    if temps and rh is not None:
        hi_noon = _S.heat_index_c(max(temps), rh)
    hx = _S.humidex_c(temp, rh) if temp is not None else None

    lines = [f"🫁 Health & comfort index — {location or 'your area'}"]
    lines.append("")
    if temp is not None:
        he = _S.heat_index_c(temp, rh)
        lines.append(f"🌡 Now {temp:.0f}°C · heat index {he:.0f}°C · humidex {hx:.0f} ({_S.humidex_label(hx)})")
    if temps:
        advice = _S.heat_stress_advice(max(temps), rh)
        if advice:
            lines.append(f"💦 Dehydration/heat-stress: {advice}")
        lines.append(f"   Peak today {max(temps):.0f}°C — drink ~250 ml water each hour of outdoor work.")
    if max_uv is not None:
        lines.append(f"☀️ {_S.uv_advice(max_uv)}")
    if aqi is not None:
        band = _S.aqi_band(aqi)
        if band:
            extra = f" (PM2.5 {pm25:.0f} µg/m³)" if pm25 is not None else ""
            lines.append(f"😷 Air quality: AQI {aqi:.0f} — {band['label']}{extra}. {band['advice']}")
    else:
        lines.append("😷 Air quality: not available in this dataset (feature needs the air-quality API enabled).")
    asthma = _S.asthma_advice(aqi, pollen, temp, rh, wind)
    if asthma:
        lines.append("🫁 Asthma-friendly advice:")
        for a in asthma:
            lines.append(f"   • {a}")
    if vis is not None:
        vr = _S.visibility_risk(vis)
        if vr and vr[0] != "good":
            lines.append(f"👁 Visibility: {vr[1]}")
    if note:
        lines.append(f"\n{note}")
    lines.append("\nℹ️ General wellness guidance — not medical advice.")
    return "\n".join(lines)


HANDLERS = {
    "activity_plan": activity_plan,
    "travel": travel,
    "crop_calendar": crop_calendar,
    "alerts_personal": alerts_personal,
    "explain": explain,
    "compare": compare,
    "health_index": health_index,
}
