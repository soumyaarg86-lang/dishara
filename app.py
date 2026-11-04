import os
import time
import html
from datetime import datetime, date, time as dtime, timedelta, timezone

import streamlit as st
import swisseph as swe
from geopy.geocoders import Photon, Nominatim
from google import genai
from google.genai import types, errors
from supabase import create_client

st.set_page_config(page_title="Dishara", page_icon="🌅", layout="centered")

FEEDBACK_URL = "https://forms.gle/paste-your-link-here"
LANGUAGES = ["English", "Hindi", "Kannada", "Tamil", "Telugu", "Marathi", "Bengali", "Gujarati"]

# ---------------- STYLE ----------------
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Poppins:wght@300;400;500&display=swap');
html, body, p, label, li, .stMarkdown {font-family:'Poppins',sans-serif;}
h1, h2, h3 {font-family:'Cormorant Garamond',serif !important; color:#FAC775 !important;}
.card {background:#3C3489; border-radius:16px; padding:16px 18px; margin-bottom:12px;}
.muted {color:#AFA9EC; font-size:13px; margin:0;}
.gold {color:#FAC775;}
.big {font-size:17px; font-weight:500; margin:4px 0;}
.bar {height:6px; background:#534AB7; border-radius:3px; margin-top:8px;}
.bar > div {height:6px; background:#FAC775; border-radius:3px;}
.stButton > button {background:#EF9F27; color:#412402; border:none; border-radius:999px; font-weight:500; padding:0.5rem 1.6rem;}
.stButton > button:hover {background:#FAC775; color:#412402;}
.stTabs [aria-selected="true"] {color:#FAC775 !important;}
</style>""", unsafe_allow_html=True)

# ---------------- SECRETS & DATABASE ----------------
def secret(name):
    return os.environ.get(name) or st.secrets[name]

def db():
    # One database client per visitor, so each user's login stays separate
    if "sb" not in st.session_state:
        st.session_state.sb = create_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"))
    return st.session_state.sb

def load_profile(uid):
    rows = db().table("profiles").select("*").eq("user_id", uid).limit(1).execute().data
    return rows[0] if rows else None

def load_messages(uid, limit=30):
    rows = (db().table("messages").select("role,content,created_at").eq("user_id", uid)
            .order("created_at", desc=True).limit(limit).execute().data)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def save_message(uid, role, content):
    try:
        db().table("messages").insert({"user_id": uid, "role": role, "content": content}).execute()
    except Exception:
        pass

# ---------------- ASTRO DATA ----------------
SIGNS = ["Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
         "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
         "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)"]
SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
DASHA_ORDER = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7),
               ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]
PLANETS = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
           "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
           "Rahu": swe.MEAN_NODE}
ABBR = {"Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me", "Jupiter": "Ju",
        "Venus": "Ve", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke"}
EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
OWN = {"Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
       "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]}
SPECIAL_ASPECTS = {"Mars": [4, 8], "Jupiter": [5, 9], "Saturn": [3, 10]}
HOUSE_TOPICS = {1: "self, body, direction", 2: "money, family, speech",
                3: "courage, siblings, skills, short travel", 4: "home, mother, property, peace",
                5: "education, creativity, children, romance", 6: "work routine, competition, health habits",
                7: "marriage, partnerships, clients", 8: "transformation, research, shared resources",
                9: "luck, higher learning, mentors, long travel", 10: "career, status, public work",
                11: "gains, income, friends, ambitions", 12: "rest, expenses, foreign lands, spirituality"}
CHAPTER_THEME = {"Sun": "confidence and leadership", "Moon": "emotions and nurturing",
                 "Mars": "courage and action", "Mercury": "learning and communication",
                 "Jupiter": "growth and wisdom", "Venus": "love, comfort and creativity",
                 "Saturn": "discipline and lasting results", "Rahu": "ambition and new territory",
                 "Ketu": "reflection and inner clarity"}
MOON_HOUSE_MEANING = {
    1: "A fresh-start feeling. Put yourself first today.",
    2: "Good for family time and money planning.",
    3: "Courage is high. Make that call or start something small.",
    4: "A day for home, comfort and recharging.",
    5: "Creative and playful. Learn, create, enjoy.",
    6: "Great for clearing pending tasks and health routines.",
    7: "Partnerships shine. Meetings and relationships flow.",
    8: "Go inward. Research, reflect and rest more.",
    9: "Luck and wisdom. Learn, plan and seek guidance.",
    10: "Career spotlight. Show your work.",
    11: "Gains and friendships. Network and ask for support.",
    12: "Slow down. Rest, let go and plan quietly."}
NAK_LEN = 360 / 27
swe.set_sid_mode(swe.SIDM_LAHIRI)
FLAGS = swe.FLG_MOSEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
IST = 5.5

# ---------------- ASTRO CALCULATIONS ----------------
def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

def julian_day(dt_utc):
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600)

def sidereal_lon(jd, pid):
    xx, _ = swe.calc_ut(jd, pid, FLAGS)
    return xx[0], xx[3] < 0

def dignity(name, sign):
    if name not in EXALT:
        return ""
    if sign == EXALT[name]:
        return "exalted"
    if sign == (EXALT[name] + 6) % 12:
        return "debilitated"
    if sign in OWN[name]:
        return "own sign"
    return ""

def d9_sign(lon):
    return int(lon * 9 / 30) % 12

def d10_sign(lon):
    s, part = int(lon // 30), int((lon % 30) // 3)
    return (s + part) % 12 if s % 2 == 0 else (s + 8 + part) % 12

def vimshottari(moon_lon, birth_utc):
    nak = int(moon_lon // NAK_LEN)
    done = (moon_lon % NAK_LEN) / NAK_LEN
    first = nak % 9
    start = birth_utc - timedelta(days=done * DASHA_ORDER[first][1] * 365.25)
    periods = []
    for i in range(9):
        lord, yrs = DASHA_ORDER[(first + i) % 9]
        end = start + timedelta(days=yrs * 365.25)
        periods.append({"lord": lord, "start": start, "end": end})
        start = end
    return periods

def antardashas(md):
    years = dict(DASHA_ORDER)
    lords = [l for l, _ in DASHA_ORDER]
    i0 = lords.index(md["lord"])
    start, out = md["start"], []
    for k in range(9):
        lord = lords[(i0 + k) % 9]
        end = start + timedelta(days=years[md["lord"]] * years[lord] / 120 * 365.25)
        out.append({"md": md["lord"], "lord": lord, "start": start, "end": end})
        start = end
    return out

def pratyantars(ad):
    years = dict(DASHA_ORDER)
    lords = [l for l, _ in DASHA_ORDER]
    length = ad["end"] - ad["start"]
    i0 = lords.index(ad["lord"])
    start, out = ad["start"], []
    for k in range(9):
        lord = lords[(i0 + k) % 9]
        end = start + length * (years[lord] / 120)
        out.append({"lord": lord, "start": start, "end": end})
        start = end
    return out

def upcoming_subperiods(chart, now, count=8):
    out = []
    for md in chart["dashas"]:
        if md["end"] < now:
            continue
        for ad in antardashas(md):
            if ad["end"] >= now and len(out) < count:
                out.append(ad)
    return out

def compute_chart(local_dt, lat, lng, time_unknown=False):
    utc = local_dt - timedelta(hours=IST)
    jd = julian_day(utc)
    planets = {}
    for name, pid in PLANETS.items():
        plon, retro = sidereal_lon(jd, pid)
        planets[name] = {"lon": plon, "retro": retro and name != "Rahu"}
    planets["Ketu"] = {"lon": (planets["Rahu"]["lon"] + 180) % 360, "retro": False}
    if time_unknown:
        asc = planets["Moon"]["lon"]          # Chandra Lagna (Moon chart)
    else:
        _, ascmc = swe.houses_ex(jd, lat, lng, b'P', FLAGS)
        asc = ascmc[0]
    asc_sign = int(asc // 30)
    for name, p in planets.items():
        p["sign"] = int(p["lon"] // 30)
        p["deg"] = p["lon"] % 30
        p["house"] = (p["sign"] - asc_sign) % 12 + 1
        p["nak"] = int(p["lon"] // NAK_LEN)
        p["pada"] = int((p["lon"] % NAK_LEN) // (NAK_LEN / 4)) + 1
        p["dignity"] = dignity(name, p["sign"])
        p["d9"] = d9_sign(p["lon"])
        p["d10"] = d10_sign(p["lon"])
    return {"asc": asc, "asc_sign": asc_sign, "time_unknown": time_unknown,
            "planets": planets, "dashas": vimshottari(planets["Moon"]["lon"], utc)}

def house_of(chart, sign):
    return (sign - chart["asc_sign"]) % 12 + 1

def lordships(chart):
    out = {}
    for h in range(1, 13):
        out.setdefault(SIGN_LORDS[(chart["asc_sign"] + h - 1) % 12], []).append(h)
    return out

def aspects_on(chart):
    asp = {h: [] for h in range(1, 13)}
    for name, p in chart["planets"].items():
        if name in ("Rahu", "Ketu"):
            continue
        for n in [7] + SPECIAL_ASPECTS.get(name, []):
            asp[(p["house"] + n - 2) % 12 + 1].append(name)
    return asp

def house_lines(chart):
    asp = aspects_on(chart)
    lines = []
    for h in range(1, 13):
        sign = (chart["asc_sign"] + h - 1) % 12
        lord = SIGN_LORDS[sign]
        lp = chart["planets"][lord]
        occ = [n for n, p in chart["planets"].items() if p["house"] == h]
        dig = f" ({lp['dignity']})" if lp["dignity"] else ""
        lines.append(f"House {h} [{HOUSE_TOPICS[h]}]: {SIGNS[sign]}; lord {lord} in house "
                     f"{lp['house']}{dig}; occupants: {', '.join(occ) or 'none'}; "
                     f"aspected by: {', '.join(asp[h]) or 'none'}")
    return lines

def find_yogas(chart):
    P, ys = chart["planets"], []
    if (P["Jupiter"]["house"] - P["Moon"]["house"]) % 3 == 0:
        ys.append("Gaja Kesari (Jupiter in a kendra from the Moon): wisdom, respect, protection")
    if P["Sun"]["sign"] == P["Mercury"]["sign"]:
        ys.append("Budhaditya (Sun with Mercury): sharp intellect, communication")
    if P["Moon"]["sign"] == P["Mars"]["sign"]:
        ys.append("Chandra-Mangala (Moon with Mars): drive to earn, enterprise")
    if not chart["time_unknown"]:
        for pl, yn in {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
                       "Venus": "Malavya", "Saturn": "Sasa"}.items():
            p = P[pl]
            if p["house"] in (1, 4, 7, 10) and p["dignity"] in ("exalted", "own sign"):
                ys.append(f"{yn} Mahapurusha yoga ({pl} {p['dignity']} in a kendra)")
        kendra = {SIGN_LORDS[(chart["asc_sign"] + h - 1) % 12] for h in (1, 4, 7, 10)}
        trikona = {SIGN_LORDS[(chart["asc_sign"] + h - 1) % 12] for h in (1, 5, 9)}
        pairs = set()
        for a in kendra:
            for b in trikona:
                if a != b and P[a]["sign"] == P[b]["sign"] and frozenset((a, b)) not in pairs:
                    pairs.add(frozenset((a, b)))
                    ys.append(f"Raja yoga ({a} and {b}, kendra and trikona lords, together): rise and recognition")
    return ys

def transits(chart, now):
    jd = julian_day(now)
    moon_sign = chart["planets"]["Moon"]["sign"]
    out = []
    for name in ("Saturn", "Jupiter", "Rahu"):
        lon, _ = sidereal_lon(jd, PLANETS[name])
        s = int(lon // 30)
        out.append(f"{name} now in {SIGNS[s]}: house {house_of(chart, s)} from Lagna, "
                   f"house {(s - moon_sign) % 12 + 1} from Moon")
    sat_from_moon = (int(sidereal_lon(jd, swe.SATURN)[0] // 30) - moon_sign) % 12 + 1
    phase = {12: "phase 1 (rising)", 1: "phase 2 (peak)", 2: "phase 3 (setting)"}.get(sat_from_moon)
    out.append(f"Sade Sati: {'active, ' + phase if phase else 'not active'}")
    return out

def moon_today_house(chart, now):
    moon_now, _ = sidereal_lon(julian_day(now), swe.MOON)
    return house_of(chart, int(moon_now // 30))

def chart_text(chart, now):
    P = chart["planets"]
    lines = []
    if chart["time_unknown"]:
        lines.append("NOTE: Birth time unknown. Houses are counted from the Moon sign (Chandra Lagna). "
                     "Avoid Lagna, D9/D10 and exact-timing claims; dasha dates may be off by months.")
        lines.append(f"Chandra Lagna: {SIGNS[chart['asc_sign']]}")
    else:
        lines.append(f"Lagna: {SIGNS[chart['asc_sign']]} {chart['asc'] % 30:.1f}°; "
                     f"D9 Lagna {SIGNS[d9_sign(chart['asc'])]}; D10 Lagna {SIGNS[d10_sign(chart['asc'])]}")
    rules = lordships(chart)
    lines.append("\nPLANETS:")
    for name, p in P.items():
        extra = [x for x in (p["dignity"], "retrograde" if p["retro"] else "") if x]
        ext = f" ({', '.join(extra)})" if extra else ""
        ruled = f", rules houses {', '.join(map(str, rules[name]))}" if name in rules else ""
        lines.append(f"{name}: {SIGNS[p['sign']]} {p['deg']:.1f}°, house {p['house']}{ext}{ruled}; "
                     f"{NAKSHATRAS[p['nak']]} pada {p['pada']}; D9 {SIGNS[p['d9']]}; D10 {SIGNS[p['d10']]}")
    lines.append("\nHOUSES:")
    lines += house_lines(chart)
    ys = find_yogas(chart)
    lines.append("\nYOGAS: " + ("; ".join(ys) if ys else "none of the common ones"))
    lines.append("\nMAHADASHAS:")
    for d in chart["dashas"]:
        tag = " (CURRENT)" if d["start"] <= now < d["end"] else ""
        lines.append(f"{d['lord']}: {d['start']:%b %Y} to {d['end']:%b %Y}{tag}")
    subs = upcoming_subperiods(chart, now)
    lines.append("\nANTARDASHAS (current and upcoming):")
    for ad in subs:
        tag = " (CURRENT)" if ad["start"] <= now < ad["end"] else ""
        lines.append(f"{ad['md']}-{ad['lord']}: {ad['start']:%b %Y} to {ad['end']:%b %Y}{tag}")
    cur_ad = subs[0]
    lines.append(f"\nPRATYANTARS within {cur_ad['md']}-{cur_ad['lord']}:")
    shown = 0
    for pr in pratyantars(cur_ad):
        if pr["end"] >= now and shown < 5:
            tag = " (CURRENT)" if pr["start"] <= now < pr["end"] else ""
            lines.append(f"{cur_ad['md']}-{cur_ad['lord']}-{pr['lord']}: "
                         f"{pr['start']:%d %b %Y} to {pr['end']:%d %b %Y}{tag}")
            shown += 1
    lines.append("\nCURRENT TRANSITS:")
    lines += transits(chart, now)
    lines.append(f"\nToday's date: {now:%d %b %Y}")
    return "\n".join(lines)

HOUSE_POS = {1: (150, 80), 2: (76, 27), 3: (27, 76), 4: (75, 150), 5: (27, 224),
             6: (76, 270), 7: (150, 222), 8: (224, 270), 9: (273, 224),
             10: (225, 150), 11: (273, 76), 12: (224, 27)}

def kundali_svg(chart):
    houses = {h: [] for h in range(1, 13)}
    for name, p in chart["planets"].items():
        houses[p["house"]].append(ABBR[name])
    if not chart["time_unknown"]:
        houses[1].insert(0, "Asc")
    parts = ['<div style="text-align:center"><svg viewBox="0 0 300 300" width="100%" style="max-width:380px">',
             '<rect x="2" y="2" width="296" height="296" rx="8" fill="#3C3489" stroke="#FAC775" stroke-width="1.5"/>',
             '<g stroke="#FAC775" stroke-width="1" fill="none"><line x1="2" y1="2" x2="298" y2="298"/>'
             '<line x1="298" y1="2" x2="2" y2="298"/><polygon points="150,2 298,150 150,298 2,150"/></g>']
    for h, (x, y) in HOUSE_POS.items():
        sign_no = (chart["asc_sign"] + h - 1) % 12 + 1
        parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-size="11" fill="#FAC775">{" ".join(houses[h])}</text>')
        parts.append(f'<text x="{x}" y="{y + 13}" text-anchor="middle" font-size="9" fill="#AFA9EC">{sign_no}</text>')
    parts.append("</svg></div>")
    return "".join(parts)

def chart_from_profile(profile):
    bd = date.fromisoformat(profile["birth_date"])
    bt = datetime.strptime(profile["birth_time"][:5], "%H:%M").time()
    return compute_chart(datetime.combine(bd, bt), profile["lat"], profile["lon"],
                         profile["time_unknown"])

# ---------------- PLACE SEARCH ----------------
@st.cache_data(show_spinner=False, ttl=86400)
def search_places(q):
    results = []
    try:
        locs = Photon(user_agent="dishara-app", timeout=10).geocode(
            q, exactly_one=False, limit=15, language="en", osm_tag="place") or []
        for l in locs:
            pr = l.raw.get("properties", {})
            if pr.get("country") != "India":
                continue
            parts = [pr.get("name"), pr.get("county") or pr.get("district"), pr.get("state")]
            label = ", ".join(dict.fromkeys(p for p in parts if p))
            results.append((label, l.latitude, l.longitude))
    except Exception:
        pass
    if not results:
        try:
            locs = Nominatim(user_agent="dishara-app").geocode(
                q, exactly_one=False, limit=6, country_codes="in", timeout=10) or []
            results = [(l.address, l.latitude, l.longitude) for l in locs]
        except Exception:
            pass
    seen, unique = set(), []
    for r in results:
        if r[0] not in seen:
            seen.add(r[0])
            unique.append(r)
    return unique[:8]

# ---------------- SAFETY ----------------
CRISIS_WORDS = ["suicide", "kill myself", "end my life", "want to die", "self harm",
                "self-harm", "hurt myself", "no reason to live", "आत्महत्या",
                "मरना चाहता", "मरना चाहती", "जीना नहीं चाहता", "जीना नहीं चाहती"]
CRISIS_REPLY = ("I'm really glad you told me, and I'm going to pause the astrology for now, "
                "because you matter more than any chart.\n\n"
                "Please talk to someone right now. **Tele-MANAS: 14416** (free, 24/7, "
                "in many Indian languages). If you're in immediate danger, call **112**.\n\n"
                "If you can, reach out to someone you trust and let them know how you're feeling. "
                "I'm here whenever you want to talk again.")

def system_prompt(lang, name):
    return f"""You are Dishara (written दिशारा in Hindi), a warm, expert Vedic astrologer
in the Parashari tradition. You are talking with {name}. Give specific, well-reasoned guidance
that leaves them clear, capable and hopeful.

HOW TO ANALYSE (every time, silently):
1. Identify the life area and its houses: career 10, 6, 2, 11 + D10; money 2, 11, 5, 9;
   marriage/relationships 7, 2, 11, Venus + D9; education 4, 5, 9, Mercury, Jupiter;
   home/property 4; children 5, Jupiter; travel/abroad 3, 9, 12; health 1, 6 (wellbeing
   habits only); spiritual growth 9, 12, Ketu.
2. For each relevant house: its sign, its lord, where that lord sits and its dignity,
   planets in the house, aspects on it, and the natural significator planet.
3. Check yogas that involve these houses or planets.
4. Timing: does the current Mahadasha, Antardasha or Pratyantar lord own, occupy or aspect
   the relevant houses? Combine with Saturn and Jupiter transits. Name periods with months.
5. Weigh supportive and challenging factors and reach a clear conclusion. Don't hedge everything.

HOW TO ANSWER:
- Use bold headings: **What your chart shows** (2-4 bullets, each citing a specific factor,
  e.g. "your 10th lord Saturn sits in your 11th house..."), **Timing** (specific periods),
  **What you can do** (2-3 practical actions).
- Be specific to THIS chart. No generic Lagna or sun-sign personality text unless asked.
- Explain any Sanskrit term in a few words. Keep it under 250 words.
- Use the earlier conversation to stay consistent and follow up naturally.

RULES:
1. Use ONLY the chart data provided. Never invent positions, yogas or dates.
2. Lead with strengths; frame challenges as growth areas with practical steps.
3. No fear: no curses, doshas as threats, gemstones or paid remedies.
4. Never predict death, illness, accidents, divorce, lottery or stock results.
5. If asked about death or lifespan, kindly say you don't predict that and turn to strengths.
   Only if the person sounds distressed or hopeless, keep astrology to a line or two, put
   support first, and suggest Tele-MANAS at 14416 (free, 24/7). Don't call it confidential.
6. If the chart notes the birth time is unknown, say once that you're reading the Moon chart,
   and avoid Lagna-based or exact-timing claims.
7. Reply in {lang}. Write your own name correctly in that language's script."""

# ---------------- AI ----------------
@st.cache_resource
def get_client():
    return genai.Client(api_key=secret("GEMINI_API_KEY"))

@st.cache_resource
def get_models():
    skip = ["image", "tts", "audio", "live", "embedding", "robotics", "computer", "2.5"]
    avail = [m.name.replace("models/", "") for m in get_client().models.list()
             if "generateContent" in (m.supported_actions or [])]
    models = [m for m in avail if "flash" in m and not any(s in m for s in skip)]
    order = {"gemini-flash-latest": 0, "gemini-flash-lite-latest": 1}
    return sorted(models, key=lambda m: order.get(m, 2))

def ask_dishara(prompt, lang, name):
    client = get_client()
    for model in get_models()[:6]:
        for attempt in range(2):
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt(lang, name), temperature=0.5))
                return r.text
            except errors.ServerError:
                time.sleep(2 * (attempt + 1))
            except errors.ClientError:
                break
    return "I'm resting for a moment. Please ask again in a minute."

# ---------------- SCREENS ----------------
def hero():
    st.markdown("""<div style="text-align:center;padding:16px 0 4px">
      <svg viewBox="0 0 200 120" width="200"><g stroke="#FAC775" stroke-width="2" stroke-linecap="round">
      <line x1="100" y1="8" x2="100" y2="26"/><line x1="40" y1="33" x2="53" y2="46"/><line x1="160" y1="33" x2="147" y2="46"/>
      <line x1="14" y1="90" x2="31" y2="90"/><line x1="186" y1="90" x2="169" y2="90"/></g>
      <path d="M45 98 A55 55 0 0 1 155 98 Z" fill="#EF9F27"/><path d="M68 98 A32 32 0 0 1 132 98 Z" fill="#FAC775"/>
      <line x1="10" y1="98" x2="190" y2="98" stroke="#7F77DD" stroke-width="1.5"/></svg>
      <h1 style="font-size:48px;margin:0">Dishara</h1>
      <p class="gold" style="margin:0">दिशारा</p>
      <p style="color:#CECBF6;font-size:15px">Your stars, your direction.<br>Every night ends in a sunrise.</p>
    </div>""", unsafe_allow_html=True)

def auth_screen():
    hero()
    signin, signup = st.tabs(["Sign in", "Create account"])
    logged_in = None
    with signin:
        email = st.text_input("Email", key="si_email")
        pw = st.text_input("Password", type="password", key="si_pw")
        if st.button("Sign in"):
            try:
                res = db().auth.sign_in_with_password({"email": email.strip(), "password": pw})
                logged_in = {"id": res.user.id, "email": res.user.email}
            except Exception:
                st.error("Couldn't sign in. Check your email and password.")
    with signup:
        email2 = st.text_input("Email", key="su_email")
        pw2 = st.text_input("Password (at least 8 characters)", type="password", key="su_pw")
        consent = st.checkbox("I agree that Dishara can store my birth details and conversations "
                              "to personalise my guidance. I can ask for them to be deleted anytime.")
        if st.button("Create account"):
            if len(pw2) < 8:
                st.error("Please use a password of at least 8 characters.")
            elif not consent:
                st.error("Please tick the consent box to continue.")
            else:
                try:
                    res = db().auth.sign_up({"email": email2.strip(), "password": pw2})
                    if res.session:
                        logged_in = {"id": res.user.id, "email": res.user.email}
                    else:
                        st.success("Account created. Check your email to confirm, then sign in.")
                except Exception as ex:
                    st.error(f"Couldn't create the account: {ex}")
    if logged_in:
        st.session_state.user = logged_in
        st.rerun()

def profile_form(uid, existing):
    hero()
    ex = existing or {}
    st.markdown("### Your birth details")
    name = st.text_input("Your name", value=ex.get("name", ""))
    bdate = st.date_input("Birth date", value=date.fromisoformat(ex["birth_date"]) if ex else None,
                          min_value=date(1900, 1, 1), max_value=date.today(), format="DD/MM/YYYY")

    unknown = st.checkbox("I don't know my exact birth time", value=ex.get("time_unknown", False))
    hour = minute = ampm = None
    if not unknown:
        ih = im = iap = None
        if ex and not ex.get("time_unknown"):
            t = datetime.strptime(ex["birth_time"][:5], "%H:%M")
            ih, im, iap = (t.hour % 12 or 12) - 1, t.minute, 0 if t.hour < 12 else 1
        st.markdown("<p class='muted'>Birth time (you can type to jump, e.g. 7 or 45)</p>",
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        hour = c1.selectbox("Hour", list(range(1, 13)), index=ih, placeholder="Hour")
        minute = c2.selectbox("Minute", [f"{m:02d}" for m in range(60)], index=im, placeholder="Min")
        ampm = c3.selectbox("AM / PM", ["AM", "PM"], index=iap, placeholder="AM/PM")
    else:
        st.caption("No problem. Dishara will read your Moon chart, which is still very meaningful.")

    place = (ex["place"], ex["lat"], ex["lon"]) if ex else None
    if ex:
        st.markdown(f"<p class='muted'>Current birth place: {html.escape(ex['place'])}</p>",
                    unsafe_allow_html=True)
    query = st.text_input("Birth place: type your town or city and press Enter",
                          placeholder="e.g. Mysuru")
    if len(query.strip()) >= 3:
        with st.spinner("Finding places..."):
            options = search_places(query.strip())
        if options:
            labels = [o[0] for o in options]
            pick = st.selectbox("Select your birth place", labels, index=None,
                                placeholder="Choose the correct place")
            if pick:
                place = options[labels.index(pick)]
        else:
            st.warning("No match found. Check the spelling, or try the nearest bigger town.")

    default_lang = LANGUAGES.index(ex["language"]) if ex.get("language") in LANGUAGES else 0
    lang = st.selectbox("Language", LANGUAGES, index=default_lang)

    if st.button("Save and continue"):
        problems = []
        if not name.strip():
            problems.append("your name")
        if not bdate:
            problems.append("your birth date")
        if not unknown and (hour is None or minute is None or ampm is None):
            problems.append("hour, minute and AM/PM")
        if not place:
            problems.append("your birth place (pick one from the list)")
        if problems:
            st.error("Please add " + ", ".join(problems) + ".")
            return
        if unknown:
            h24, mins = 12, 0
        else:
            h24, mins = hour % 12 + (12 if ampm == "PM" else 0), int(minute)
        row = {"user_id": uid, "name": name.strip(), "birth_date": bdate.isoformat(),
               "birth_time": f"{h24:02d}:{mins:02d}", "time_unknown": unknown,
               "place": place[0], "lat": place[1], "lon": place[2], "language": lang}
        saved = None
        try:
            saved = db().table("profiles").upsert(row, on_conflict="user_id").execute().data[0]
        except Exception as ex2:
            st.error(f"Couldn't save your details: {ex2}")
        if saved:
            st.session_state.profile = saved
            st.session_state.pop("chart", None)
            st.session_state.pop("strengths", None)
            st.session_state.editing = False
            st.rerun()

    if existing and st.button("Cancel"):
        st.session_state.editing = False
        st.rerun()

# ---------------- APP FLOW ----------------
if "user" not in st.session_state:
    auth_screen()
    st.stop()

uid = st.session_state.user["id"]
if "profile" not in st.session_state:
    st.session_state.profile = load_profile(uid)
if st.session_state.profile is None or st.session_state.get("editing"):
    profile_form(uid, st.session_state.profile)
    st.stop()

profile = st.session_state.profile
if "chart" not in st.session_state:
    st.session_state.chart = chart_from_profile(profile)
if "messages" not in st.session_state:
    st.session_state.messages = load_messages(uid)

chart = st.session_state.chart
name_raw = profile["name"]
name = html.escape(name_raw)
lang = profile["language"]
now = datetime.now(timezone.utc).replace(tzinfo=None)
cur = next(d for d in chart["dashas"] if d["start"] <= now < d["end"])

st.markdown(f"<p class='muted'>Shubh din</p><h2 style='margin-top:0'>Namaste, {name}</h2>",
            unsafe_allow_html=True)
home, chat, kundali = st.tabs(["Home", "Ask Dishara", "Kundali"])

with home:
    mh = moon_today_house(chart, now)
    st.markdown(f"""<div class="card"><p class="muted">Today</p>
      <p class="big">{MOON_HOUSE_MEANING[mh]}</p>
      <p class="muted">Why: the Moon is moving through your {ordinal(mh)} house today.</p></div>""",
                unsafe_allow_html=True)
    pct = int(100 * (now - cur["start"]) / (cur["end"] - cur["start"]))
    st.markdown(f"""<div class="card"><p class="muted">Your current chapter · until {cur['end']:%b %Y}</p>
      <p class="big">{cur['lord']} Mahadasha: {CHAPTER_THEME[cur['lord']]}</p>
      <div class="bar"><div style="width:{pct}%"></div></div></div>""", unsafe_allow_html=True)
    sub = upcoming_subperiods(chart, now, 1)[0]
    st.markdown(f"""<div class="card"><p class="muted">Current sub-period · until {sub['end']:%b %Y}</p>
      <p class="big">{sub['md']}–{sub['lord']}: {CHAPTER_THEME[sub['lord']]}</p></div>""",
                unsafe_allow_html=True)
    if chart["time_unknown"]:
        st.caption("Reading from your Moon chart, since your birth time is unknown.")
    if st.button("Show my natural strengths"):
        with st.spinner("Dishara is studying your chart..."):
            st.session_state.strengths = ask_dishara(
                f"BIRTH CHART:\n{chart_text(chart, now)}\n\nQUESTION: What are my 3 biggest "
                f"natural strengths, and how can I use them in my current period?", lang, name_raw)
    if "strengths" in st.session_state:
        st.markdown(st.session_state.strengths)

with chat:
    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar="🌅" if m["role"] == "assistant" else None):
            st.markdown(m["content"])
    q = st.chat_input("Ask anything about your life")
    if q:
        st.session_state.messages.append({"role": "user", "content": q})
        save_message(uid, "user", q)
        with st.chat_message("user"):
            st.markdown(q)
        if any(w in q.lower() for w in CRISIS_WORDS):
            answer = CRISIS_REPLY
        else:
            memory = "\n".join(f"{m['role']}: {m['content']}"
                               for m in st.session_state.messages[-13:-1])
            prompt = (f"BIRTH CHART:\n{chart_text(chart, now)}\n\n"
                      f"EARLIER CONVERSATIONS:\n{memory or 'None'}\n\nQUESTION: {q}")
            with st.spinner("Dishara is studying your chart..."):
                answer = ask_dishara(prompt, lang, name_raw)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        save_message(uid, "assistant", answer)
        with st.chat_message("assistant", avatar="🌅"):
            st.markdown(answer)

with kundali:
    st.markdown(kundali_svg(chart), unsafe_allow_html=True)
    st.caption("North Indian style · numbers show the sign in each house"
               + (" · Moon chart (birth time unknown)" if chart["time_unknown"] else ""))
    rows = [{"Planet": n + (" (R)" if p["retro"] else ""), "Sign": SIGNS[p["sign"]],
             "Degree": f"{p['deg']:.2f}°", "House": p["house"], "Strength": p["dignity"] or "-",
             "Nakshatra": f"{NAKSHATRAS[p['nak']]} {p['pada']}",
             "D9": SIGNS[p["d9"]].split(" ")[0], "D10": SIGNS[p["d10"]].split(" ")[0]}
            for n, p in chart["planets"].items()]
    st.dataframe(rows, hide_index=True)
    ys = find_yogas(chart)
    if ys:
        st.markdown("#### Your yogas")
        for y in ys:
            st.markdown(f"- {y}")
    st.markdown("#### Life chapters")
    for d in chart["dashas"]:
        mark = "  ← now" if d is cur else ""
        st.markdown(f"**{d['lord']}** · {d['start']:%b %Y} – {d['end']:%b %Y}{mark}")

st.divider()
if "paste-your-link" not in FEEDBACK_URL:
    st.markdown(f"<p class='muted' style='text-align:center'>Help shape Dishara: "
                f"<a href='{FEEDBACK_URL}' style='color:#FAC775'>share your feedback</a></p>",
                unsafe_allow_html=True)
c1, c2 = st.columns(2)
if c1.button("Edit birth details"):
    st.session_state.editing = True
    st.rerun()
if c2.button("Sign out"):
    try:
        db().auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()
