import time
import html
from datetime import datetime, date, time as dtime, timedelta, timezone

import streamlit as st
import swisseph as swe
from geopy.geocoders import Nominatim
from google import genai
from google.genai import types, errors

st.set_page_config(page_title="Dishara", page_icon="🌅", layout="centered")

FEEDBACK_URL = "https://forms.gle/paste-your-link-here"

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
.stButton > button, .stFormSubmitButton > button {background:#EF9F27; color:#412402; border:none; border-radius:999px; font-weight:500; padding:0.5rem 1.6rem;}
.stButton > button:hover, .stFormSubmitButton > button:hover {background:#FAC775; color:#412402;}
.stTabs [aria-selected="true"] {color:#FAC775 !important;}
</style>""", unsafe_allow_html=True)

# ---------------- ASTRO DATA ----------------
SIGNS = ["Mesha (Aries)", "Vrishabha (Taurus)", "Mithuna (Gemini)", "Karka (Cancer)",
         "Simha (Leo)", "Kanya (Virgo)", "Tula (Libra)", "Vrishchika (Scorpio)",
         "Dhanu (Sagittarius)", "Makara (Capricorn)", "Kumbha (Aquarius)", "Meena (Pisces)"]
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

def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

def julian_day(dt_utc):
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600)

def sidereal_lon(jd, pid):
    xx, _ = swe.calc_ut(jd, pid, FLAGS)
    return xx[0], xx[3] < 0

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

def upcoming_subperiods(chart, now, count=8):
    out = []
    for md in chart["dashas"]:
        if md["end"] < now:
            continue
        for ad in antardashas(md):
            if ad["end"] >= now and len(out) < count:
                out.append(ad)
    return out

def compute_chart(local_dt, lat, lng):
    utc = local_dt - timedelta(hours=IST)
    jd = julian_day(utc)
    _, ascmc = swe.houses_ex(jd, lat, lng, b'P', FLAGS)
    asc = ascmc[0]
    asc_sign = int(asc // 30)
    planets = {}
    for name, pid in PLANETS.items():
        plon, retro = sidereal_lon(jd, pid)
        planets[name] = {"lon": plon, "retro": retro and name != "Rahu"}
    planets["Ketu"] = {"lon": (planets["Rahu"]["lon"] + 180) % 360, "retro": False}
    for p in planets.values():
        p["sign"] = int(p["lon"] // 30)
        p["deg"] = p["lon"] % 30
        p["house"] = (p["sign"] - asc_sign) % 12 + 1
        p["nak"] = int(p["lon"] // NAK_LEN)
        p["pada"] = int((p["lon"] % NAK_LEN) // (NAK_LEN / 4)) + 1
    return {"asc": asc, "asc_sign": asc_sign, "planets": planets,
            "dashas": vimshottari(planets["Moon"]["lon"], utc)}

def moon_today_house(chart, now):
    moon_now, _ = sidereal_lon(julian_day(now), swe.MOON)
    return (int(moon_now // 30) - chart["asc_sign"]) % 12 + 1

def chart_text(chart, now):
    lines = [f"Lagna (Ascendant): {SIGNS[chart['asc_sign']]} {chart['asc'] % 30:.2f}°"]
    for name, p in chart["planets"].items():
        r = ", retrograde" if p["retro"] else ""
        lines.append(f"{name}: {SIGNS[p['sign']]} {p['deg']:.2f}°, house {p['house']}, "
                     f"{NAKSHATRAS[p['nak']]} pada {p['pada']}{r}")
    for d in chart["dashas"]:
        tag = " (CURRENT)" if d["start"] <= now < d["end"] else ""
        lines.append(f"Mahadasha {d['lord']}: {d['start']:%b %Y} to {d['end']:%b %Y}{tag}")
    for ad in upcoming_subperiods(chart, now):
        tag = " (CURRENT)" if ad["start"] <= now < ad["end"] else ""
        lines.append(f"Sub-period {ad['md']}-{ad['lord']}: {ad['start']:%b %Y} to {ad['end']:%b %Y}{tag}")
    lines.append(f"Today's date: {now:%d %b %Y}")
    lines.append(f"Today's Moon transit: house {moon_today_house(chart, now)} from Lagna")
    return "\n".join(lines)

HOUSE_POS = {1: (150, 80), 2: (76, 27), 3: (27, 76), 4: (75, 150), 5: (27, 224),
             6: (76, 270), 7: (150, 222), 8: (224, 270), 9: (273, 224),
             10: (225, 150), 11: (273, 76), 12: (224, 27)}

def kundali_svg(chart):
    houses = {h: [] for h in range(1, 13)}
    for name, p in chart["planets"].items():
        houses[p["house"]].append(ABBR[name])
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

def system_prompt(lang):
    return f"""You are Dishara (written दिशारा in Hindi), a warm and wise Vedic astrology guide.
Your purpose is to help people feel clear, capable and hopeful.

RULES:
1. Use ONLY the chart data provided. Never invent planet positions or dates.
2. Always explain WHY: name the planet, house or dasha behind each point.
3. Lead with strengths. Frame challenges as growth areas with practical steps.
4. Never use fear. No curses, doshas as threats, gemstones or paid remedies.
5. Never predict death, illness, accidents, divorce, lottery or stock results.
6. If asked about death or lifespan, kindly say you don't predict that and turn to
   strengths. Only if the person sounds distressed or hopeless, keep astrology to a
   line or two, put support first, and suggest Tele-MANAS at 14416 (free, 24/7).
   Don't describe it as confidential.
7. For timing questions, use the sub-periods (Mahadasha-Antardasha) and name them.
8. Keep answers under 180 words, simple words, explain any jargon.
9. Reply in {lang}. Write your own name correctly in that language's script."""

# ---------------- AI ----------------
@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def get_models():
    skip = ["image", "tts", "audio", "live", "embedding", "robotics", "computer", "2.5"]
    avail = [m.name.replace("models/", "") for m in get_client().models.list()
             if "generateContent" in (m.supported_actions or [])]
    models = [m for m in avail if "flash" in m and not any(s in m for s in skip)]
    return sorted(models, key=lambda m: 0 if m == "gemini-flash-lite-latest"
                  else 1 if m.endswith("-latest") else 2)

def ask_dishara(prompt, lang):
    client = get_client()
    for model in get_models()[:6]:
        for attempt in range(2):
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system_prompt(lang),
                                                       temperature=0.7))
                return r.text
            except errors.ServerError:
                time.sleep(2 * (attempt + 1))
            except errors.ClientError:
                break
    return "I'm resting for a moment. Please ask again in a minute."

@st.cache_data(show_spinner=False)
def geocode(place):
    try:
        loc = Nominatim(user_agent="dishara-app").geocode(place, country_codes="in", timeout=10)
        return (loc.latitude, loc.longitude, loc.address) if loc else None
    except Exception:
        return None

# ---------------- ONBOARDING ----------------
if "chart" not in st.session_state:
    st.markdown("""<div style="text-align:center;padding:24px 0 8px">
      <svg viewBox="0 0 200 120" width="220"><g stroke="#FAC775" stroke-width="2" stroke-linecap="round">
      <line x1="100" y1="8" x2="100" y2="26"/><line x1="40" y1="33" x2="53" y2="46"/><line x1="160" y1="33" x2="147" y2="46"/>
      <line x1="14" y1="90" x2="31" y2="90"/><line x1="186" y1="90" x2="169" y2="90"/></g>
      <path d="M45 98 A55 55 0 0 1 155 98 Z" fill="#EF9F27"/><path d="M68 98 A32 32 0 0 1 132 98 Z" fill="#FAC775"/>
      <line x1="10" y1="98" x2="190" y2="98" stroke="#7F77DD" stroke-width="1.5"/></svg>
      <h1 style="font-size:52px;margin:0">Dishara</h1>
      <p class="gold" style="margin:0">दिशारा</p>
      <p style="color:#CECBF6;font-size:16px">Your stars, your direction.<br>Every night ends in a sunrise.</p>
    </div>""", unsafe_allow_html=True)

    with st.form("birth"):
        name = st.text_input("Your name")
        c1, c2 = st.columns(2)
        bdate = c1.date_input("Birth date", value=date(1995, 1, 1),
                              min_value=date(1900, 1, 1), max_value=date.today())
        btime = c2.time_input("Birth time", value=dtime(12, 0), step=60)
        place = st.text_input("Birth place", placeholder="Bengaluru, Karnataka")
        lang = st.selectbox("Language", ["English", "Hindi", "Kannada", "Tamil",
                                         "Telugu", "Marathi", "Bengali", "Gujarati"])
        go = st.form_submit_button("Begin my journey")

    if go:
        if not name.strip() or not place.strip():
            st.error("Enter your name and birth place to continue.")
        else:
            with st.spinner("Reading the sky at your birth..."):
                loc = geocode(place.strip())
            if not loc:
                st.error("Couldn't find that place. Try adding the state, like 'Mysuru, Karnataka'.")
            else:
                chart = compute_chart(datetime.combine(bdate, btime), loc[0], loc[1])
                st.session_state.update(chart=chart, name=name.strip(), lang=lang,
                                        place=loc[2], messages=[])
                st.rerun()
    st.caption("Births in India only for now. Your details stay in this session.")
    st.stop()

# ---------------- MAIN APP ----------------
chart = st.session_state.chart
name = html.escape(st.session_state.name)
lang = st.session_state.lang
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
    if st.button("Show my natural strengths"):
        with st.spinner("Dishara is reading your chart..."):
            st.session_state.strengths = ask_dishara(
                f"BIRTH CHART:\n{chart_text(chart, now)}\n\nDescribe my 3 biggest natural "
                f"strengths from this chart, with the reason for each.", lang)
    if "strengths" in st.session_state:
        st.markdown(st.session_state.strengths)

with chat:
    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar="🌅" if m["role"] == "assistant" else None):
            st.markdown(m["content"])
    q = st.chat_input("Ask anything about your life")
    if q:
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        if any(w in q.lower() for w in CRISIS_WORDS):
            answer = CRISIS_REPLY
        else:
            history = "\n".join(f"{m['role']}: {m['content']}"
                                for m in st.session_state.messages[-7:-1])
            prompt = (f"BIRTH CHART:\n{chart_text(chart, now)}\n\n"
                      f"EARLIER IN THIS CONVERSATION:\n{history or 'None'}\n\nQUESTION: {q}")
            with st.spinner("Dishara is thinking..."):
                answer = ask_dishara(prompt, lang)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant", avatar="🌅"):
            st.markdown(answer)

with kundali:
    st.markdown(kundali_svg(chart), unsafe_allow_html=True)
    st.caption("North Indian style · numbers show the sign in each house")
    rows = [{"Planet": n + (" (R)" if p["retro"] else ""), "Sign": SIGNS[p["sign"]],
             "Degree": f"{p['deg']:.2f}°", "House": p["house"],
             "Nakshatra": f"{NAKSHATRAS[p['nak']]} {p['pada']}"}
            for n, p in chart["planets"].items()]
    st.dataframe(rows, hide_index=True)
    st.markdown("#### Life chapters")
    for d in chart["dashas"]:
        mark = "  ← now" if d is cur else ""
        st.markdown(f"**{d['lord']}** · {d['start']:%b %Y} – {d['end']:%b %Y}{mark}")

st.divider()
if "paste-your-link" not in FEEDBACK_URL:
    st.markdown(f"<p class='muted' style='text-align:center'>Help shape Dishara: "
                f"<a href='{FEEDBACK_URL}' style='color:#FAC775'>share your feedback</a></p>",
                unsafe_allow_html=True)
if st.button("Start over with new details"):
    st.session_state.clear()
    st.rerun()
