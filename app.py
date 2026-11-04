import os
import time
import html
from datetime import datetime, date, timedelta, timezone

import streamlit as st
import swisseph as swe
from geopy.geocoders import Photon, Nominatim
from google import genai
from google.genai import types, errors
from supabase import create_client

st.set_page_config(page_title="Dishara", page_icon="🌅", layout="centered")

FEEDBACK_URL = "https://forms.gle/paste-your-link-here"
LANGUAGES = ["English", "Hindi", "Kannada", "Tamil", "Telugu", "Marathi", "Bengali", "Gujarati"]
RELATIONS = ["Self", "Spouse / Partner", "Mother", "Father", "Son", "Daughter",
             "Sibling", "Friend", "Other"]

# ---------------- STYLE ----------------
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Poppins:wght@300;400;500&display=swap');
html, body, p, label, li, .stMarkdown {font-family:'Poppins',sans-serif;}
h1, h2, h3, h4 {font-family:'Cormorant Garamond',serif !important; color:#FAC775 !important;}
.card {background:#3C3489; border-radius:16px; padding:16px 18px; margin-bottom:12px;}
.muted {color:#AFA9EC; font-size:13px; margin:0;}
.gold {color:#FAC775;}
.big {font-size:17px; font-weight:500; margin:4px 0;}
.score {font-size:42px; font-weight:500; color:#FAC775; margin:0; line-height:1.1;}
.bar {height:6px; background:#534AB7; border-radius:3px; margin-top:8px;}
.bar > div {height:6px; background:#FAC775; border-radius:3px;}
.stButton > button {background:#EF9F27; color:#412402; border:none; border-radius:999px; font-weight:500; padding:0.45rem 1.4rem;}
.stButton > button:hover {background:#FAC775; color:#412402;}
.stTabs [aria-selected="true"] {color:#FAC775 !important;}
</style>""", unsafe_allow_html=True)

# ---------------- SECRETS & DATABASE ----------------
def secret(name):
    return os.environ.get(name) or st.secrets[name]

def db():
    if "sb" not in st.session_state:
        st.session_state.sb = create_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"))
    return st.session_state.sb

def list_charts(uid):
    return (db().table("profiles").select("*").eq("user_id", uid)
            .order("created_at").execute().data)

def list_conversations(pid):
    return (db().table("conversations").select("id,title,created_at").eq("profile_id", pid)
            .order("created_at", desc=True).limit(40).execute().data)

def load_conversation(cid):
    return (db().table("messages").select("role,content").eq("conversation_id", cid)
            .order("created_at").execute().data)

def new_conversation(uid, pid, title):
    return (db().table("conversations").insert(
        {"user_id": uid, "profile_id": pid, "title": title[:80]}).execute().data[0]["id"])

def save_message(uid, cid, role, content):
    try:
        db().table("messages").insert({"user_id": uid, "conversation_id": cid,
                                       "role": role, "content": content}).execute()
    except Exception:
        pass

def get_saved_tip(pid, day):
    try:
        rows = (db().table("daily_tips").select("content").eq("profile_id", pid)
                .eq("day", day.isoformat()).limit(1).execute().data)
        return rows[0]["content"] if rows else None
    except Exception:
        return None

def save_tip(uid, pid, day, content):
    try:
        db().table("daily_tips").upsert({"user_id": uid, "profile_id": pid, "day": day.isoformat(),
                                         "content": content}, on_conflict="profile_id,day").execute()
    except Exception:
        pass

# ---------------- ASTRO DATA ----------------
SIGNS = ["Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
         "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
         "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)"]
SHORT = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
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
VARGAS = {"D1 · Rashi (overall life)": 1, "D2 · Hora (wealth)": 2,
          "D3 · Drekkana (siblings, courage)": 3, "D4 · Chaturthamsa (home, property)": 4,
          "D7 · Saptamsa (children)": 7, "D9 · Navamsa (marriage, inner strength)": 9,
          "D10 · Dasamsa (career)": 10, "D12 · Dwadasamsa (parents)": 12,
          "D24 · Chaturvimsamsa (education)": 24}
VARGA_NS = [2, 3, 4, 7, 9, 10, 12, 24]
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
TARAS = ["Janma", "Sampat", "Vipat", "Kshema", "Pratyak", "Sadhana", "Naidhana", "Mitra", "Parama Mitra"]
GOOD_TARAS = {"Sampat", "Kshema", "Sadhana", "Mitra", "Parama Mitra"}
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

def varga_sign(lon, n):
    s, deg = int(lon // 30), lon % 30
    odd = s % 2 == 0          # Aries, Gemini... are odd signs
    if n == 1:
        return s
    if n == 2:
        first = deg < 15
        return (4 if first else 3) if odd else (3 if first else 4)
    if n == 3:
        return (s + int(deg // 10) * 4) % 12
    if n == 4:
        return (s + int(deg // 7.5) * 3) % 12
    if n == 7:
        p = min(int(deg // (30 / 7)), 6)
        return (s + p) % 12 if odd else (s + 6 + p) % 12
    if n == 9:
        return int(lon * 9 / 30) % 12
    if n == 10:
        p = int(deg // 3)
        return (s + p) % 12 if odd else (s + 8 + p) % 12
    if n == 12:
        return (s + int(deg // 2.5)) % 12
    if n == 24:
        p = int(deg // 1.25)
        return (4 + p) % 12 if odd else (3 + p) % 12
    return s

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
        asc = planets["Moon"]["lon"]
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
        p["vargas"] = {n: varga_sign(p["lon"], n) for n in VARGA_NS}
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

def daily_indicators(chart, now):
    moon_now, _ = sidereal_lon(julian_day(now), swe.MOON)
    nak_now = int(moon_now // NAK_LEN)
    tara = TARAS[(nak_now - chart["planets"]["Moon"]["nak"]) % 9]
    msign = int(moon_now // 30)
    chandra = (msign - chart["planets"]["Moon"]["sign"]) % 12 + 1
    good_t, good_c = tara in GOOD_TARAS, chandra in (1, 3, 6, 7, 10, 11)
    return {"tara": tara, "good_tara": good_t, "chandra": chandra, "good_chandra": good_c,
            "house": house_of(chart, msign), "moon_nak": NAKSHATRAS[nak_now],
            "moon_sign": SIGNS[msign], "score": 45 + (25 if good_t else 0) + (25 if good_c else 0)}

def chart_text(chart, now):
    P = chart["planets"]
    lines = []
    if chart["time_unknown"]:
        lines.append("NOTE: Birth time unknown. Houses are counted from the Moon sign (Chandra Lagna). "
                     "Avoid Lagna, divisional-chart and exact-timing claims; dasha dates may be off by months.")
        lines.append(f"Chandra Lagna: {SIGNS[chart['asc_sign']]}")
    else:
        vl = "; ".join(f"D{n} {SHORT[varga_sign(chart['asc'], n)]}" for n in VARGA_NS)
        lines.append(f"Lagna: {SIGNS[chart['asc_sign']]} {chart['asc'] % 30:.1f}°. "
                     f"Divisional Lagnas: {vl}")
    rules = lordships(chart)
    lines.append("\nPLANETS:")
    for name, p in P.items():
        extra = [x for x in (p["dignity"], "retrograde" if p["retro"] else "") if x]
        ext = f" ({', '.join(extra)})" if extra else ""
        ruled = f", rules houses {', '.join(map(str, rules[name]))}" if name in rules else ""
        vg = ""
        if not chart["time_unknown"]:
            vg = "; " + ", ".join(f"D{n} {SHORT[p['vargas'][n]]}" for n in VARGA_NS)
        lines.append(f"{name}: {SIGNS[p['sign']]} {p['deg']:.1f}°, house {p['house']}{ext}{ruled}; "
                     f"{NAKSHATRAS[p['nak']]} pada {p['pada']}{vg}")
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

def kundali_svg(chart, n=1):
    asc_v = varga_sign(chart["asc"], n)
    houses = {h: [] for h in range(1, 13)}
    for name, p in chart["planets"].items():
        s = p["sign"] if n == 1 else p["vargas"][n]
        houses[(s - asc_v) % 12 + 1].append(ABBR[name])
    if not chart["time_unknown"]:
        houses[1].insert(0, "Asc")
    parts = ['<div style="text-align:center"><svg viewBox="0 0 300 300" width="100%" style="max-width:380px">',
             '<rect x="2" y="2" width="296" height="296" rx="8" fill="#3C3489" stroke="#FAC775" stroke-width="1.5"/>',
             '<g stroke="#FAC775" stroke-width="1" fill="none"><line x1="2" y1="2" x2="298" y2="298"/>'
             '<line x1="298" y1="2" x2="2" y2="298"/><polygon points="150,2 298,150 150,298 2,150"/></g>']
    for h, (x, y) in HOUSE_POS.items():
        sign_no = (asc_v + h - 1) % 12 + 1
        parts.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-size="11" fill="#FAC775">{" ".join(houses[h])}</text>')
        parts.append(f'<text x="{x}" y="{y + 13}" text-anchor="middle" font-size="9" fill="#AFA9EC">{sign_no}</text>')
    parts.append("</svg></div>")
    return "".join(parts)

def chart_from_profile(profile):
    bd = date.fromisoformat(profile["birth_date"])
    bt = datetime.strptime(profile["birth_time"][:5], "%H:%M").time()
    return compute_chart(datetime.combine(bd, bt), profile["lat"], profile["lon"],
                         profile["time_unknown"])

def get_chart(profile):
    key = (f"{profile['id']}|{profile['birth_date']}|{profile['birth_time']}|"
           f"{profile['time_unknown']}|{profile['lat']}|{profile['lon']}")
    cache = st.session_state.setdefault("chart_cache", {})
    if key not in cache:
        cache[key] = chart_from_profile(profile)
    return cache[key]

# ---------------- MATCHMAKING (ASHTAKOOT) ----------------
VARNA = [3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1, 4]   # 4 Brahmin, 3 Kshatriya, 2 Vaishya, 1 Shudra
VASHYA_TABLE = [[2, 1, 1, 0.5, 1], [1, 2, 0.5, 0, 1], [1, 0.5, 2, 1, 1],
                [0.5, 0, 1, 2, 0], [1, 1, 1, 0, 2]]
NAK_GANA = "DMRMDMDDRRMMDRDRDRRMMDRRMMD"
GANA_TABLE = {"D": {"D": 6, "M": 6, "R": 1}, "M": {"D": 5, "M": 6, "R": 0},
              "R": {"D": 1, "M": 0, "R": 6}}
GANA_NAME = {"D": "Deva", "M": "Manushya", "R": "Rakshasa"}
ANIMALS = ["Horse", "Elephant", "Sheep", "Serpent", "Dog", "Cat", "Rat", "Cow",
           "Buffalo", "Tiger", "Deer", "Monkey", "Mongoose", "Lion"]
NAK_YONI = [0, 1, 2, 3, 3, 4, 5, 2, 5, 6, 6, 7, 8, 9, 8, 9, 10, 10, 4, 11, 12, 11, 13, 0, 13, 7, 1]
YONI_TABLE = [
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1], [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1], [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1], [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2], [1, 2, 3, 1, 2, 2, 2, 4, 3, 0, 3, 2, 2, 1],
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1], [1, 1, 1, 2, 1, 1, 2, 0, 1, 4, 1, 1, 2, 1],
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1], [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2], [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4]]
FRIENDS = {"Sun": {"Moon", "Mars", "Jupiter"}, "Moon": {"Sun", "Mercury"},
           "Mars": {"Sun", "Moon", "Jupiter"}, "Mercury": {"Sun", "Venus"},
           "Jupiter": {"Sun", "Moon", "Mars"}, "Venus": {"Mercury", "Saturn"},
           "Saturn": {"Mercury", "Venus"}}
ENEMIES = {"Sun": {"Venus", "Saturn"}, "Moon": set(), "Mars": {"Mercury"},
           "Mercury": {"Moon"}, "Jupiter": {"Mercury", "Venus"},
           "Venus": {"Sun", "Moon"}, "Saturn": {"Sun", "Moon", "Mars"}}
NADI = [0, 1, 2, 2, 1, 0]   # repeats every 6 nakshatras: Adi, Madhya, Antya
MANGLIK_HOUSES = (1, 2, 4, 7, 8, 12)

def vashya_class(sign, deg):
    if sign == 8:
        return 1 if deg < 15 else 0
    if sign == 9:
        return 0 if deg < 15 else 2
    return [0, 0, 1, 2, 3, 1, 1, 4, 0, 0, 1, 2][sign]

def relation(a, b):
    return "F" if b in FRIENDS[a] else "E" if b in ENEMIES[a] else "N"

def tara_ok(frm, to):
    r = ((to - frm) % 27 + 1) % 9 or 9
    return r not in (3, 5, 7)

def ashtakoot(boy, girl):
    bm, gm = boy["planets"]["Moon"], girl["planets"]["Moon"]
    bs, gs, bn, gn = bm["sign"], gm["sign"], bm["nak"], gm["nak"]
    rows = []
    rows.append(("Varna", 1 if VARNA[bs] >= VARNA[gs] else 0, 1, "Values and work approach"))
    rows.append(("Vashya", VASHYA_TABLE[vashya_class(bs, bm["deg"])][vashya_class(gs, gm["deg"])], 2,
                 "Mutual attraction and influence"))
    t = tara_ok(gn, bn) + tara_ok(bn, gn)
    rows.append(("Tara", {2: 3, 1: 1.5, 0: 0}[t], 3, "Wellbeing and fortune together"))
    rows.append(("Yoni", YONI_TABLE[NAK_YONI[bn]][NAK_YONI[gn]], 4,
                 f"Physical and intimate harmony ({ANIMALS[NAK_YONI[bn]]} and {ANIMALS[NAK_YONI[gn]]})"))
    l1, l2 = SIGN_LORDS[bs], SIGN_LORDS[gs]
    if l1 == l2:
        gm_score = 5
    else:
        pair = tuple(sorted([relation(l1, l2), relation(l2, l1)]))
        gm_score = {("F", "F"): 5, ("F", "N"): 4, ("N", "N"): 3, ("E", "F"): 1,
                    ("E", "N"): 0.5, ("E", "E"): 0}[pair]
    rows.append(("Graha Maitri", gm_score, 5, f"Mental wavelength and friendship ({l1} and {l2})"))
    rows.append(("Gana", GANA_TABLE[NAK_GANA[bn]][NAK_GANA[gn]], 6,
                 f"Temperament ({GANA_NAME[NAK_GANA[bn]]} and {GANA_NAME[NAK_GANA[gn]]})"))
    d1, d2 = (gs - bs) % 12 + 1, (bs - gs) % 12 + 1
    bad = {(2, 12), (12, 2), (5, 9), (9, 5), (6, 8), (8, 6)}
    rows.append(("Bhakoot", 0 if (d1, d2) in bad else 7, 7, "Emotional bond and family welfare"))
    rows.append(("Nadi", 0 if NADI[bn % 6] == NADI[gn % 6] else 8, 8,
                 "Health and constitution (traditional)"))
    return rows

def manglik(chart):
    mars = chart["planets"]["Mars"]
    from_moon = (mars["sign"] - chart["planets"]["Moon"]["sign"]) % 12 + 1 in MANGLIK_HOUSES
    from_lagna = None if chart["time_unknown"] else mars["house"] in MANGLIK_HOUSES
    return from_lagna, from_moon

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

# ---------------- SAFETY & AI ----------------
CRISIS_WORDS = ["suicide", "kill myself", "end my life", "want to die", "self harm",
                "self-harm", "hurt myself", "no reason to live", "आत्महत्या",
                "मरना चाहता", "मरना चाहती", "जीना नहीं चाहता", "जीना नहीं चाहती"]
CRISIS_REPLY = ("I'm really glad you told me, and I'm going to pause the astrology for now, "
                "because you matter more than any chart.\n\n"
                "Please talk to someone right now. **Tele-MANAS: 14416** (free, 24/7, "
                "in many Indian languages). If you're in immediate danger, call **112**.\n\n"
                "If you can, reach out to someone you trust and let them know how you're feeling. "
                "I'm here whenever you want to talk again.")
RESTING = "I'm resting for a moment. Please ask again in a minute."

def system_prompt(lang, chart_name, rel):
    who = ("The user is asking about their own chart." if rel == "Self" else
           f"This chart belongs to {chart_name}, the user's {rel.lower()}. "
           f"Speak about {chart_name} in the third person.")
    return f"""You are Dishara (written दिशारा in Hindi), a warm, expert Vedic astrologer in the
Parashari tradition. {who} Give specific, well-reasoned guidance that leaves people clear,
capable and hopeful.

HOW TO ANALYSE (every time, silently):
1. Identify the life area and its houses: career 10, 6, 2, 11 + D10; money 2, 11, 5, 9 + D2;
   marriage/relationships 7, 2, 11, Venus + D9; education 4, 5, 9, Mercury, Jupiter + D24;
   home/property 4 + D4; children 5, Jupiter + D7; siblings/courage 3 + D3; parents 4, 9 + D12;
   travel/abroad 3, 9, 12; health 1, 6 (wellbeing habits only); spiritual growth 9, 12, Ketu.
2. For each relevant house: its sign, its lord, where that lord sits and its dignity,
   planets in it, aspects on it, and the natural significator. D1 is primary; use the
   divisional chart as supporting evidence.
3. Check yogas that involve these houses or planets.
4. Timing: does the current Mahadasha, Antardasha or Pratyantar lord own, occupy or aspect
   the relevant houses? Combine with Saturn and Jupiter transits. Name periods with months.
5. Weigh supportive and challenging factors and reach a clear conclusion.

HOW TO ANSWER (default):
- Bold headings: **What the chart shows** (2-4 bullets, each citing a specific factor),
  **Timing** (specific periods), **What you can do** (2-3 practical actions).
- Be specific to THIS chart. No generic Lagna or sun-sign personality text unless asked.
- Explain any Sanskrit term in a few words. Under 250 words.
- If the request says DAILY TIPS or COMPATIBILITY, follow the format given in the request instead.

RULES:
1. Use ONLY the data provided. Never invent positions, yogas, scores or dates.
2. Lead with strengths; frame challenges as growth areas with practical steps.
3. No fear: no curses, doshas as threats, gemstones or paid remedies.
4. Never predict death, illness, accidents, divorce, lottery or stock results.
5. If asked about death or lifespan, kindly say you don't predict that and turn to strengths.
   Only if the person sounds distressed or hopeless, keep astrology to a line or two, put
   support first, and suggest Tele-MANAS at 14416 (free, 24/7). Don't call it confidential.
6. If the chart notes the birth time is unknown, say once that you're reading the Moon chart,
   and avoid Lagna-based, divisional-chart or exact-timing claims.
7. Reply in {lang}. Write your own name correctly in that language's script."""

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

def ask_dishara(prompt, lang, chart_name,
