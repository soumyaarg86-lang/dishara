import os
import io
import json
import math
import time
import html
import urllib.parse
from datetime import datetime, date, timedelta, timezone

import requests
import streamlit as st
import swisseph as swe
from PIL import Image, ImageDraw, ImageFont, features
from geopy.geocoders import Photon, Nominatim
from google import genai
from google.genai import types, errors
from supabase import create_client

st.set_page_config(page_title="Dishara", page_icon="🌅", layout="centered")

FEEDBACK_URL = "https://forms.gle/paste-your-link-here"
APP_URL = "https://dishara.streamlit.app"
RELATIONS = ["Self", "Spouse / Partner", "Mother", "Father", "Son", "Daughter",
             "Sibling", "Friend", "Other"]
CHART_VERSION = 4

# =====================================================================
# LANGUAGES & TRANSLATIONS
# =====================================================================
LANG_CODES = {"en": "English", "hi": "हिन्दी", "bn": "বাংলা"}
ANSWER_LANG = {"en": "English", "hi": "Hindi", "bn": "Bengali"}
LI = {"en": 0, "hi": 1, "bn": 2}

def L():
    return st.session_state.get("ui_lang", "en")

def pick(tup):
    return tup[LI[L()]]

def pl(tup, lang):
    return tup[LI[lang]]

T = {
    "tagline": ("Your stars, your direction.<br>Every night ends in a sunrise.",
                "आपके सितारे, आपकी दिशा।<br>हर रात के बाद सवेरा होता है।",
                "আপনার তারা, আপনার দিশা।<br>প্রতিটি রাতের শেষে আসে ভোর।"),
    "signin_intro": ("Sign in with your email to save your charts and conversations.",
                     "अपनी कुंडलियाँ और बातचीत सहेजने के लिए ईमेल से साइन इन करें।",
                     "আপনার কুণ্ডলী ও কথোপকথন সংরক্ষণ করতে ইমেল দিয়ে সাইন ইন করুন।"),
    "tab_signin": ("Sign in", "साइन इन", "সাইন ইন"),
    "tab_signup": ("Create account", "खाता बनाएँ", "অ্যাকাউন্ট তৈরি করুন"),
    "email": ("Email", "ईमेल", "ইমেল"),
    "password": ("Password", "पासवर्ड", "পাসওয়ার্ড"),
    "password_new": ("Password (at least 8 characters)", "पासवर्ड (कम से कम 8 अक्षर)", "পাসওয়ার্ড (কমপক্ষে 8 অক্ষর)"),
    "email_hint": ("Your browser can remember your email for next time. To use a different one, just type it in.",
                   "आपका ब्राउज़र अगली बार के लिए आपका ईमेल याद रख सकता है। दूसरा ईमेल इस्तेमाल करने के लिए बस उसे टाइप करें।",
                   "আপনার ব্রাউজার পরের বারের জন্য আপনার ইমেল মনে রাখতে পারে। অন্য ইমেল ব্যবহার করতে শুধু সেটি টাইপ করুন।"),
    "autofill": ("Your browser filled in the boxes, but the app didn't receive them. Please click inside the Email "
                 "and Password boxes (or press Tab through them), then click Sign in again.",
                 "आपके ब्राउज़र ने बॉक्स भर दिए, लेकिन ऐप तक जानकारी नहीं पहुँची। कृपया ईमेल और पासवर्ड बॉक्स में एक बार "
                 "क्लिक करें (या Tab दबाएँ), फिर दोबारा साइन इन दबाएँ।",
                 "আপনার ব্রাউজার বাক্সগুলি পূরণ করেছে, কিন্তু অ্যাপ তথ্যটি পায়নি। অনুগ্রহ করে ইমেল ও পাসওয়ার্ড বাক্সে একবার "
                 "ক্লিক করুন (বা Tab চাপুন), তারপর আবার সাইন ইন চাপুন।"),
    "signin_failed": ("Couldn't sign in. Check your email and password.",
                      "साइन इन नहीं हो सका। अपना ईमेल और पासवर्ड जाँचें।",
                      "সাইন ইন করা যায়নি। আপনার ইমেল ও পাসওয়ার্ড দেখুন।"),
    "pw_short": ("Please use a password of at least 8 characters.",
                 "कृपया कम से कम 8 अक्षरों का पासवर्ड रखें।",
                 "অনুগ্রহ করে কমপক্ষে 8 অক্ষরের পাসওয়ার্ড দিন।"),
    "need_consent": ("Please tick the consent box to continue.",
                     "आगे बढ़ने के लिए कृपया सहमति बॉक्स पर टिक करें।",
                     "এগিয়ে যেতে অনুগ্রহ করে সম্মতির বাক্সে টিক দিন।"),
    "check_email": ("Account created. Check your email to confirm, then sign in.",
                    "खाता बन गया। पुष्टि के लिए अपना ईमेल देखें, फिर साइन इन करें।",
                    "অ্যাকাউন্ট তৈরি হয়েছে। নিশ্চিত করতে ইমেল দেখুন, তারপর সাইন ইন করুন।"),
    "signup_failed": ("Couldn't create the account: {err}", "खाता नहीं बन सका: {err}", "অ্যাকাউন্ট তৈরি করা যায়নি: {err}"),
    "privacy_link": ("Privacy policy", "गोपनीयता नीति", "গোপনীয়তা নীতি"),
    "consent": ("I agree that Dishara can store birth details and conversations to personalise guidance. "
                "I can ask for them to be deleted anytime.",
                "मैं सहमत हूँ कि दिशारा व्यक्तिगत मार्गदर्शन के लिए जन्म विवरण और बातचीत सहेज सकती है। "
                "मैं कभी भी इन्हें हटाने का अनुरोध कर सकता/सकती हूँ।",
                "আমি সম্মত যে দিশারা ব্যক্তিগত পরামর্শের জন্য জন্মের তথ্য ও কথোপকথন সংরক্ষণ করতে পারে। "
                "আমি যেকোনো সময় এগুলি মুছে ফেলার অনুরোধ করতে পারি।"),
    "edit_birth": ("Edit birth details", "जन्म विवरण बदलें", "জন্মের তথ্য সম্পাদনা করুন"),
    "add_chart_title": ("Add a birth chart", "नई कुंडली जोड़ें", "নতুন কুণ্ডলী যোগ করুন"),
    "name": ("Name", "नाम", "নাম"),
    "whose_chart": ("Whose chart is this?", "यह किसकी कुंडली है?", "এটি কার কুণ্ডলী?"),
    "birth_date": ("Birth date", "जन्म तिथि", "জন্ম তারিখ"),
    "unknown_time": ("I don't know the exact birth time", "मुझे सही जन्म समय नहीं पता", "আমি সঠিক জন্মসময় জানি না"),
    "time_hint": ("Birth time (you can type to jump, e.g. 7 or 45)",
                  "जन्म समय (टाइप करके सीधे चुन सकते हैं, जैसे 7 या 45)",
                  "জন্মসময় (টাইপ করে সরাসরি বেছে নিতে পারেন, যেমন 7 বা 45)"),
    "hour": ("Hour", "घंटा", "ঘণ্টা"),
    "minute": ("Minute", "मिनट", "মিনিট"),
    "ampm": ("AM / PM", "AM / PM", "AM / PM"),
    "unknown_caption": ("No problem. Dishara will read the Moon chart, which is still very meaningful.",
                        "कोई बात नहीं। दिशारा चंद्र कुंडली पढ़ेगी, जो फिर भी बहुत सार्थक है।",
                        "কোনো অসুবিধা নেই। দিশারা চন্দ্র কুণ্ডলী পড়বে, যা এখনও খুবই অর্থবহ।"),
    "current_place": ("Current birth place: {place}", "वर्तमान जन्म स्थान: {place}", "বর্তমান জন্মস্থান: {place}"),
    "place_label": ("Birth place: type the town or city and press Enter",
                    "जन्म स्थान: शहर या कस्बे का नाम अंग्रेज़ी में लिखें और Enter दबाएँ",
                    "জন্মস্থান: শহর বা নগরের নাম ইংরেজিতে লিখে Enter চাপুন"),
    "city_label": ("City: type the town or city and press Enter",
                   "शहर: नाम अंग्रेज़ी में लिखें और Enter दबाएँ",
                   "শহর: নাম ইংরেজিতে লিখে Enter চাপুন"),
    "place_ph": ("e.g. Mysuru", "जैसे Varanasi", "যেমন Kolkata"),
    "finding_places": ("Finding places...", "स्थान खोजे जा रहे हैं...", "স্থান খোঁজা হচ্ছে..."),
    "select_place": ("Select the place", "स्थान चुनें", "স্থান বেছে নিন"),
    "choose_place": ("Choose the correct place", "सही स्थान चुनें", "সঠিক স্থানটি বেছে নিন"),
    "no_match": ("No match found. Check the spelling, or try the nearest bigger town.",
                 "कोई स्थान नहीं मिला। वर्तनी जाँचें, या पास का बड़ा शहर आज़माएँ।",
                 "কোনো মিল পাওয়া যায়নি। বানান দেখুন, অথবা কাছের বড় শহরের নাম দিন।"),
    "save_chart": ("Save chart", "कुंडली सहेजें", "কুণ্ডলী সংরক্ষণ করুন"),
    "please_add": ("Please add: {items}.", "कृपया जोड़ें: {items}।", "অনুগ্রহ করে যোগ করুন: {items}।"),
    "p_name": ("a name", "नाम", "নাম"),
    "p_date": ("the birth date", "जन्म तिथि", "জন্ম তারিখ"),
    "p_time": ("hour, minute and AM/PM", "घंटा, मिनट और AM/PM", "ঘণ্টা, মিনিট ও AM/PM"),
    "p_place": ("the birth place (pick one from the list)", "जन्म स्थान (सूची से चुनें)", "জন্মস্থান (তালিকা থেকে বেছে নিন)"),
    "save_failed": ("Couldn't save the chart: {err}", "कुंडली सहेजी नहीं जा सकी: {err}", "কুণ্ডলী সংরক্ষণ করা যায়নি: {err}"),
    "cancel": ("Cancel", "रद्द करें", "বাতিল"),
    "delete_confirm": ("Yes, permanently delete {name}'s chart and its conversations",
                       "हाँ, {name} की कुंडली और उसकी बातचीत स्थायी रूप से हटाएँ",
                       "হ্যাঁ, {name}-এর কুণ্ডলী ও কথোপকথন স্থায়ীভাবে মুছে ফেলুন"),
    "delete_chart": ("Delete this chart", "यह कुंडली हटाएँ", "এই কুণ্ডলী মুছুন"),
    "shubh_din": ("Shubh din", "शुभ दिन", "শুভ দিন"),
    "namaste": ("Namaste, {name}", "नमस्ते, {name}", "নমস্কার, {name}"),
    "viewing_chart": ("Viewing chart", "देखी जा रही कुंडली", "যে কুণ্ডলী দেখছেন"),
    "add_chart_btn": ("+ Add chart", "+ कुंडली जोड़ें", "+ কুণ্ডলী যোগ"),
    "tab_home": ("Home", "होम", "হোম"),
    "tab_ask": ("Ask Dishara", "दिशारा से पूछें", "দিশারাকে জিজ্ঞাসা"),
    "tab_kundali": ("Kundali", "कुंडली", "কুণ্ডলী"),
    "tab_match": ("Match Making", "कुंडली मिलान", "কোষ্ঠী মিলন"),
    "tab_share": ("Share", "शेयर", "শেয়ার"),
    "todays_energy": ("Today's energy · {date}", "आज की ऊर्जा · {date}", "আজকের শক্তি · {date}"),
    "why_score": ("Why: the Moon is in {nak}, giving {name} a {tara} tara ({tara_word}). It's in the {ch} sign "
                  "from the natal Moon ({ch_word}) and the {house} house of the chart.",
                  "कारण: चंद्रमा {nak} नक्षत्र में है, जिससे {name} के लिए {tara} तारा बनती है ({tara_word})। "
                  "यह जन्म चंद्र से {ch} राशि में है ({ch_word}) और कुंडली के {house} भाव में है।",
                  "কারণ: চন্দ্র {nak} নক্ষত্রে আছে, যা {name}-এর জন্য {tara} তারা তৈরি করে ({tara_word})। "
                  "এটি জন্মচন্দ্র থেকে {ch} রাশিতে ({ch_word}) এবং কুণ্ডলীর {house} ভাবে আছে।"),
    "av_line": (" Ashtakavarga gives the Moon {b} of 8 points in today's sign.",
                " अष्टकवर्ग में आज की राशि में चंद्रमा को 8 में से {b} अंक मिलते हैं।",
                " অষ্টকবর্গে আজকের রাশিতে চন্দ্র 8-এর মধ্যে {b} বিন্দু পায়।"),
    "tw_support": ("supportive", "सहायक", "সহায়ক"),
    "tw_reflect": ("a reflective day", "चिंतन का दिन", "চিন্তনের দিন"),
    "tw_gentle": ("a day to go gently", "धीरे चलने का दिन", "ধীরে চলার দিন"),
    "cw_good": ("favourable", "अनुकूल", "অনুকূল"),
    "cw_patience": ("asks for patience", "धैर्य माँगता है", "ধৈর্য চায়"),
    "score_expander": ("What does this score mean?", "इस स्कोर का क्या अर्थ है?", "এই স্কোরের অর্থ কী?"),
    "today_tag": ("today", "आज", "আজ"),
    "about_score": ("About this score", "इस स्कोर के बारे में", "এই স্কোর সম্পর্কে"),
    "about1": ("The score is set once each morning (6 AM IST) and stays the same all day. It combines three classical "
               "Vedic checks of the Moon: Tara Bala, today's nakshatra counted from your birth star (up to 20 points); "
               "Chandra Bala, today's Moon sign counted from your birth Moon (20); and Ashtakavarga, the Moon's "
               "classical point score (0 to 8) in the sign it's moving through (up to 15). If the birth time is "
               "unknown, the third check uses the Moon's house instead.",
               "यह स्कोर हर सुबह (भारतीय समय 6 बजे) एक बार तय होता है और पूरे दिन वही रहता है। इसमें चंद्रमा की तीन "
               "शास्त्रीय वैदिक जाँचें शामिल हैं: तारा बल, यानी जन्म नक्षत्र से आज के नक्षत्र की गिनती (20 अंक तक); "
               "चंद्र बल, यानी जन्म चंद्र से आज की चंद्र राशि की गिनती (20); और अष्टकवर्ग, यानी जिस राशि से चंद्रमा "
               "गुज़र रहा है उसमें उसके शास्त्रीय अंक (0 से 8), जिनसे 15 अंक तक मिलते हैं। जन्म समय अज्ञात हो तो "
               "तीसरी जाँच में चंद्रमा का भाव देखा जाता है।",
               "স্কোরটি প্রতিদিন সকালে একবার (ভারতীয় সময় সকাল 6টা) নির্ধারিত হয় এবং সারাদিন একই থাকে। এতে চন্দ্রের "
               "তিনটি শাস্ত্রীয় বৈদিক পরীক্ষা রয়েছে: তারা বল, অর্থাৎ জন্মনক্ষত্র থেকে আজকের নক্ষত্রের গণনা (20 পর্যন্ত); "
               "চন্দ্র বল, অর্থাৎ জন্মচন্দ্র থেকে আজকের চন্দ্ররাশির গণনা (20); এবং অষ্টকবর্গ, অর্থাৎ চন্দ্র যে রাশিতে "
               "আছে সেখানে তার শাস্ত্রীয় বিন্দু (0 থেকে 8), যা থেকে 15 পর্যন্ত পাওয়া যায়। জন্মসময় অজানা হলে তৃতীয় "
               "পরীক্ষায় চন্দ্রের ভাব দেখা হয়।"),
    "about2": ("Method updated on 5 Nov 2026 to use Ashtakavarga and to stay fixed through the day. Think of it as a "
               "gentle guide to the day's mood, not a fixed prediction. There are no bad days, only days suited to "
               "different things.",
               "5 नवंबर 2026 को पद्धति अपडेट की गई: अब इसमें अष्टकवर्ग शामिल है और स्कोर पूरे दिन स्थिर रहता है। इसे "
               "दिन के मिज़ाज का एक सौम्य संकेत मानें, कोई निश्चित भविष्यवाणी नहीं। कोई दिन बुरा नहीं होता, हर दिन "
               "अलग कामों के लिए उपयुक्त होता है।",
               "5 নভেম্বর 2026-এ পদ্ধতি হালনাগাদ করা হয়েছে: এখন এতে অষ্টকবর্গ ব্যবহৃত হয় এবং স্কোর সারাদিন স্থির থাকে। "
               "এটিকে দিনের মেজাজের একটি কোমল ইঙ্গিত হিসেবে দেখুন, নির্দিষ্ট ভবিষ্যদ্বাণী নয়। কোনো দিনই খারাপ নয়, "
               "প্রতিটি দিন আলাদা কাজের জন্য উপযুক্ত।"),
    "preparing_tips": ("Preparing today's personal tips...", "आज के व्यक्तिगत सुझाव तैयार हो रहे हैं...",
                       "আজকের ব্যক্তিগত পরামর্শ তৈরি হচ্ছে..."),
    "tips_soon": ("Today's tips will appear shortly. Refresh in a minute.",
                  "आज के सुझाव जल्द ही दिखेंगे। एक मिनट में रिफ्रेश करें।",
                  "আজকের পরামর্শ শীঘ্রই দেখা যাবে। এক মিনিট পরে রিফ্রেশ করুন।"),
    "todays_tips": ("Today's personal tips", "आज के व्यक्तिगत सुझाव", "আজকের ব্যক্তিগত পরামর্শ"),
    "current_chapter": ("Current chapter · until {date}", "वर्तमान अध्याय · {date} तक", "বর্তমান অধ্যায় · {date} পর্যন্ত"),
    "mahadasha": ("{lord} Mahadasha: {theme}", "{lord} महादशा: {theme}", "{lord} মহাদশা: {theme}"),
    "current_sub": ("Current sub-period · until {date}", "वर्तमान अंतर्दशा · {date} तक", "বর্তমান অন্তর্দশা · {date} পর্যন্ত"),
    "moon_chart_caption": ("Reading from the Moon chart, since the birth time is unknown.",
                           "जन्म समय अज्ञात होने के कारण चंद्र कुंडली से पढ़ा जा रहा है।",
                           "জন্মসময় অজানা, তাই চন্দ্র কুণ্ডলী থেকে পড়া হচ্ছে।"),
    "pan_title": ("Today's Panchang", "आज का पंचांग", "আজকের পঞ্চাঙ্গ"),
    "pan_change": ("Change city", "शहर बदलें", "শহর বদলান"),
    "pan_for": ("For {place}", "स्थान: {place}", "স্থান: {place}"),
    "pan_sunrise": ("Sunrise", "सूर्योदय", "সূর্যোদয়"),
    "pan_sunset": ("Sunset", "सूर्यास्त", "সূর্যাস্ত"),
    "pan_vara": ("Day", "वार", "বার"),
    "pan_tithi": ("Tithi", "तिथि", "তিথি"),
    "pan_yoga": ("Yoga", "योग", "যোগ"),
    "pan_karana": ("Karana", "करण", "করণ"),
    "pan_times": ("Key timings today", "आज के मुख्य समय", "আজকের গুরুত্বপূর্ণ সময়"),
    "pan_rahu": ("Rahu Kaal", "राहु काल", "রাহু কাল"),
    "pan_rahu_note": ("Traditionally avoided for new starts and important beginnings.",
                      "परंपरागत रूप से नई शुरुआत और महत्वपूर्ण कार्यों के लिए टाला जाता है।",
                      "ঐতিহ্যগতভাবে নতুন শুরু ও গুরুত্বপূর্ণ কাজের জন্য এড়ানো হয়।"),
    "pan_rahu_now": ("Rahu Kaal is on now, until {end}.", "अभी राहु काल चल रहा है, {end} तक।",
                     "এখন রাহু কাল চলছে, {end} পর্যন্ত।"),
    "pan_yama": ("Yamaganda", "यमगंड", "যমগণ্ড"),
    "pan_gulika": ("Gulika Kaal", "गुलिक काल", "গুলিক কাল"),
    "pan_abhijit": ("Abhijit Muhurta", "अभिजित मुहूर्त", "অভিজিৎ মুহূর্ত"),
    "pan_abhijit_note": ("Traditionally auspicious for important work.",
                         "परंपरागत रूप से महत्वपूर्ण कार्यों के लिए शुभ।",
                         "ঐতিহ্যগতভাবে গুরুত্বপূর্ণ কাজের জন্য শুভ।"),
    "pan_abhijit_wed": ("(traditionally not used on Wednesdays)", "(बुधवार को परंपरागत रूप से नहीं लिया जाता)",
                        "(বুধবারে ঐতিহ্যগতভাবে ব্যবহৃত হয় না)"),
    "pan_note": ("Tithi, nakshatra, yoga and karana are shown as at sunrise, following tradition. Timings are for "
                 "the selected city; the birth place is used by default.",
                 "परंपरा के अनुसार तिथि, नक्षत्र, योग और करण सूर्योदय के समय के दिखाए गए हैं। समय चुने गए शहर के अनुसार "
                 "हैं; डिफ़ॉल्ट रूप से जन्म स्थान लिया जाता है।",
                 "ঐতিহ্য অনুযায়ী তিথি, নক্ষত্র, যোগ ও করণ সূর্যোদয়ের সময়ের দেখানো হয়েছে। সময়গুলি বেছে নেওয়া শহরের "
                 "জন্য; ডিফল্টভাবে জন্মস্থান ব্যবহৃত হয়।"),
    "pan_error": ("Panchang couldn't be calculated right now.", "पंचांग अभी गणना नहीं हो सका।",
                  "পঞ্চাঙ্গ এখন গণনা করা যায়নি।"),
    "sh_title": ("Share a card", "कार्ड शेयर करें", "কার্ড শেয়ার করুন"),
    "sh_sub": ("New messages every morning. Cards never show birth details.",
               "हर सुबह नए संदेश। कार्ड पर कभी जन्म विवरण नहीं दिखते।",
               "প্রতিদিন সকালে নতুন বার্তা। কার্ডে কখনো জন্মের তথ্য দেখানো হয় না।"),
    "k_my_rashi": ("My Rashi", "मेरी राशि", "আমার রাশি"),
    "k_my_nak": ("My nakshatra", "मेरा नक्षत्र", "আমার নক্ষত্র"),
    "k_today_me": ("Today for me", "आज मेरे लिए", "আজ আমার জন্য"),
    "k_guide": ("Rashi guide", "राशि मार्गदर्शन", "রাশি নির্দেশিকা"),
    "k_thought": ("Thought of the day", "आज का विचार", "আজকের ভাবনা"),
    "k_festival": ("Festival wish", "त्योहार की शुभकामना", "উৎসবের শুভেচ্ছা"),
    "sh_lang": ("Card language", "कार्ड की भाषा", "কার্ডের ভাষা"),
    "sh_fest": ("Festival", "त्योहार", "উৎসব"),
    "sh_another": ("Show another", "दूसरा दिखाएँ", "আরেকটি দেখুন"),
    "sh_name": ("Add your name (optional)", "अपना नाम जोड़ें (वैकल्पिक)", "আপনার নাম যোগ করুন (ঐচ্ছিক)"),
    "sh_download": ("Download card", "कार्ड डाउनलोड करें", "কার্ড ডাউনলোড করুন"),
    "sh_whatsapp": ("Share on WhatsApp", "WhatsApp पर शेयर करें", "WhatsApp-এ শেয়ার করুন"),
    "sh_hint": ("Download the card, then attach it in WhatsApp or Instagram.",
                "कार्ड डाउनलोड करें, फिर उसे WhatsApp या Instagram में जोड़ें।",
                "কার্ডটি ডাউনলোড করে WhatsApp বা Instagram-এ যুক্ত করুন।"),
    "sh_fresh": ("Today's fresh messages are being prepared. Refresh in a minute to see them.",
                 "आज के नए संदेश तैयार हो रहे हैं। देखने के लिए एक मिनट बाद रिफ्रेश करें।",
                 "আজকের নতুন বার্তা তৈরি হচ্ছে। দেখতে এক মিনিট পরে রিফ্রেশ করুন।"),
    "sh_lang_off": ("Hindi and Bengali cards need fonts that aren't available right now, so this card is in English.",
                    "हिंदी और बांग्ला कार्ड के लिए ज़रूरी फ़ॉन्ट अभी उपलब्ध नहीं हैं, इसलिए यह कार्ड अंग्रेज़ी में है।",
                    "হিন্দি ও বাংলা কার্ডের জন্য প্রয়োজনীয় ফন্ট এখন পাওয়া যাচ্ছে না, তাই এই কার্ডটি ইংরেজিতে।"),
    "sh_wa_msg": ("Made with Dishara. Get your free daily guide: {url}",
                  "दिशारा से बनाया गया। अपना मुफ़्त दैनिक मार्गदर्शन पाएँ: {url}",
                  "দিশারা দিয়ে তৈরি। আপনার বিনামূল্যে দৈনিক নির্দেশিকা পান: {url}"),
    "new_conv": ("New conversation", "नई बातचीत", "নতুন কথোপকথন"),
    "past_conv": ("Open a past conversation ({n})", "पिछली बातचीत खोलें ({n})", "আগের কথোপকথন খুলুন ({n})"),
    "ask_intro": ("Ask anything about {name}'s chart: career, relationships, timing, strengths...",
                  "{name} की कुंडली के बारे में कुछ भी पूछें: करियर, रिश्ते, समय, क्षमताएँ...",
                  "{name}-এর কুণ্ডলী সম্পর্কে যেকোনো প্রশ্ন করুন: কর্মজীবন, সম্পর্ক, সময়, শক্তি..."),
    "chat_ph": ("Ask anything about this chart", "इस कुंडली के बारे में कुछ भी पूछें", "এই কুণ্ডলী সম্পর্কে যেকোনো প্রশ্ন করুন"),
    "thinking": ("Dishara is studying the chart...", "दिशारा कुंडली का अध्ययन कर रही है...", "দিশারা কুণ্ডলী বিশ্লেষণ করছে..."),
    "chart_select": ("Chart", "चार्ट", "চার্ট"),
    "chart_caption": ("North Indian style · numbers show the sign in each house",
                      "उत्तर भारतीय शैली · अंक प्रत्येक भाव की राशि दर्शाते हैं",
                      "উত্তর ভারতীয় শৈলী · সংখ্যাগুলি প্রতিটি ভাবের রাশি দেখায়"),
    "chart_caption_moon": (" · Moon chart (birth time unknown; divisional charts need the exact time)",
                           " · चंद्र कुंडली (जन्म समय अज्ञात; वर्ग कुंडलियों के लिए सही समय चाहिए)",
                           " · চন্দ্র কুণ্ডলী (জন্মসময় অজানা; বর্গ চার্টের জন্য সঠিক সময় প্রয়োজন)"),
    "col_planet": ("Planet", "ग्रह", "গ্রহ"),
    "col_sign": ("Sign", "राशि", "রাশি"),
    "col_degree": ("Degree", "अंश", "অংশ"),
    "col_house": ("House", "भाव", "ভাব"),
    "col_role": ("Role", "भूमिका", "ভূমিকা"),
    "col_notes": ("Notes", "टिप्पणी", "মন্তব্য"),
    "col_nak": ("Nakshatra", "नक्षत्र", "নক্ষত্র"),
    "glossary_title": ("What do Role and Notes mean?", "भूमिका और टिप्पणी का क्या अर्थ है?", "ভূমিকা ও মন্তব্যের অর্থ কী?"),
    "roles_moon": ("Roles are read from the Moon sign here, since the birth time is unknown.",
                   "जन्म समय अज्ञात होने के कारण यहाँ भूमिकाएँ चंद्र राशि से पढ़ी गई हैं।",
                   "জন্মসময় অজানা, তাই এখানে ভূমিকা চন্দ্ররাশি থেকে পড়া হয়েছে।"),
    "life_areas": ("Life areas at a glance", "जीवन क्षेत्र एक नज़र में", "এক নজরে জীবনের ক্ষেত্রগুলি"),
    "col_area": ("Area", "क्षेत्र", "ক্ষেত্র"),
    "col_outlook": ("Outlook", "संभावना", "সম্ভাবনা"),
    "col_strength": ("Key strength", "मुख्य शक्ति", "প্রধান শক্তি"),
    "col_dt": ("Next double transit", "अगला दोहरा गोचर", "পরবর্তী দ্বৈত গোচর"),
    "not_2y": ("Not in next 2 years", "अगले 2 वर्षों में नहीं", "আগামী 2 বছরে নেই"),
    "areas_caption": ("Outlook is calculated from the house lord's placement and strength, planets in and aspecting "
                      "the house, the natural significator, the relevant divisional chart and Ashtakavarga. Double "
                      "transit is when Jupiter and Saturn both influence the area's main house: a classical timing "
                      "signal. Ask Dishara about any area for the full picture.",
                      "संभावना की गणना भाव स्वामी की स्थिति और बल, भाव में स्थित और उस पर दृष्टि डालने वाले ग्रहों, "
                      "प्राकृतिक कारक, संबंधित वर्ग कुंडली और अष्टकवर्ग से की जाती है। दोहरा गोचर तब होता है जब गुरु "
                      "और शनि दोनों उस क्षेत्र के मुख्य भाव को प्रभावित करते हैं, जो समय का एक शास्त्रीय संकेत है। पूरी "
                      "जानकारी के लिए दिशारा से किसी भी क्षेत्र के बारे में पूछें।",
                      "সম্ভাবনা নির্ণয় করা হয় ভাবপতির অবস্থান ও শক্তি, ভাবে থাকা ও দৃষ্টি দেওয়া গ্রহ, প্রাকৃতিক কারক, "
                      "সংশ্লিষ্ট বর্গ চার্ট এবং অষ্টকবর্গ থেকে। দ্বৈত গোচর হলো যখন বৃহস্পতি ও শনি দুজনেই ক্ষেত্রটির প্রধান "
                      "ভাবকে প্রভাবিত করে, যা সময় নির্ধারণের একটি শাস্ত্রীয় সংকেত। পূর্ণ চিত্রের জন্য দিশারাকে যেকোনো "
                      "ক্ষেত্র সম্পর্কে জিজ্ঞাসা করুন।"),
    "av_title": ("Ashtakavarga strength by house", "भाव अनुसार अष्टकवर्ग बल", "ভাব অনুযায়ী অষ্টকবর্গ শক্তি"),
    "col_points": ("Points", "अंक", "বিন্দু"),
    "col_av_strength": ("Strength", "बल", "শক্তি"),
    "av_strong": ("Strong", "मज़बूत", "শক্তিশালী"),
    "av_avg": ("Average", "औसत", "মাঝারি"),
    "av_build": ("Build steadily", "धीरे-धीरे बनाएँ", "ধীরে ধীরে গড়ে তুলুন"),
    "av_caption": ("Classical point system: 28 or more is strong, 25 to 27 average, below 25 asks for steady effort. "
                   "Total: {total} (always 337 when calculated correctly).",
                   "शास्त्रीय अंक प्रणाली: 28 या अधिक मज़बूत, 25 से 27 औसत, 25 से कम पर निरंतर प्रयास चाहिए। "
                   "कुल: {total} (सही गणना में हमेशा 337)।",
                   "শাস্ত্রীয় বিন্দু পদ্ধতি: 28 বা তার বেশি শক্তিশালী, 25 থেকে 27 মাঝারি, 25-এর নিচে নিয়মিত প্রচেষ্টা "
                   "প্রয়োজন। মোট: {total} (সঠিক গণনায় সর্বদা 337)।"),
    "yogas": ("Yogas", "योग", "যোগ"),
    "en_detail_note": ("", "विस्तृत विवरण अभी अंग्रेज़ी में हैं; जल्द ही हिंदी में उपलब्ध होंगे।",
                       "বিস্তারিত বিবরণ আপাতত ইংরেজিতে; শীঘ্রই বাংলায় আসবে।"),
    "life_chapters": ("Life chapters", "जीवन के अध्याय", "জীবনের অধ্যায়"),
    "now": ("now", "अभी", "এখন"),
    "add_partner": ("Add your partner's chart first: tap **+ Add chart** and choose 'Spouse / Partner'. "
                    "Then come back here.",
                    "पहले अपने साथी की कुंडली जोड़ें: **+ कुंडली जोड़ें** दबाएँ और 'जीवनसाथी' चुनें। फिर यहाँ वापस आएँ।",
                    "প্রথমে আপনার সঙ্গীর কুণ্ডলী যোগ করুন: **+ কুণ্ডলী যোগ** চাপুন এবং 'জীবনসঙ্গী' বেছে নিন। "
                    "তারপর এখানে ফিরে আসুন।"),
    "partner1": ("Groom / Partner 1", "वर / साथी 1", "বর / সঙ্গী 1"),
    "partner2": ("Bride / Partner 2", "वधू / साथी 2", "কনে / সঙ্গী 2"),
    "choose_two": ("Choose two different charts.", "दो अलग-अलग कुंडलियाँ चुनें।", "দুটি আলাদা কুণ্ডলী বেছে নিন।"),
    "check_compat": ("Check compatibility", "मिलान देखें", "মিলন দেখুন"),
    "guna_milan": ("Ashtakoot Guna Milan", "अष्टकूट गुण मिलान", "অষ্টকূট গুণ মিলন"),
    "v_excellent": ("Excellent", "उत्तम", "অতি উত্তম"),
    "v_vgood": ("Very good", "बहुत अच्छा", "খুব ভালো"),
    "v_good": ("Good", "अच्छा", "ভালো"),
    "v_effort": ("Needs understanding and effort", "समझ और प्रयास की आवश्यकता", "বোঝাপড়া ও প্রচেষ্টা প্রয়োজন"),
    "match_note": ("18+ is traditionally considered suitable. A score is one view; the full charts and the two "
                   "people matter more.",
                   "परंपरागत रूप से 18+ उपयुक्त माना जाता है। अंक केवल एक दृष्टिकोण है; पूरी कुंडलियाँ और दोनों व्यक्ति "
                   "अधिक मायने रखते हैं।",
                   "ঐতিহ্যগতভাবে 18+ উপযুক্ত ধরা হয়। স্কোর একটি দিক মাত্র; সম্পূর্ণ কুণ্ডলী ও দুজন মানুষই বেশি গুরুত্বপূর্ণ।"),
    "col_koota": ("Koota", "कूट", "কূট"),
    "col_score": ("Score", "अंक", "স্কোর"),
    "col_reflects": ("What it reflects", "क्या दर्शाता है", "কী নির্দেশ করে"),
    "manglik_title": ("Mars placement (Manglik check)", "मंगल स्थिति (मांगलिक जाँच)", "মঙ্গলের অবস্থান (মাঙ্গলিক পরীক্ষা)"),
    "from_lagna": ("from Lagna", "लग्न से", "লগ্ন থেকে"),
    "from_moon": ("from Moon", "चंद्र से", "চন্দ্র থেকে"),
    "yes": ("yes", "हाँ", "হ্যাঁ"),
    "no": ("no", "नहीं", "না"),
    "unknown_nt": ("unknown (no birth time)", "अज्ञात (जन्म समय नहीं)", "অজানা (জন্মসময় নেই)"),
    "manglik_caption": ("Traditionally, if both partners have this Mars placement it balances out. It's one factor "
                        "among many, not a verdict.",
                        "परंपरा के अनुसार, यदि दोनों साथियों में मंगल की यह स्थिति हो तो यह संतुलित हो जाती है। यह कई "
                        "कारकों में से एक है, कोई अंतिम निर्णय नहीं।",
                        "ঐতিহ্য অনুযায়ী, দুজনেরই মঙ্গলের এই অবস্থান থাকলে তা ভারসাম্যে আসে। এটি অনেক বিষয়ের একটি, "
                        "কোনো চূড়ান্ত রায় নয়।"),
    "detailed_btn": ("Get detailed compatibility reading", "विस्तृत मिलान विश्लेषण पाएँ", "বিস্তারিত মিলন বিশ্লেষণ পান"),
    "comparing": ("Dishara is comparing both charts...", "दिशारा दोनों कुंडलियों की तुलना कर रही है...",
                  "দিশারা দুটি কুণ্ডলী তুলনা করছে..."),
    "feedback": ("Help shape Dishara:", "दिशारा को बेहतर बनाने में मदद करें:", "দিশারাকে আরও ভালো করতে সাহায্য করুন:"),
    "feedback_link": ("share your feedback", "अपनी राय दें", "আপনার মতামত দিন"),
    "signed_in": ("Signed in as {email}", "{email} के रूप में साइन इन", "{email} হিসেবে সাইন ইন"),
    "edit_chart": ("Edit this chart", "यह कुंडली बदलें", "এই কুণ্ডলী সম্পাদনা"),
    "sign_out": ("Sign out", "साइन आउट", "সাইন আউট"),
    "crisis_reply": (
        "I'm really glad you told me, and I'm going to pause the astrology for now, because you matter more than "
        "any chart.\n\nPlease talk to someone right now. **Tele-MANAS: 14416** (free, 24/7, in many Indian "
        "languages). If you're in immediate danger, call **112**.\n\nIf you can, reach out to someone you trust "
        "and let them know how you're feeling. I'm here whenever you want to talk again.",
        "मुझे खुशी है कि आपने मुझे बताया। मैं अभी ज्योतिष को रोक रही हूँ, क्योंकि आप किसी भी कुंडली से ज़्यादा मायने "
        "रखते हैं।\n\nकृपया अभी किसी से बात करें। **टेली-मानस: 14416** (निःशुल्क, 24x7, कई भारतीय भाषाओं में)। "
        "अगर आप तुरंत खतरे में हैं, तो **112** पर कॉल करें।\n\nहो सके तो किसी भरोसेमंद व्यक्ति से संपर्क करें और उन्हें "
        "बताएँ कि आप कैसा महसूस कर रहे हैं। जब भी आप फिर से बात करना चाहें, मैं यहाँ हूँ।",
        "আপনি আমাকে জানিয়েছেন বলে আমি সত্যিই খুশি। আমি এখন জ্যোতিষ থামিয়ে রাখছি, কারণ যেকোনো কুণ্ডলীর চেয়ে আপনি "
        "অনেক বেশি গুরুত্বপূর্ণ।\n\nঅনুগ্রহ করে এখনই কারও সঙ্গে কথা বলুন। **টেলি-মানস: 14416** (বিনামূল্যে, 24x7, "
        "অনেক ভারতীয় ভাষায়)। আপনি যদি তাৎক্ষণিক বিপদে থাকেন, **112**-এ ফোন করুন।\n\nসম্ভব হলে কোনো বিশ্বস্ত "
        "মানুষের সঙ্গে যোগাযোগ করুন এবং তাঁকে জানান আপনি কেমন বোধ করছেন। আবার কথা বলতে চাইলে আমি এখানেই আছি।"),
    "resting": ("I'm resting for a moment. Please ask again in a minute.",
                "मैं थोड़ा विश्राम कर रही हूँ। कृपया एक मिनट बाद फिर पूछें।",
                "আমি একটু বিশ্রাম নিচ্ছি। অনুগ্রহ করে এক মিনিট পরে আবার জিজ্ঞাসা করুন।"),
}

def t(key, **kw):
    s = pick(T[key])
    return s.format(**kw) if kw else s

SIGNS_HI = ["मेष", "वृषभ", "मिथुन", "कर्क", "सिंह", "कन्या", "तुला", "वृश्चिक", "धनु", "मकर", "कुंभ", "मीन"]
SIGNS_BN = ["মেষ", "বৃষ", "মিথুন", "কর্কট", "সিংহ", "কন্যা", "তুলা", "বৃশ্চিক", "ধনু", "মকর", "কুম্ভ", "মীন"]
NAK_HI = ["अश्विनी", "भरणी", "कृत्तिका", "रोहिणी", "मृगशिरा", "आर्द्रा", "पुनर्वसु", "पुष्य", "आश्लेषा", "मघा",
          "पूर्वा फाल्गुनी", "उत्तरा फाल्गुनी", "हस्त", "चित्रा", "स्वाति", "विशाखा", "अनुराधा", "ज्येष्ठा", "मूल",
          "पूर्वाषाढ़ा", "उत्तराषाढ़ा", "श्रवण", "धनिष्ठा", "शतभिषा", "पूर्वा भाद्रपद", "उत्तरा भाद्रपद", "रेवती"]
NAK_BN = ["অশ্বিনী", "ভরণী", "কৃত্তিকা", "রোহিণী", "মৃগশিরা", "আর্দ্রা", "পুনর্বসু", "পুষ্যা", "অশ্লেষা", "মঘা",
          "পূর্বফাল্গুনী", "উত্তরফাল্গুনী", "হস্তা", "চিত্রা", "স্বাতী", "বিশাখা", "অনুরাধা", "জ্যেষ্ঠা", "মূলা",
          "পূর্বাষাঢ়া", "উত্তরাষাঢ়া", "শ্রবণা", "ধনিষ্ঠা", "শতভিষা", "পূর্বভাদ্রপদ", "উত্তরভাদ্রপদ", "রেবতী"]
PLANET_T = {"Sun": ("Sun", "सूर्य", "সূর্য"), "Moon": ("Moon", "चंद्र", "চন্দ্র"), "Mars": ("Mars", "मंगल", "মঙ্গল"),
            "Mercury": ("Mercury", "बुध", "বুধ"), "Jupiter": ("Jupiter", "गुरु", "বৃহস্পতি"),
            "Venus": ("Venus", "शुक्र", "শুক্র"), "Saturn": ("Saturn", "शनि", "শনি"),
            "Rahu": ("Rahu", "राहु", "রাহু"), "Ketu": ("Ketu", "केतु", "কেতু")}
ABBR_T = {"Sun": ("Su", "सू", "র"), "Moon": ("Mo", "चं", "চ"), "Mars": ("Ma", "मं", "ম"),
          "Mercury": ("Me", "बु", "বু"), "Jupiter": ("Ju", "गु", "বৃ"), "Venus": ("Ve", "शु", "শু"),
          "Saturn": ("Sa", "श", "শ"), "Rahu": ("Ra", "रा", "রা"), "Ketu": ("Ke", "के", "কে")}
ASC_T = ("Asc", "ल", "ল")
TARA_T = {"Janma": ("Janma", "जन्म", "জন্ম"), "Sampat": ("Sampat", "संपत", "সম্পৎ"),
          "Vipat": ("Vipat", "विपत", "বিপৎ"), "Kshema": ("Kshema", "क्षेम", "ক্ষেম"),
          "Pratyak": ("Pratyak", "प्रत्यक", "প্রত্যক"), "Sadhana": ("Sadhana", "साधना", "সাধনা"),
          "Naidhana": ("Naidhana", "नैधन", "নৈধন"), "Mitra": ("Mitra", "मित्र", "মিত্র"),
          "Parama Mitra": ("Parama Mitra", "परम मित्र", "পরম মিত্র")}
ROLE_T = {"Lagna lord": ("Lagna lord", "लग्नेश", "লগ্নেশ"),
          "Yogakaraka": ("Yogakaraka", "योगकारक", "যোগকারক"),
          "Functional benefic": ("Functional benefic", "कार्यात्मक शुभ ग्रह", "কার্যকরী শুভ গ্রহ"),
          "Neutral": ("Neutral", "तटस्थ", "নিরপেক্ষ"),
          "Functional malefic": ("Functional malefic", "कार्यात्मक पाप ग्रह", "কার্যকরী পাপ গ্রহ"),
          "Acts through its sign lord": ("Acts through its sign lord", "राशि स्वामी के अनुसार फल",
                                         "রাশিপতির মাধ্যমে ফল")}
NOTE_T = {"exalted": ("exalted", "उच्च", "উচ্চ"), "own sign": ("own sign", "स्वराशि", "স্বক্ষেত্র"),
          "debilitated": ("debilitated", "नीच", "নীচ"),
          "debilitation cancelled": ("debilitation cancelled", "नीचभंग", "নীচভঙ্গ"),
          "combust": ("combust", "अस्त", "অস্ত"), "vargottama": ("vargottama", "वर्गोत्तम", "বর্গোত্তম"),
          "retrograde": ("retrograde", "वक्री", "বক্রী")}
RELATION_T = {"Self": ("Self", "स्वयं", "নিজে"), "Spouse / Partner": ("Spouse / Partner", "जीवनसाथी", "জীবনসঙ্গী"),
              "Mother": ("Mother", "माँ", "মা"), "Father": ("Father", "पिता", "বাবা"),
              "Son": ("Son", "बेटा", "ছেলে"), "Daughter": ("Daughter", "बेटी", "মেয়ে"),
              "Sibling": ("Sibling", "भाई-बहन", "ভাইবোন"), "Friend": ("Friend", "मित्र", "বন্ধু"),
              "Other": ("Other", "अन्य", "অন্যান্য")}
KOOTA_T = {"Varna": ("Varna", "वर्ण", "বর্ণ"), "Vashya": ("Vashya", "वश्य", "বশ্য"),
           "Tara": ("Tara", "तारा", "তারা"), "Yoni": ("Yoni", "योनि", "যোনি"),
           "Graha Maitri": ("Graha Maitri", "ग्रह मैत्री", "গ্রহমৈত্রী"), "Gana": ("Gana", "गण", "গণ"),
           "Bhakoot": ("Bhakoot", "भकूट", "ভকূট"), "Nadi": ("Nadi", "नाड़ी", "নাড়ী")}
AREA_T = {"career": ("Career & work", "करियर और काम", "কর্মজীবন ও কাজ"),
          "money": ("Money & wealth", "धन और संपत्ति", "অর্থ ও সম্পদ"),
          "marriage": ("Marriage & relationships", "विवाह और रिश्ते", "বিবাহ ও সম্পর্ক"),
          "education": ("Education & learning", "शिक्षा", "শিক্ষা"),
          "property": ("Home & property", "घर और संपत्ति", "বাড়ি ও সম্পত্তি"),
          "children": ("Children", "संतान", "সন্তান"),
          "travel": ("Travel & abroad", "यात्रा और विदेश", "ভ্রমণ ও বিদেশ"),
          "health": ("Health & wellbeing habits", "स्वास्थ्य की आदतें", "স্বাস্থ্যকর অভ্যাস"),
          "spiritual": ("Inner growth", "आंतरिक विकास", "অন্তরের বিকাশ")}
VERDICT_T = {"Strongly supported": ("Strongly supported", "प्रबल रूप से समर्थित", "দৃঢ়ভাবে সমর্থিত"),
             "Supported": ("Supported", "समर्थित", "সমর্থিত"),
             "Balanced": ("Balanced", "संतुलित", "ভারসাম্যপূর্ণ"),
             "Needs steady effort": ("Needs steady effort", "निरंतर प्रयास चाहिए", "নিয়মিত প্রচেষ্টা প্রয়োজন"),
             "Asks for patience and long-term effort": ("Asks for patience and long-term effort",
                                                        "धैर्य और दीर्घकालिक प्रयास चाहिए",
                                                        "ধৈর্য ও দীর্ঘমেয়াদি প্রচেষ্টা প্রয়োজন")}
VARGA_LIST = [
    (1, ("D1 · Rashi (overall life)", "D1 · राशि (समग्र जीवन)", "D1 · রাশি (সমগ্র জীবন)")),
    (2, ("D2 · Hora (wealth)", "D2 · होरा (धन)", "D2 · হোরা (সম্পদ)")),
    (3, ("D3 · Drekkana (siblings, courage)", "D3 · द्रेष्काण (भाई-बहन, साहस)", "D3 · দ্রেক্কাণ (ভাইবোন, সাহস)")),
    (4, ("D4 · Chaturthamsa (home, property)", "D4 · चतुर्थांश (घर, संपत्ति)", "D4 · চতুর্থাংশ (বাড়ি, সম্পত্তি)")),
    (7, ("D7 · Saptamsa (children)", "D7 · सप्तांश (संतान)", "D7 · সপ্তাংশ (সন্তান)")),
    (9, ("D9 · Navamsa (marriage, inner strength)", "D9 · नवांश (विवाह, आंतरिक शक्ति)",
         "D9 · নবাংশ (বিবাহ, অন্তরের শক্তি)")),
    (10, ("D10 · Dasamsa (career)", "D10 · दशांश (करियर)", "D10 · দশাংশ (কর্মজীবন)")),
    (12, ("D12 · Dwadasamsa (parents)", "D12 · द्वादशांश (माता-पिता)", "D12 · দ্বাদশাংশ (পিতামাতা)")),
    (24, ("D24 · Chaturvimsamsa (education)", "D24 · चतुर्विंशांश (शिक्षा)", "D24 · চতুর্বিংশাংশ (শিক্ষা)")),
]
CHAPTER_THEME_T = {
    "Sun": ("confidence and leadership", "आत्मविश्वास और नेतृत्व", "আত্মবিশ্বাস ও নেতৃত্ব"),
    "Moon": ("emotions and nurturing", "भावनाएँ और पोषण", "আবেগ ও যত্ন"),
    "Mars": ("courage and action", "साहस और कर्म", "সাহস ও কর্ম"),
    "Mercury": ("learning and communication", "सीखना और संवाद", "শেখা ও যোগাযোগ"),
    "Jupiter": ("growth and wisdom", "विकास और ज्ञान", "বৃদ্ধি ও জ্ঞান"),
    "Venus": ("love, comfort and creativity", "प्रेम, सुख और रचनात्मकता", "প্রেম, স্বাচ্ছন্দ্য ও সৃজনশীলতা"),
    "Saturn": ("discipline and lasting results", "अनुशासन और स्थायी परिणाम", "শৃঙ্খলা ও স্থায়ী ফল"),
    "Rahu": ("ambition and new territory", "महत्वाकांक्षा और नई राहें", "উচ্চাকাঙ্ক্ষা ও নতুন পথ"),
    "Ketu": ("reflection and inner clarity", "चिंतन और आंतरिक स्पष्टता", "চিন্তন ও অন্তরের স্বচ্ছতা")}
MOON_HOUSE_T = {
    1: ("A fresh-start feeling. Put yourself first today.", "नई शुरुआत का एहसास। आज खुद को प्राथमिकता दें।",
        "নতুন শুরুর অনুভূতি। আজ নিজেকে অগ্রাধিকার দিন।"),
    2: ("Good for family time and money planning.", "परिवार के साथ समय और धन की योजना के लिए अच्छा।",
        "পরিবারের সঙ্গে সময় ও অর্থ পরিকল্পনার জন্য ভালো।"),
    3: ("Courage is high. Make that call or start something small.",
        "साहस ऊँचा है। वह फ़ोन कर लें या कुछ छोटा शुरू करें।", "সাহস বেশি। সেই ফোনটা করে ফেলুন বা ছোট কিছু শুরু করুন।"),
    4: ("A day for home, comfort and recharging.", "घर, आराम और ऊर्जा फिर से भरने का दिन।",
        "বাড়ি, আরাম ও নতুন করে শক্তি সঞ্চয়ের দিন।"),
    5: ("Creative and playful. Learn, create, enjoy.", "रचनात्मक और खुशमिज़ाज। सीखें, रचें, आनंद लें।",
        "সৃজনশীল ও আনন্দময়। শিখুন, সৃষ্টি করুন, উপভোগ করুন।"),
    6: ("Great for clearing pending tasks and health routines.", "अधूरे काम और सेहत की दिनचर्या निपटाने के लिए बढ़िया।",
        "জমে থাকা কাজ ও স্বাস্থ্যের রুটিন সারার জন্য চমৎকার।"),
    7: ("Partnerships shine. Meetings and relationships flow.", "साझेदारी चमकती है। बैठकें और रिश्ते सहज चलते हैं।",
        "অংশীদারিত্ব উজ্জ্বল। বৈঠক ও সম্পর্ক সহজে এগোয়।"),
    8: ("Go inward. Research, reflect and rest more.", "भीतर झाँकें। शोध करें, विचार करें और ज़्यादा आराम करें।",
        "অন্তর্মুখী হোন। গবেষণা করুন, ভাবুন ও বেশি বিশ্রাম নিন।"),
    9: ("Luck and wisdom. Learn, plan and seek guidance.", "भाग्य और ज्ञान। सीखें, योजना बनाएँ और मार्गदर्शन लें।",
        "ভাগ্য ও জ্ঞান। শিখুন, পরিকল্পনা করুন ও পরামর্শ নিন।"),
    10: ("Career spotlight. Show your work.", "करियर पर रोशनी। अपना काम दिखाएँ।", "কর্মজীবনে আলো। আপনার কাজ তুলে ধরুন।"),
    11: ("Gains and friendships. Network and ask for support.", "लाभ और मित्रता। संपर्क बढ़ाएँ और सहयोग माँगें।",
         "লাভ ও বন্ধুত্ব। যোগাযোগ বাড়ান ও সহায়তা চান।"),
    12: ("Slow down. Rest, let go and plan quietly.", "गति धीमी करें। आराम करें, छोड़ दें और शांति से योजना बनाएँ।",
         "গতি কমান। বিশ্রাম নিন, ছেড়ে দিন ও শান্তভাবে পরিকল্পনা করুন।")}
SCORE_BANDS = [(85, 100, "Strong day"), (70, 84, "Steady day"), (55, 69, "Gentle day"), (45, 54, "Quiet, reflective day")]
BAND_T = {
    "Strong day": (("Strong day", "Good for important starts, key meetings and decisions."),
                   ("मज़बूत दिन", "महत्वपूर्ण शुरुआत, ज़रूरी बैठकों और फ़ैसलों के लिए अच्छा।"),
                   ("শক্তিশালী দিন", "গুরুত্বপূর্ণ শুরু, জরুরি বৈঠক ও সিদ্ধান্তের জন্য ভালো।")),
    "Steady day": (("Steady day", "Good for regular work, follow-ups and steady progress."),
                   ("स्थिर दिन", "नियमित काम, फ़ॉलो-अप और लगातार प्रगति के लिए अच्छा।"),
                   ("স্থির দিন", "নিয়মিত কাজ, ফলো-আপ ও ধারাবাহিক অগ্রগতির জন্য ভালো।")),
    "Gentle day": (("Gentle day", "Keep plans simple. Finish things rather than start new ones."),
                   ("सौम्य दिन", "योजनाएँ सरल रखें। नया शुरू करने की बजाय काम पूरे करें।"),
                   ("কোমল দিন", "পরিকল্পনা সহজ রাখুন। নতুন শুরুর চেয়ে কাজ শেষ করায় মন দিন।")),
    "Quiet, reflective day": (("Quiet, reflective day", "Rest, plan and reflect. Avoid rushing big decisions."),
                              ("शांत, चिंतनशील दिन", "आराम करें, योजना बनाएँ और विचार करें। बड़े फ़ैसलों में जल्दबाज़ी न करें।"),
                              ("শান্ত, চিন্তনের দিন", "বিশ্রাম নিন, পরিকল্পনা করুন ও ভাবুন। বড় সিদ্ধান্তে তাড়াহুড়ো করবেন না।")),
}
BN_ORD = {1: "ম", 2: "য়", 3: "য়", 4: "র্থ", 5: "ম", 6: "ষ্ঠ", 7: "ম", 8: "ম", 9: "ম", 10: "ম", 11: "শ", 12: "শ"}

def ord_l(n):
    if L() == "hi":
        return "पहले" if n == 1 else f"{n}वें"
    if L() == "bn":
        return f"{n}{BN_ORD.get(n, 'তম')}"
    return ordinal(n)

def sign_name(i):
    return pick((SIGNS[i], SIGNS_HI[i], SIGNS_BN[i]))

def short_sign(i):
    return pick((SHORT[i], SIGNS_HI[i], SIGNS_BN[i]))

def nak_name(i):
    return pick((NAKSHATRAS[i], NAK_HI[i], NAK_BN[i]))

def planet_name(p):
    return pick(PLANET_T[p])

# ---------------- STYLE ----------------
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Poppins:wght@300;400;500&family=Noto+Sans+Devanagari:wght@400;500&family=Noto+Sans+Bengali:wght@400;500&family=Noto+Serif+Devanagari:wght@500;600&family=Noto+Serif+Bengali:wght@500;600&display=swap');
html, body, p, label, li, .stMarkdown {font-family:'Poppins','Noto Sans Devanagari','Noto Sans Bengali',sans-serif;}
h1, h2, h3, h4 {font-family:'Cormorant Garamond','Noto Serif Devanagari','Noto Serif Bengali',serif !important; color:#FAC775 !important;}
.card {background:#3C3489; border-radius:16px; padding:16px 18px; margin-bottom:12px;}
.muted {color:#AFA9EC; font-size:13px; margin:0;}
.gold {color:#FAC775;}
.big {font-size:17px; font-weight:500; margin:4px 0;}
.bar {height:6px; background:#534AB7; border-radius:3px; margin-top:8px;}
.bar > div {height:6px; background:#FAC775; border-radius:3px;}
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {background:#EF9F27; color:#412402; border:none; border-radius:999px; font-weight:500; padding:0.45rem 1.4rem;}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {background:#FAC775; color:#412402;}
.stTabs [aria-selected="true"] {color:#FAC775 !important;}
</style>""", unsafe_allow_html=True)

BIG_NUMBER = "font-size:40px;font-weight:500;color:#FAC775;margin:0;line-height:1.2"
SMALL_SUFFIX = "font-size:15px;color:#AFA9EC"

# ---------------- PRIVACY POLICY PAGE (dishara.streamlit.app/?page=privacy) ----------------
PRIVACY_POLICY = """
# Dishara Privacy Policy
*Last updated: 6 November 2026*

Dishara ("we") is a Vedic astrology guidance app. This policy explains what we collect and how we use it.

**What we collect**
- Your email address, when you create an account.
- Birth details you enter for yourself or others: name, relationship, birth date, birth time and birth place.
- Your questions to Dishara and the answers it gives, your daily tips, and your language preference.

**How we use it**
- To calculate birth charts and give you personalised guidance, daily tips and compatibility readings.
- To remember your past conversations so guidance stays consistent.
- We do not sell your data or use it for advertising.

**AI processing**
Answers are generated by Google's Gemini AI. To create an answer, your question and the relevant chart
details are sent to Google. During our beta we use Gemini's free tier, under which Google may use this
content to improve its products. Please don't include sensitive personal information you don't want shared.

**Shareable cards**
Cards you create show only your name (if you add it), your Moon sign or nakshatra, and general daily
messages. They never show your birth date, time or place.

**Where data is stored**
Your data is stored with Supabase (database) and the app is hosted on Streamlit Community Cloud.
Access is restricted so that each signed-in user can only see their own data.

**Your choices and rights**
You can edit or delete any chart in the app; deleting a chart also deletes its conversations.
To access, correct or delete all your data, email us at your-email@gmail.com and we will act within 30 days.

**Important**
Dishara offers astrology-based guidance for reflection and self-understanding. It is not medical, legal,
financial or psychological advice. If you are in distress, please call Tele-MANAS at 14416 (free, 24/7).
Dishara is intended for users aged 18 and over.

**Changes**
We may update this policy and will show the new date above.

**Contact**
your-email@gmail.com
"""

if st.query_params.get("page") == "privacy":
    st.markdown(PRIVACY_POLICY)
    st.stop()

# ---------------- SECRETS & DATABASE ----------------
def secret(name):
    return os.environ.get(name) or st.secrets[name]

@st.cache_resource
def db():
    return create_client(secret("SUPABASE_URL"), secret("SUPABASE_SERVICE_KEY"))

def auth_client():
    if "sb_auth" not in st.session_state:
        st.session_state.sb_auth = create_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"))
    return st.session_state.sb_auth

def get_or_create_user(email, name, lang):
    email = email.strip().lower()
    rows = db().table("app_users").select("id,language").eq("email", email).limit(1).execute().data
    if rows:
        return rows[0]["id"], (rows[0].get("language") or "en")
    new = db().table("app_users").insert({"email": email, "name": name, "language": lang}).execute().data[0]
    return new["id"], lang

def save_user_lang(uid, code):
    try:
        db().table("app_users").update({"language": code}).eq("id", uid).execute()
    except Exception:
        pass

def list_charts(uid):
    return (db().table("profiles").select("*").eq("user_id", uid)
            .order("created_at").execute().data)

def list_conversations(uid, pid):
    return (db().table("conversations").select("id,title,created_at").eq("user_id", uid)
            .eq("profile_id", pid).order("created_at", desc=True).limit(40).execute().data)

def load_conversation(uid, cid):
    return (db().table("messages").select("role,content").eq("user_id", uid)
            .eq("conversation_id", cid).order("created_at").execute().data)

def new_conversation(uid, pid, title):
    return (db().table("conversations").insert(
        {"user_id": uid, "profile_id": pid, "title": title[:80]}).execute().data[0]["id"])

def save_message(uid, cid, role, content):
    try:
        db().table("messages").insert({"user_id": uid, "conversation_id": cid,
                                       "role": role, "content": content}).execute()
    except Exception:
        pass

def get_saved_tip(uid, pid, day, lang):
    try:
        rows = (db().table("daily_tips").select("content").eq("user_id", uid).eq("profile_id", pid)
                .eq("day", day.isoformat()).eq("lang", lang).limit(1).execute().data)
        return rows[0]["content"] if rows else None
    except Exception:
        return None

def save_tip(uid, pid, day, lang, content):
    try:
        db().table("daily_tips").upsert({"user_id": uid, "profile_id": pid, "day": day.isoformat(),
                                         "lang": lang, "content": content},
                                        on_conflict="profile_id,day,lang").execute()
    except Exception:
        pass

def get_daily_cards(day_iso, lang):
    try:
        rows = (db().table("daily_cards").select("content").eq("day", day_iso).eq("lang", lang)
                .limit(1).execute().data)
        return rows[0]["content"] if rows else None
    except Exception:
        return None

def save_daily_cards(day_iso, lang, content):
    try:
        db().table("daily_cards").upsert({"day": day_iso, "lang": lang, "content": content},
                                         on_conflict="day,lang").execute()
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
SEVEN = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
NATURAL_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
EXALT = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5, "Jupiter": 3, "Venus": 11, "Saturn": 6}
OWN = {"Sun": [4], "Moon": [3], "Mars": [0, 7], "Mercury": [2, 5],
       "Jupiter": [8, 11], "Venus": [1, 6], "Saturn": [9, 10]}
SPECIAL_ASPECTS = {"Mars": [4, 8], "Jupiter": [5, 9], "Saturn": [3, 10]}
COMBUST_ORBS = {"Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15}
HOUSE_TOPICS = {1: "self, body, direction", 2: "money, family, speech",
                3: "courage, siblings, skills, short travel", 4: "home, mother, property, peace",
                5: "education, creativity, children, romance", 6: "work routine, competition, health habits",
                7: "marriage, partnerships, clients", 8: "transformation, research, shared resources",
                9: "luck, higher learning, mentors, long travel", 10: "career, status, public work",
                11: "gains, income, friends, ambitions", 12: "rest, expenses, foreign lands, spirituality"}
VARGA_NS = [2, 3, 4, 7, 9, 10, 12, 24]
BAV_RULES = {
    "Sun": {"Sun": [1, 2, 4, 7, 8, 9, 10, 11], "Moon": [3, 6, 10, 11], "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
            "Mercury": [3, 5, 6, 9, 10, 11, 12], "Jupiter": [5, 6, 9, 11], "Venus": [6, 7, 12],
            "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Lagna": [3, 4, 6, 10, 11, 12]},
    "Moon": {"Sun": [3, 6, 7, 8, 10, 11], "Moon": [1, 3, 6, 7, 10, 11], "Mars": [2, 3, 5, 6, 9, 10, 11],
             "Mercury": [1, 3, 4, 5, 7, 8, 10, 11], "Jupiter": [1, 4, 7, 8, 10, 11, 12],
             "Venus": [3, 4, 5, 7, 9, 10, 11], "Saturn": [3, 5, 6, 11], "Lagna": [3, 6, 10, 11]},
    "Mars": {"Sun": [3, 5, 6, 10, 11], "Moon": [3, 6, 11], "Mars": [1, 2, 4, 7, 8, 10, 11],
             "Mercury": [3, 5, 6, 11], "Jupiter": [6, 10, 11, 12], "Venus": [6, 8, 11, 12],
             "Saturn": [1, 4, 7, 8, 9, 10, 11], "Lagna": [1, 3, 6, 10, 11]},
    "Mercury": {"Sun": [5, 6, 9, 11, 12], "Moon": [2, 4, 6, 8, 10, 11], "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
                "Mercury": [1, 3, 5, 6, 9, 10, 11, 12], "Jupiter": [6, 8, 11, 12],
                "Venus": [1, 2, 3, 4, 5, 8, 9, 11], "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
                "Lagna": [1, 2, 4, 6, 8, 10, 11]},
    "Jupiter": {"Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11], "Moon": [2, 5, 7, 9, 11], "Mars": [1, 2, 4, 7, 8, 10, 11],
                "Mercury": [1, 2, 4, 5, 6, 9, 10, 11], "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
                "Venus": [2, 5, 6, 9, 10, 11], "Saturn": [3, 5, 6, 12], "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11]},
    "Venus": {"Sun": [8, 11, 12], "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12], "Mars": [3, 5, 6, 9, 11, 12],
              "Mercury": [3, 5, 6, 9, 11], "Jupiter": [5, 8, 9, 10, 11], "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
              "Saturn": [3, 4, 5, 8, 9, 10, 11], "Lagna": [1, 2, 3, 4, 5, 8, 9, 11]},
    "Saturn": {"Sun": [1, 2, 4, 7, 8, 10, 11], "Moon": [3, 6, 11], "Mars": [3, 5, 6, 10, 11, 12],
               "Mercury": [6, 8, 9, 10, 11, 12], "Jupiter": [5, 6, 11, 12], "Venus": [6, 11, 12],
               "Saturn": [3, 5, 6, 11], "Lagna": [1, 3, 4, 6, 10, 11]},
}
AREAS = {
    "career": {"label": "Career & work", "houses": [10, 6, 2, 11], "karakas": ["Saturn", "Sun", "Mercury"], "varga": 10},
    "money": {"label": "Money & wealth", "houses": [2, 11, 5, 9], "karakas": ["Jupiter", "Venus"], "varga": 2},
    "marriage": {"label": "Marriage & relationships", "houses": [7, 2, 11], "karakas": ["Venus", "Jupiter"], "varga": 9},
    "education": {"label": "Education & learning", "houses": [4, 5, 9], "karakas": ["Mercury", "Jupiter"], "varga": 24},
    "property": {"label": "Home & property", "houses": [4], "karakas": ["Mars", "Venus"], "varga": 4},
    "children": {"label": "Children", "houses": [5], "karakas": ["Jupiter"], "varga": 7},
    "travel": {"label": "Travel & abroad", "houses": [12, 9, 3], "karakas": ["Rahu"], "varga": None},
    "health": {"label": "Health & wellbeing habits", "houses": [1, 6], "karakas": ["Sun", "Moon"], "varga": None},
    "spiritual": {"label": "Inner growth", "houses": [9, 12], "karakas": ["Ketu", "Jupiter"], "varga": None},
}
AREA_KEYWORDS = {
    "career": ["career", "job", "work", "promotion", "business", "office", "boss", "interview", "startup",
               "naukri", "kaam", "नौकरी", "करियर", "व्यवसाय", "काम", "চাকরি", "কর্মজীবন",
               "কাজ", "ব্যবসা", "পদোন্নতি", "অফিস"],
    "money": ["money", "wealth", "finance", "income", "salary", "saving", "invest", "loan", "debt", "paisa",
              "dhan", "पैसा", "धन", "आय", "वेतन", "টাকা", "অর্থ", "আয়", "বেতন", "সম্পদ", "ঋণ"],
    "marriage": ["marriage", "marry", "wedding", "spouse", "husband", "wife", "partner", "relationship",
                 "love", "girlfriend", "boyfriend", "shaadi", "shadi", "vivah", "biye", "शादी", "विवाह",
                 "प्रेम", "पति", "पत्नी", "रिश्ता", "বিয়ে", "বিবাহ", "স্বামী", "স্ত্রী", "প্রেম", "সম্পর্ক"],
    "education": ["study", "studies", "exam", "education", "college", "degree", "course", "university",
                  "padhai", "पढ़ाई", "परीक्षा", "शिक्षा", "পড়াশোনা", "পরীক্ষা", "শিক্ষা", "কলেজ"],
    "property": ["house", "home", "property", "flat", "land", "vehicle", "ghar", "घर", "मकान", "संपत्ति",
                 "জমি", "বাড়ি", "সম্পত্তি", "ফ্ল্যাট"],
    "children": ["child", "children", "baby", "son", "daughter", "pregnan", "santan", "संतान", "बच्च",
                 "সন্তান", "বাচ্চা"],
    "travel": ["abroad", "foreign", "travel", "visa", "relocat", "settle", "overseas", "videsh", "bidesh",
               "विदेश", "यात्रा", "বিদেশ", "ভ্রমণ", "ভিসা"],
    "health": ["health", "fitness", "energy", "stress", "sleep", "sehat", "स्वास्थ्य", "सेहत",
               "স্বাস্থ্য", "শরীর"],
    "spiritual": ["spiritual", "meditation", "peace", "purpose", "अध्यात्म", "शांति", "ध्यान",
                  "আধ্যাত্মিক", "শান্তি", "ধ্যান"],
}
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

def is_combust(name, lon, sun_lon, retro):
    if name not in COMBUST_ORBS:
        return False
    orb = COMBUST_ORBS[name]
    if retro and name == "Mercury":
        orb = 12
    if retro and name == "Venus":
        orb = 8
    d = abs(lon - sun_lon) % 360
    return min(d, 360 - d) <= orb

def varga_sign(lon, n):
    s, deg = int(lon // 30), lon % 30
    odd = s % 2 == 0
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

def functional_roles(asc_sign):
    roles = {}
    for planet in SEVEN:
        owned = [h for h in range(1, 13) if SIGN_LORDS[(asc_sign + h - 1) % 12] == planet]
        if 1 in owned:
            roles[planet] = "Lagna lord"
            continue
        if any(h in (4, 7, 10) for h in owned) and any(h in (5, 9) for h in owned):
            roles[planet] = "Yogakaraka"
            continue
        score = 0
        for h in owned:
            if h in (5, 9):
                score += 3
            elif h in (3, 6, 8, 11):
                score -= 2
            elif h in (4, 7, 10) and planet in ("Jupiter", "Venus"):
                score -= 1
        roles[planet] = ("Functional benefic" if score > 0 else
                         "Functional malefic" if score < 0 else "Neutral")
    roles["Rahu"] = "Acts through its sign lord"
    roles["Ketu"] = "Acts through its sign lord"
    return roles

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

def ashtakavarga(chart):
    if chart["time_unknown"]:
        return None
    ref_signs = {r: chart["planets"][r]["sign"] for r in SEVEN}
    ref_signs["Lagna"] = chart["asc_sign"]
    bav = {}
    for pl_, refs in BAV_RULES.items():
        row = [0] * 12
        for ref, houses in refs.items():
            for h in houses:
                row[(ref_signs[ref] + h - 1) % 12] += 1
        bav[pl_] = row
    sav = [sum(bav[p][s] for p in bav) for s in range(12)]
    return {"bav": bav, "sav": sav}

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
    sun_lon = planets["Sun"]["lon"]
    for name, p in planets.items():
        p["sign"] = int(p["lon"] // 30)
        p["deg"] = p["lon"] % 30
        p["house"] = (p["sign"] - asc_sign) % 12 + 1
        p["nak"] = int(p["lon"] // NAK_LEN)
        p["pada"] = int((p["lon"] % NAK_LEN) // (NAK_LEN / 4)) + 1
        p["dignity"] = dignity(name, p["sign"])
        p["vargas"] = {n: varga_sign(p["lon"], n) for n in VARGA_NS}
        p["combust"] = is_combust(name, p["lon"], sun_lon, p["retro"])
        p["vargottama"] = (not time_unknown) and p["sign"] == p["vargas"][9]
    chart = {"asc": asc, "asc_sign": asc_sign, "time_unknown": time_unknown,
             "planets": planets, "roles": functional_roles(asc_sign),
             "dashas": vimshottari(planets["Moon"]["lon"], utc)}
    chart["av"] = ashtakavarga(chart)
    return chart

def house_of(chart, sign):
    return (sign - chart["asc_sign"]) % 12 + 1

def lord_of(chart, h):
    return SIGN_LORDS[(chart["asc_sign"] + h - 1) % 12]

def lordships(chart):
    out = {}
    for h in range(1, 13):
        out.setdefault(lord_of(chart, h), []).append(h)
    return out

def neecha_bhanga(chart):
    P, out = chart["planets"], set()
    moon_sign = P["Moon"]["sign"]
    for name, p in P.items():
        if p["dignity"] != "debilitated":
            continue
        deb = p["sign"]
        helpers = [SIGN_LORDS[deb]] + [pl_ for pl_, ex in EXALT.items() if ex == deb]
        for hp in helpers:
            hs = P[hp]["sign"]
            if (hs - chart["asc_sign"]) % 3 == 0 or (hs - moon_sign) % 3 == 0:
                out.add(name)
                break
    return out

def exchanges(chart):
    P, out = chart["planets"], []
    for i, a in enumerate(SEVEN):
        for b in SEVEN[i + 1:]:
            if SIGN_LORDS[P[a]["sign"]] == b and SIGN_LORDS[P[b]["sign"]] == a:
                out.append((a, b))
    return out

def planet_notes(chart, name, nb):
    p, notes = chart["planets"][name], []
    if p["dignity"]:
        notes.append(p["dignity"])
    if name in nb:
        notes.append("debilitation cancelled")
    if p["combust"]:
        notes.append("combust")
    if p["vargottama"]:
        notes.append("vargottama")
    if p["retro"]:
        notes.append("retrograde")
    return notes

def aspects_on(chart):
    asp = {h: [] for h in range(1, 13)}
    for name, p in chart["planets"].items():
        if name in ("Rahu", "Ketu"):
            continue
        for n in [7] + SPECIAL_ASPECTS.get(name, []):
            asp[(p["house"] + n - 2) % 12 + 1].append(name)
    return asp

def house_lines(chart, nb):
    asp = aspects_on(chart)
    lines = []
    for h in range(1, 13):
        sign = (chart["asc_sign"] + h - 1) % 12
        lord = SIGN_LORDS[sign]
        lp = chart["planets"][lord]
        notes = planet_notes(chart, lord, nb)
        nt = f" ({', '.join(notes)})" if notes else ""
        occ = [n for n, p in chart["planets"].items() if p["house"] == h]
        lines.append(f"House {h} [{HOUSE_TOPICS[h]}]: {SIGNS[sign]}; lord {lord} "
                     f"[{chart['roles'][lord]}] in house {lp['house']}{nt}; "
                     f"occupants: {', '.join(occ) or 'none'}; aspected by: {', '.join(asp[h]) or 'none'}")
    return lines

def find_yogas(chart):
    P, ys = chart["planets"], []
    known = not chart["time_unknown"]
    moon_s = P["Moon"]["sign"]
    five = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    if (P["Jupiter"]["sign"] - moon_s) % 3 == 0:
        ys.append("Gaja Kesari (Jupiter in a kendra from the Moon): wisdom, respect, protection")
    if P["Sun"]["sign"] == P["Mercury"]["sign"]:
        ys.append("Budhaditya (Sun with Mercury): sharp intellect, communication")
    if P["Moon"]["sign"] == P["Mars"]["sign"]:
        ys.append("Chandra-Mangala (Moon with Mars): drive to earn, enterprise")
    second = [n for n in five if (P[n]["sign"] - moon_s) % 12 == 1]
    twelfth = [n for n in five if (P[n]["sign"] - moon_s) % 12 == 11]
    if second and twelfth:
        ys.append(f"Durudhara yoga ({', '.join(second + twelfth)} on both sides of the Moon): "
                  f"resources, support and a well-rounded life")
    elif second:
        ys.append(f"Sunapha yoga ({', '.join(second)} in the 2nd from the Moon): self-earned wealth and ability")
    elif twelfth:
        ys.append(f"Anapha yoga ({', '.join(twelfth)} in the 12th from the Moon): good character, ease and comfort")
    else:
        near = [n for n in five if (P[n]["sign"] - moon_s) % 3 == 0]
        if not near:
            ys.append("Kemadruma yoga (no planets around the Moon): independence; building a personal "
                      "support system brings stability")
    adhi = [n for n in ("Mercury", "Jupiter", "Venus") if (P[n]["sign"] - moon_s) % 12 in (5, 6, 7)]
    if len(adhi) >= 2:
        ys.append(f"Adhi yoga ({', '.join(adhi)} in the 6th to 8th from the Moon): leadership, comfort, steady progress")
    amala = [n for n in ("Mercury", "Jupiter", "Venus")
             if (known and P[n]["house"] == 10) or (P[n]["sign"] - moon_s) % 12 == 9]
    if amala:
        ys.append(f"Amala yoga ({', '.join(amala)} in the 10th): good reputation through ethical work")
    for name in sorted(neecha_bhanga(chart)):
        ys.append(f"Neecha Bhanga Raja yoga ({name}'s debilitation is cancelled): an early weakness "
                  f"that turns into real strength through effort")
    for a, b in exchanges(chart):
        ha, hb = P[a]["house"], P[b]["house"]
        hs = {ha, hb}
        if hs & {6, 8, 12}:
            kind, meaning = "Dainya", "early struggles in these areas turn into resilience"
        elif 3 in hs:
            kind, meaning = "Khala", "gains through effort, courage and initiative"
        else:
            kind, meaning = "Maha", "strong mutual support between these life areas"
        ys.append(f"{kind} Parivartana yoga ({a} and {b} exchange signs, houses {ha} and {hb}): {meaning}")
    if known:
        for pl_, yn in {"Mars": "Ruchaka", "Mercury": "Bhadra", "Jupiter": "Hamsa",
                        "Venus": "Malavya", "Saturn": "Sasa"}.items():
            p = P[pl_]
            if p["house"] in (1, 4, 7, 10) and p["dignity"] in ("exalted", "own sign"):
                ys.append(f"{yn} Mahapurusha yoga ({pl_} {p['dignity']} in a kendra)")
        kendra = {lord_of(chart, h) for h in (1, 4, 7, 10)}
        trikona = {lord_of(chart, h) for h in (1, 5, 9)}
        pairs = set()
        for a in kendra:
            for b in trikona:
                if a != b and P[a]["sign"] == P[b]["sign"] and frozenset((a, b)) not in pairs:
                    pairs.add(frozenset((a, b)))
                    ys.append(f"Raja yoga ({a} and {b}, kendra and trikona lords, together): rise and recognition")
        for h, yn in {6: "Harsha", 8: "Sarala", 12: "Vimala"}.items():
            lord = lord_of(chart, h)
            if P[lord]["house"] in (6, 8, 12):
                ys.append(f"{yn} Viparita Raja yoga ({ordinal(h)} lord {lord} in house {P[lord]['house']}): "
                          f"success that comes after, or through, challenges")
        wealth = {lord_of(chart, 2), lord_of(chart, 11)}
        fortune = {lord_of(chart, 1), lord_of(chart, 5), lord_of(chart, 9)}
        dpairs = set()
        for a in wealth:
            for b in fortune:
                if a != b and P[a]["sign"] == P[b]["sign"] and frozenset((a, b)) not in dpairs:
                    dpairs.add(frozenset((a, b)))
                    ys.append(f"Dhana yoga ({a} and {b}, wealth and fortune lords, together): capacity to build wealth")
    return ys

def transits(chart, now):
    jd = julian_day(now)
    moon_sign = chart["planets"]["Moon"]["sign"]
    av = chart.get("av")
    out = []
    for name in ("Saturn", "Jupiter", "Rahu"):
        lon, _ = sidereal_lon(jd, PLANETS[name])
        s = int(lon // 30)
        pts = f"; its Ashtakavarga points there: {av['bav'][name][s]}/8" if av and name in av["bav"] else ""
        out.append(f"{name} now in {SIGNS[s]}: house {house_of(chart, s)} from Lagna, "
                   f"house {(s - moon_sign) % 12 + 1} from Moon{pts}")
    sat_from_moon = (int(sidereal_lon(jd, swe.SATURN)[0] // 30) - moon_sign) % 12 + 1
    phase = {12: "phase 1 (rising)", 1: "phase 2 (peak)", 2: "phase 3 (setting)"}.get(sat_from_moon)
    out.append(f"Sade Sati: {'active, ' + phase if phase else 'not active'}")
    return out

def transit_months(chart, now, months=24):
    key = f"{now:%Y-%m}"
    store = chart.setdefault("_tr", {})
    if key not in store:
        out = []
        for i in range(months):
            mm = (now.month - 1 + i) % 12 + 1
            yy = now.year + (now.month - 1 + i) // 12
            d = datetime(yy, mm, 15)
            jd = julian_day(d)
            js = int(sidereal_lon(jd, swe.JUPITER)[0] // 30)
            ss = int(sidereal_lon(jd, swe.SATURN)[0] // 30)
            out.append((d, js, ss))
        store[key] = out
    return store[key]

def influences(planet, from_sign, target_sign):
    d = (target_sign - from_sign) % 12 + 1
    return d in {"Jupiter": (1, 5, 7, 9), "Saturn": (1, 3, 7, 10)}[planet]

def double_transit_windows(chart, now, house):
    target = (chart["asc_sign"] + house - 1) % 12
    windows, cur_w = [], None
    for d, js, ss in transit_months(chart, now):
        on = influences("Jupiter", js, target) and influences("Saturn", ss, target)
        if on and cur_w is None:
            cur_w = [d, d]
        elif on:
            cur_w[1] = d
        elif cur_w:
            windows.append(tuple(cur_w))
            cur_w = None
    if cur_w:
        windows.append(tuple(cur_w))
    return windows

def fmt_windows(windows):
    return "; ".join(f"{a:%b %Y}" if a == b else f"{a:%b %Y} to {b:%b %Y}" for a, b in windows)

def house_strength(chart, h, nb, av, asp):
    P, roles, factors = chart["planets"], chart["roles"], []
    sign = (chart["asc_sign"] + h - 1) % 12
    lord = SIGN_LORDS[sign]
    lp = P[lord]
    if lp["house"] in (1, 4, 5, 7, 9, 10):
        factors.append((1, f"{ordinal(h)} lord {lord} sits in a strong house (the {ordinal(lp['house'])})"))
    elif lp["house"] in (6, 8, 12):
        if h in (6, 8, 12):
            factors.append((1, f"{ordinal(h)} lord {lord} in the {ordinal(lp['house'])} house "
                               f"(Viparita: difficulties cancel out)"))
        else:
            factors.append((-1, f"{ordinal(h)} lord {lord} sits in the {ordinal(lp['house'])} house, "
                                f"a house of effort"))
    d = lp["dignity"]
    if d == "exalted":
        factors.append((2, f"{ordinal(h)} lord {lord} is exalted"))
    elif d == "own sign":
        factors.append((1, f"{ordinal(h)} lord {lord} is in its own sign"))
    elif d == "debilitated":
        if lord in nb:
            factors.append((1, f"{ordinal(h)} lord {lord}'s debilitation is cancelled: strength through effort"))
        else:
            factors.append((-2, f"{ordinal(h)} lord {lord} is debilitated: needs patient, deliberate effort"))
    if lp["combust"]:
        factors.append((-1, f"{ordinal(h)} lord {lord} is combust (close to the Sun)"))
    if lp["vargottama"]:
        factors.append((1, f"{ordinal(h)} lord {lord} is vargottama (consistent strength)"))
    if roles.get(lord) == "Yogakaraka":
        factors.append((1, f"{ordinal(h)} lord {lord} is the Yogakaraka for this Lagna"))
    occ = [n for n, p in P.items() if p["house"] == h]
    for n in sorted(set(occ + asp[h])):
        how = "in" if n in occ else "aspecting"
        if n in NATURAL_BENEFICS or roles.get(n) in ("Yogakaraka", "Lagna lord"):
            factors.append((1, f"{n} {how} the {ordinal(h)} house brings support"))
        elif n in ("Saturn", "Mars", "Rahu", "Ketu", "Sun"):
            factors.append((-1, f"{n} {how} the {ordinal(h)} house asks for discipline"))
    if av:
        s = av["sav"][sign]
        if s >= 28:
            factors.append((1, f"Ashtakavarga gives the {ordinal(h)} house {s} points (strong, 28+)"))
        elif s <= 24:
            factors.append((-1, f"Ashtakavarga gives the {ordinal(h)} house {s} points (below 25: build steadily)"))
    return factors

def area_analysis(chart, key, now):
    A, P = AREAS[key], chart["planets"]
    nb, av, asp = neecha_bhanga(chart), chart.get("av"), aspects_on(chart)
    factors = []
    for i, h in enumerate(A["houses"]):
        w = 1 if i == 0 else 0.5
        factors += [(v * w, t_) for v, t_ in house_strength(chart, h, nb, av, asp)]
    for k in A["karakas"]:
        p = P[k]
        if p["dignity"] in ("exalted", "own sign"):
            factors.append((1, f"{k}, the natural significator, is {p['dignity']}"))
        elif p["dignity"] == "debilitated" and k not in nb:
            factors.append((-1, f"{k}, the natural significator, is debilitated"))
        if p.get("combust"):
            factors.append((-0.5, f"{k}, the natural significator, is combust"))
    if A["varga"] and not chart["time_unknown"]:
        n = A["varga"]
        h1 = A["houses"][0]
        lord1 = lord_of(chart, h1)
        vh = (P[lord1]["vargas"][n] - varga_sign(chart["asc"], n)) % 12 + 1
        if vh in (1, 4, 5, 7, 9, 10):
            factors.append((0.5, f"In the D{n} chart, the {ordinal(h1)} lord {lord1} is well placed (house {vh})"))
        elif vh in (6, 8, 12):
            factors.append((-0.5, f"In the D{n} chart, the {ordinal(h1)} lord {lord1} is in house {vh}, asking for effort"))
    net = sum(v for v, _ in factors)
    if net >= 4:
        verdict = "Strongly supported"
    elif net >= 1.5:
        verdict = "Supported"
    elif net > -1.5:
        verdict = "Balanced"
    elif net > -4:
        verdict = "Needs steady effort"
    else:
        verdict = "Asks for patience and long-term effort"
    supportive = [t_ for v, t_ in sorted(factors, key=lambda f: -f[0]) if v > 0][:4]
    challenging = [t_ for v, t_ in sorted(factors, key=lambda f: f[0]) if v < 0][:3]
    houses_set = set(A["houses"])

    def link(pl_):
        why = []
        if pl_ not in ("Rahu", "Ketu"):
            owned = [h for h in A["houses"] if lord_of(chart, h) == pl_]
            if owned:
                why.append(f"rules house {', '.join(map(str, owned))}")
        if P[pl_]["house"] in houses_set:
            why.append(f"sits in house {P[pl_]['house']}")
        asp_h = [h for h in A["houses"] if pl_ in asp[h]]
        if asp_h:
            why.append(f"aspects house {', '.join(map(str, asp_h))}")
        if pl_ in A["karakas"]:
            why.append("is a natural significator")
        return why

    periods = []
    for ad in upcoming_subperiods(chart, now, 8):
        why = link(ad["lord"])
        current = ad["start"] <= now < ad["end"]
        if why or current:
            periods.append(f"{ad['md']}-{ad['lord']} ({ad['start']:%b %Y} to {ad['end']:%b %Y})"
                           f"{' [CURRENT]' if current else ''}: {ad['lord']} [{chart['roles'][ad['lord']]}] "
                           + ("; ".join(why) if why else "is not directly linked to this area"))
    windows = double_transit_windows(chart, now, A["houses"][0])
    return {"key": key, "label": A["label"], "house": A["houses"][0], "net": net, "verdict": verdict,
            "supportive": supportive, "challenging": challenging, "periods": periods, "windows": windows}

def area_block(an):
    lines = [f"AREA: {an['label']} | Outlook: {an['verdict']} (engine score {an['net']:+.1f})",
             "Supportive factors: " + ("; ".join(an["supportive"]) or "none notable"),
             "Factors needing effort: " + ("; ".join(an["challenging"]) or "none notable"),
             "Relevant dasha periods: " + (" | ".join(an["periods"]) or "none in the next few periods"),
             f"Double transit (Jupiter + Saturn) on house {an['house']}: "
             + (fmt_windows(an["windows"]) or "none in the next 24 months")]
    return "\n".join(lines)

def detect_areas(q):
    ql = q.lower()
    return [k for k, words in AREA_KEYWORDS.items() if any(w in ql for w in words)]

def areas_summary(chart, now):
    out = []
    for key in AREAS:
        an = area_analysis(chart, key, now)
        top = an["supportive"][0] if an["supportive"] else "no single standout factor"
        out.append(f"{an['label']}: {an['verdict']}; top strength: {top}")
    return "\n".join(out)

def daily_indicators(chart, ref_time):
    moon_now, _ = sidereal_lon(julian_day(ref_time), swe.MOON)
    nak_now = int(moon_now // NAK_LEN)
    tara = TARAS[(nak_now - chart["planets"]["Moon"]["nak"]) % 9]
    msign = int(moon_now // 30)
    chandra = (msign - chart["planets"]["Moon"]["sign"]) % 12 + 1
    good_t, good_c = tara in GOOD_TARAS, chandra in (1, 3, 6, 7, 10, 11)
    house = house_of(chart, msign)
    av = chart.get("av")
    if av:
        bindus = av["bav"]["Moon"][msign]
        third = round(bindus * 15 / 8)
    else:
        bindus = None
        third = 15 if house in (1, 2, 3, 5, 9, 10, 11) else 0
    score = 45 + (20 if good_t else 10 if tara == "Janma" else 0) + (20 if good_c else 0) + third
    label = next(b[2] for b in SCORE_BANDS if b[0] <= score <= b[1])
    return {"tara": tara, "good_tara": good_t, "chandra": chandra, "good_chandra": good_c,
            "house": house, "nak_idx": nak_now, "moon_sign": SIGNS[msign],
            "bindus": bindus, "score": score, "label": label}

def chart_text(chart, now):
    P = chart["planets"]
    nb = neecha_bhanga(chart)
    lines = []
    if chart["time_unknown"]:
        lines.append("NOTE: Birth time unknown. Houses are counted from the Moon sign (Chandra Lagna). "
                     "Avoid Lagna, divisional-chart and exact-timing claims; dasha dates may be off by months.")
        lines.append(f"Chandra Lagna: {SIGNS[chart['asc_sign']]}")
    else:
        vl = "; ".join(f"D{n} {SHORT[varga_sign(chart['asc'], n)]}" for n in VARGA_NS)
        lines.append(f"Lagna: {SIGNS[chart['asc_sign']]} {chart['asc'] % 30:.1f}°. Divisional Lagnas: {vl}")
    roles = chart["roles"]
    groups = {}
    for pl_ in SEVEN:
        groups.setdefault(roles[pl_], []).append(pl_)
    lines.append("\nFUNCTIONAL NATURE FOR THIS LAGNA: " +
                 "; ".join(f"{k}: {', '.join(v)}" for k, v in groups.items()))
    rules = lordships(chart)
    lines.append("\nPLANETS:")
    for name, p in P.items():
        notes = planet_notes(chart, name, nb)
        ext = f" ({', '.join(notes)})" if notes else ""
        ruled = f", rules houses {', '.join(map(str, rules[name]))}" if name in rules else ""
        vg = ""
        if not chart["time_unknown"]:
            vg = "; " + ", ".join(f"D{n} {SHORT[p['vargas'][n]]}" for n in VARGA_NS)
        lines.append(f"{name} [{roles[name]}]: {SIGNS[p['sign']]} {p['deg']:.1f}°, house {p['house']}"
                     f"{ext}{ruled}; {NAKSHATRAS[p['nak']]} pada {p['pada']}{vg}")
    lines.append("\nHOUSES:")
    lines += house_lines(chart, nb)
    av = chart.get("av")
    if av:
        lines.append("\nASHTAKAVARGA (SAV points by house; 28+ strong, below 25 needs effort): " +
                     ", ".join(f"H{h} {av['sav'][(chart['asc_sign'] + h - 1) % 12]}" for h in range(1, 13)))
    ys = find_yogas(chart)
    lines.append("\nYOGAS: " + ("; ".join(ys) if ys else "none of the common ones"))
    lines.append("\nMAHADASHAS:")
    for d in chart["dashas"]:
        tag = " (CURRENT)" if d["start"] <= now < d["end"] else ""
        lines.append(f"{d['lord']} [{roles[d['lord']]}]: {d['start']:%b %Y} to {d['end']:%b %Y}{tag}")
    subs = upcoming_subperiods(chart, now)
    lines.append("\nANTARDASHAS (current and upcoming):")
    for ad in subs:
        tag = " (CURRENT)" if ad["start"] <= now < ad["end"] else ""
        lines.append(f"{ad['md']}-{ad['lord']} [{roles[ad['lord']]}]: "
                     f"{ad['start']:%b %Y} to {ad['end']:%b %Y}{tag}")
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
        houses[(s - asc_v) % 12 + 1].append(pick(ABBR_T[name]))
    if not chart["time_unknown"]:
        houses[1].insert(0, pick(ASC_T))
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
    key = (f"v{CHART_VERSION}|{profile['id']}|{profile['birth_date']}|{profile['birth_time']}|"
           f"{profile['time_unknown']}|{profile['lat']}|{profile['lon']}")
    cache = st.session_state.setdefault("chart_cache", {})
    if key not in cache:
        cache[key] = chart_from_profile(profile)
    return cache[key]

# ---------------- MATCHMAKING (ASHTAKOOT) ----------------
VARNA = [3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1, 4]
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
NADI = [0, 1, 2, 2, 1, 0]
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
    tt = tara_ok(gn, bn) + tara_ok(bn, gn)
    rows.append(("Tara", {2: 3, 1: 1.5, 0: 0}[tt], 3, "Wellbeing and fortune together"))
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

def manglik_text(from_lagna, from_moon):
    lt = "unknown (no birth time)" if from_lagna is None else ("yes" if from_lagna else "no")
    return f"from Lagna: {lt}; from Moon: {'yes' if from_moon else 'no'}"

def manglik_text_ui(from_lagna, from_moon):
    lt = t("unknown_nt") if from_lagna is None else (t("yes") if from_lagna else t("no"))
    return f"{t('from_lagna')}: {lt}; {t('from_moon')}: {t('yes') if from_moon else t('no')}"

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
CRISIS_WORDS = ["suicide", "kill myself", "end my life", "want to die", "self harm", "self-harm",
                "hurt myself", "no reason to live",
                "आत्महत्या", "मरना चाहता", "मरना चाहती", "मर जाना चाहता", "मर जाना चाहती",
                "जीना नहीं चाहता", "जीना नहीं चाहती", "खुद को खत्म", "खुद को नुकसान",
                "marna chahta", "marna chahti", "jeena nahi chahta", "jeena nahi chahti", "khud ko khatam",
                "আত্মহত্যা", "মরে যেতে চাই", "বাঁচতে চাই না", "নিজেকে শেষ করে", "নিজের ক্ষতি",
                "more jete chai", "bachte chai na"]

def system_prompt(lang, chart_name, rel):
    who = ("The user is asking about their own chart." if rel == "Self" else
           f"This chart belongs to {chart_name}, the user's {rel.lower()}. "
           f"Speak about {chart_name} in the third person.")
    return f"""You are Dishara (written दिशारा in Hindi and দিশারা in Bengali), a warm, expert Vedic
astrologer in the Parashari tradition. {who} Give specific, well-reasoned guidance that leaves people
clear, capable and hopeful.

HOW TO ANALYSE (every time, silently):
0. If an AREA ANALYSIS is provided, it is the calculated judgement of Dishara's engine. Base your
   conclusion on its outlook, explain its top supportive and effort factors in plain words, and use
   its dasha periods and double-transit windows for timing. Do not contradict it; you may add nuance
   from the chart. A double transit (Jupiter and Saturn both influencing a house) is a classical
   timing indicator for that area. Ashtakavarga: 28+ points strong, below 25 needs steady effort.
1. Identify the life area and its houses: career 10, 6, 2, 11 + D10; money 2, 11, 5, 9 + D2;
   marriage/relationships 7, 2, 11, Venus + D9; education 4, 5, 9, Mercury, Jupiter + D24;
   home/property 4 + D4; children 5, Jupiter + D7; siblings/courage 3 + D3; parents 4, 9 + D12;
   travel/abroad 3, 9, 12; health 1, 6 (wellbeing habits only); spiritual growth 9, 12, Ketu.
2. For each relevant house: its sign; its lord, where that lord sits, its dignity and its
   functional nature for this Lagna; whether the lord is combust, vargottama or has cancelled
   debilitation; planets in the house; aspects on it; and the natural significator.
3. Check yogas and sign exchanges that involve these houses or planets.
4. Timing: periods of the Yogakaraka, Lagna lord and functional benefics are more supportive;
   periods of functional malefics bring results through effort and patience. Name periods with months.
5. Weigh supportive and challenging factors and reach a clear conclusion.

HOW TO ANSWER (default):
- Bold headings: **What the chart shows** (2-4 bullets, each citing a specific factor),
  **Timing** (specific periods), **What you can do** (2-3 practical actions). Translate the
  headings into the reply language.
- Be specific to THIS chart. No generic Lagna or sun-sign personality text unless asked.
- Explain any Sanskrit term in a few words. Under 250 words.
- If the request says DAILY TIPS or COMPATIBILITY, follow the format given in the request instead.

RULES:
1. Use ONLY the data provided. Never invent positions, yogas, roles, scores or dates.
2. Lead with strengths; frame challenges as growth areas with practical steps.
3. No fear: no curses, doshas as threats, gemstones or paid remedies. Never call a planet
   or period "bad"; describe what it asks of the person.
4. Never predict death, illness, accidents, divorce, lottery or stock results.
5. If asked about death or lifespan, kindly say you don't predict that and turn to strengths.
   Only if the person sounds distressed or hopeless, keep astrology to a line or two, put
   support first, and suggest Tele-MANAS at 14416 (free, 24/7). Don't call it confidential.
6. If the chart notes the birth time is unknown, say once that you're reading the Moon chart,
   and avoid Lagna-based, divisional-chart or exact-timing claims.
7. Reply in {lang}, using natural everyday {lang} with common astrology terms in that language.
   Write your own name correctly in that language's script."""

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

def ask_dishara(prompt, chart_name, rel, fast=False):
    client = get_client()
    lang = ANSWER_LANG[L()]
    models = get_models()
    if fast:
        models = sorted(models, key=lambda m: 0 if m == "gemini-flash-lite-latest" else 1)[:3]
    else:
        models = models[:6]
    for model in models:
        for attempt in range(1 if fast else 2):
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt(lang, chart_name, rel), temperature=0.4))
                return r.text
            except errors.ServerError:
                if not fast:
                    time.sleep(2 * (attempt + 1))
            except errors.ClientError:
                break
    return None

def ai_json(prompt):
    client = get_client()
    models = sorted(get_models(), key=lambda m: {"gemini-flash-latest": 0,
                                                 "gemini-flash-lite-latest": 1}.get(m, 2))[:3]
    for model in models:
        try:
            r = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8, response_mime_type="application/json"))
            data = json.loads(r.text)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None

# ---------------- PANCHANG ----------------
TITHI_T = [("Pratipada", "प्रतिपदा", "প্রতিপদ"), ("Dwitiya", "द्वितीया", "দ্বিতীয়া"), ("Tritiya", "तृतीया", "তৃতীয়া"),
           ("Chaturthi", "चतुर्थी", "চতুর্থী"), ("Panchami", "पंचमी", "পঞ্চমী"), ("Shashthi", "षष्ठी", "ষষ্ঠী"),
           ("Saptami", "सप्तमी", "সপ্তমী"), ("Ashtami", "अष्टमी", "অষ্টমী"), ("Navami", "नवमी", "নবমী"),
           ("Dashami", "दशमी", "দশমী"), ("Ekadashi", "एकादशी", "একাদশী"), ("Dwadashi", "द्वादशी", "দ্বাদশী"),
           ("Trayodashi", "त्रयोदशी", "ত্রয়োদশী"), ("Chaturdashi", "चतुर्दशी", "চতুর্দশী"),
           ("Purnima", "पूर्णिमा", "পূর্ণিমা"), ("Amavasya", "अमावस्या", "অমাবস্যা")]
PAKSHA_T = [("Shukla", "शुक्ल", "শুক্ল"), ("Krishna", "कृष्ण", "কৃষ্ণ")]
VARA_T = [("Somavara (Monday)", "सोमवार", "সোমবার"), ("Mangalavara (Tuesday)", "मंगलवार", "মঙ্গলবার"),
          ("Budhavara (Wednesday)", "बुधवार", "বুধবার"), ("Guruvara (Thursday)", "गुरुवार", "বৃহস্পতিবার"),
          ("Shukravara (Friday)", "शुक्रवार", "শুক্রবার"), ("Shanivara (Saturday)", "शनिवार", "শনিবার"),
          ("Ravivara (Sunday)", "रविवार", "রবিবার")]
YOGA_T = [("Vishkambha", "विष्कुंभ", "বিষ্কম্ভ"), ("Priti", "प्रीति", "প্রীতি"), ("Ayushman", "आयुष्मान", "আয়ুষ্মান"),
          ("Saubhagya", "सौभाग्य", "সৌভাগ্য"), ("Shobhana", "शोभन", "শোভন"), ("Atiganda", "अतिगंड", "অতিগণ্ড"),
          ("Sukarma", "सुकर्मा", "সুকর্মা"), ("Dhriti", "धृति", "ধৃতি"), ("Shula", "शूल", "শূল"),
          ("Ganda", "गंड", "গণ্ড"), ("Vriddhi", "वृद्धि", "বৃদ্ধি"), ("Dhruva", "ध्रुव", "ধ্রুব"),
          ("Vyaghata", "व्याघात", "ব্যাঘাত"), ("Harshana", "हर्षण", "হর্ষণ"), ("Vajra", "वज्र", "বজ্র"),
          ("Siddhi", "सिद्धि", "সিদ্ধি"), ("Vyatipata", "व्यतीपात", "ব্যতীপাত"), ("Variyan", "वरीयान", "বরীয়ান"),
          ("Parigha", "परिघ", "পরিঘ"), ("Shiva", "शिव", "শিব"), ("Siddha", "सिद्ध", "সিদ্ধ"),
          ("Sadhya", "साध्य", "সাধ্য"), ("Shubha", "शुभ", "শুভ"), ("Shukla", "शुक्ल", "শুক্ল"),
          ("Brahma", "ब्रह्म", "ব্রহ্ম"), ("Indra", "इंद्र", "ইন্দ্র"), ("Vaidhriti", "वैधृति", "বৈধৃতি")]
KARANA_T = [("Bava", "बव", "বব"), ("Balava", "बालव", "বালব"), ("Kaulava", "कौलव", "কৌলব"),
            ("Taitila", "तैतिल", "তৈতিল"), ("Gara", "गर", "গর"), ("Vanija", "वणिज", "বণিজ"),
            ("Vishti (Bhadra)", "विष्टि (भद्रा)", "বিষ্টি (ভদ্রা)"), ("Shakuni", "शकुनि", "শকুনি"),
            ("Chatushpada", "चतुष्पद", "চতুষ্পদ"), ("Naga", "नाग", "নাগ"), ("Kimstughna", "किंस्तुघ्न", "কিংস্তুঘ্ন")]
RAHU_PART = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}
YAMA_PART = {0: 4, 1: 3, 2: 2, 3: 1, 4: 7, 5: 6, 6: 5}
GULIKA_PART = {0: 6, 1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 7}

def jd_to_ist(jd):
    y, m, d, h = swe.revjul(jd)
    return datetime(y, m, d) + timedelta(hours=h) + timedelta(hours=IST)

@st.cache_data(ttl=3600, show_spinner=False)
def panchang(day_iso, lat, lon):
    day = date.fromisoformat(day_iso)
    start = datetime.combine(day, datetime.min.time()) - timedelta(hours=IST)
    jd0 = julian_day(start)
    geopos = (lon, lat, 0.0)
    _, rise = swe.rise_trans(jd0, swe.SUN, swe.CALC_RISE, geopos, 0.0, 0.0, swe.FLG_MOSEPH)
    _, sett = swe.rise_trans(jd0, swe.SUN, swe.CALC_SET, geopos, 0.0, 0.0, swe.FLG_MOSEPH)
    rise_jd, set_jd = rise[0], sett[0]
    sun, _ = sidereal_lon(rise_jd, swe.SUN)
    moon, _ = sidereal_lon(rise_jd, swe.MOON)
    diff = (moon - sun) % 360
    tithi = int(diff // 12)
    tithi_name = 14 if tithi == 14 else 15 if tithi == 29 else tithi % 15
    k = int(diff // 6)
    karana = 10 if k == 0 else 7 if k == 57 else 8 if k == 58 else 9 if k == 59 else (k - 1) % 7
    sunrise, sunset = jd_to_ist(rise_jd), jd_to_ist(set_jd)
    daylen = sunset - sunrise
    seg = daylen / 8
    wd = day.weekday()

    def part(n):
        s = sunrise + seg * (n - 1)
        return (s, s + seg)

    mid, mu = sunrise + daylen / 2, daylen / 15
    return {"sunrise": sunrise, "sunset": sunset, "wd": wd,
            "paksha": 0 if tithi < 15 else 1, "tithi_name": tithi_name,
            "nak": int(moon // NAK_LEN), "yoga": int(((sun + moon) % 360) // NAK_LEN), "karana": karana,
            "rahu": part(RAHU_PART[wd]), "yama": part(YAMA_PART[wd]), "gulika": part(GULIKA_PART[wd]),
            "abhijit": (mid - mu / 2, mid + mu / 2)}

def fmt_time(d):
    return d.strftime("%I:%M %p").lstrip("0")

def panchang_section(profile, now):
    st.markdown(f"#### {t('pan_title')}")
    default = (profile["place"], profile["lat"], profile["lon"])
    with st.expander(t("pan_change")):
        q = st.text_input(t("city_label"), key="pan_q", placeholder=t("place_ph"))
        if len(q.strip()) >= 3:
            opts = search_places(q.strip())
            if opts:
                labels = [o[0] for o in opts]
                pk = st.selectbox(t("select_place"), labels, index=None,
                                  placeholder=t("choose_place"), key="pan_pick")
                if pk:
                    st.session_state.pan_place = opts[labels.index(pk)]
            else:
                st.warning(t("no_match"))
    place = st.session_state.get("pan_place", default)
    now_ist = now + timedelta(hours=IST)
    try:
        p = panchang(now_ist.date().isoformat(), float(place[1]), float(place[2]))
    except Exception:
        st.caption(t("pan_error"))
        return
    rows = [(t("pan_sunrise"), fmt_time(p["sunrise"])), (t("pan_sunset"), fmt_time(p["sunset"])),
            (t("pan_vara"), pick(VARA_T[p["wd"]])),
            (t("pan_tithi"), f"{pick(PAKSHA_T[p['paksha']])} {pick(TITHI_T[p['tithi_name']])}"),
            (t("col_nak"), nak_name(p["nak"])), (t("pan_yoga"), pick(YOGA_T[p["yoga"]])),
            (t("pan_karana"), pick(KARANA_T[p["karana"]]))]
    row_html = "".join(f"<tr><td style='padding:3px 16px 3px 0;color:#AFA9EC;border:none'>{k}</td>"
                       f"<td style='padding:3px 0;border:none'>{v}</td></tr>" for k, v in rows)
    place_short = html.escape(str(place[0]).split(",")[0])
    st.markdown(f"<div class='card'><p class='muted'>{t('pan_for', place=place_short)} · "
                f"{now_ist:%d %b %Y}</p><table style='border:none;margin-top:6px'>{row_html}</table></div>",
                unsafe_allow_html=True)

    def span(a):
        return f"{fmt_time(a[0])} – {fmt_time(a[1])}"

    rahu_now = p["rahu"][0] <= now_ist < p["rahu"][1]
    alert = (f"<p style='color:#FAC775;font-weight:500;margin:6px 0 0'>{t('pan_rahu_now', end=fmt_time(p['rahu'][1]))}</p>"
             if rahu_now else "")
    wed = (" " + t("pan_abhijit_wed")) if p["wd"] == 2 else ""
    st.markdown(f"""<div class="card"><p class="muted">{t('pan_times')}</p>
      <p class="big">{t('pan_rahu')}: {span(p['rahu'])}</p>
      <p class="muted">{t('pan_rahu_note')}</p>{alert}
      <p style="margin:10px 0 0">{t('pan_yama')}: {span(p['yama'])}</p>
      <p style="margin:4px 0 0">{t('pan_gulika')}: {span(p['gulika'])}</p>
      <p class="gold" style="margin:10px 0 0;font-weight:500">{t('pan_abhijit')}: {span(p['abhijit'])}{wed}</p>
      <p class="muted">{t('pan_abhijit_note')}</p></div>""", unsafe_allow_html=True)
    st.caption(t("pan_note"))

# ---------------- SHAREABLE CARDS: CONTENT ----------------
CARD_T = {
    "wordmark": ("Dishara", "दिशारा", "দিশারা"),
    "my_moon": ("My Moon sign", "मेरी चंद्र राशि", "আমার চন্দ্র রাশি"),
    "my_nak": ("My nakshatra", "मेरा नक्षत्र", "আমার নক্ষত্র"),
    "ruled": ("Ruled by {p}", "स्वामी: {p}", "অধিপতি: {p}"),
    "today_for": ("Today for {s} Moon", "{s} राशि के लिए आज", "{s} রাশির জন্য আজ"),
    "guide": ("Today's Rashi guide", "आज का राशि मार्गदर्शन", "আজকের রাশি নির্দেশিকা"),
    "thought": ("Thought for today", "आज का विचार", "আজকের ভাবনা"),
    "moon_in": ("Moon in {n}", "चंद्रमा {n} में", "চন্দ্র {n} নক্ষত্রে"),
    "from": ("From {n}", "{n} की ओर से", "{n}-এর পক্ষ থেকে"),
    "with_love": ("With love, {n}", "स्नेह सहित, {n}", "ভালোবাসা সহ, {n}"),
    "cta_rashi": ("find your Rashi", "अपनी राशि जानें", "আপনার রাশি জানুন"),
    "cta_nak": ("find your nakshatra", "अपना नक्षत्र जानें", "আপনার নক্ষত্র জানুন"),
    "cta_day": ("your daily guide", "आपका दैनिक मार्गदर्शक", "আপনার দৈনিক পথপ্রদর্শক"),
    "nak_fallback": ("Today, let your {t} nature lead the way.", "आज अपने {t} स्वभाव को राह दिखाने दें।",
                     "আজ আপনার {t} স্বভাবকে পথ দেখাতে দিন।"),
}
EN_WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
EN_MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
MON_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
MON_BN = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর",
          "নভেম্বর", "ডিসেম্বর"]
RASHI_TRAITS = [
    ("Bold · Energetic · Pioneering", "साहसी · ऊर्जावान · अग्रणी", "সাহসী · উদ্যমী · অগ্রণী"),
    ("Steady · Loyal · Graceful", "स्थिर · वफ़ादार · सौम्य", "স্থির · বিশ্বস্ত · মার্জিত"),
    ("Curious · Witty · Versatile", "जिज्ञासु · हाज़िरजवाब · बहुमुखी", "কৌতূহলী · রসিক · বহুমুখী"),
    ("Caring · Intuitive · Protective", "स्नेही · सहज ज्ञानी · रक्षक", "যত্নশীল · অন্তর্দৃষ্টিসম্পন্ন · রক্ষাকর্তা"),
    ("Generous · Confident · Warm", "उदार · आत्मविश्वासी · गर्मजोश", "উদার · আত্মবিশ্বাসী · উষ্ণ"),
    ("Thoughtful · Precise · Helpful", "विचारशील · सटीक · मददगार", "চিন্তাশীল · নিখুঁত · সহায়ক"),
    ("Balanced · Charming · Fair", "संतुलित · आकर्षक · न्यायप्रिय", "ভারসাম্যপূর্ণ · মনোমুগ্ধকর · ন্যায়পরায়ণ"),
    ("Deep · Determined · Loyal", "गहरे · दृढ़ · वफ़ादार", "গভীর · দৃঢ়প্রতিজ্ঞ · বিশ্বস্ত"),
    ("Optimistic · Wise · Adventurous", "आशावादी · ज्ञानी · साहसिक", "আশাবাদী · জ্ঞানী · অভিযাত্রী"),
    ("Disciplined · Patient · Reliable", "अनुशासित · धैर्यवान · भरोसेमंद", "শৃঙ্খলাপরায়ণ · ধৈর্যশীল · নির্ভরযোগ্য"),
    ("Original · Kind · Visionary", "मौलिक · दयालु · दूरदर्शी", "মৌলিক · দয়ালু · দূরদর্শী"),
    ("Compassionate · Creative · Dreamy", "करुणामय · रचनात्मक · स्वप्नशील", "সহানুভূতিশীল · সৃজনশীল · স্বপ্নময়"),
]
NAK_TRAITS = [
    ("Swift · Healing · Bold", "तेज़ · उपचारक · साहसी", "দ্রুত · নিরাময়কারী · সাহসী"),
    ("Creative · Strong · Responsible", "रचनात्मक · दृढ़ · ज़िम्मेदार", "সৃজনশীল · দৃঢ় · দায়িত্বশীল"),
    ("Sharp · Honest · Determined", "तीक्ष्ण · ईमानदार · दृढ़", "তীক্ষ্ণ · সৎ · দৃঢ়প্রতিজ্ঞ"),
    ("Creative · Charming · Steady", "रचनात्मक · आकर्षक · स्थिर", "সৃজনশীল · মনোমুগ্ধকর · স্থির"),
    ("Curious · Gentle · Seeking", "जिज्ञासु · कोमल · खोजी", "কৌতূহলী · কোমল · অনুসন্ধানী"),
    ("Intense · Insightful · Renewing", "गहन · अंतर्दृष्टिपूर्ण · नवीनकारी", "তীব্র · অন্তর্দৃষ্টিসম্পন্ন · নবায়নকারী"),
    ("Hopeful · Kind · Resilient", "आशावान · दयालु · लचीले", "আশাবাদী · দয়ালু · অদম্য"),
    ("Nurturing · Wise · Generous", "पोषक · ज्ञानी · उदार", "লালনকারী · জ্ঞানী · উদার"),
    ("Perceptive · Magnetic · Clever", "पारखी · आकर्षक · चतुर", "বিচক্ষণ · আকর্ষণীয় · চতুর"),
    ("Dignified · Proud · Rooted", "गरिमामय · स्वाभिमानी · परंपरा से जुड़े", "মর্যাদাপূর্ণ · আত্মসম্মানী · শিকড়ে বাঁধা"),
    ("Joyful · Creative · Loving", "आनंदमय · रचनात्मक · स्नेही", "আনন্দময় · সৃজনশীল · স্নেহময়"),
    ("Generous · Loyal · Helpful", "उदार · वफ़ादार · मददगार", "উদার · বিশ্বস্ত · সহায়ক"),
    ("Skilful · Witty · Hardworking", "कुशल · हाज़िरजवाब · मेहनती", "দক্ষ · রসিক · পরিশ্রমী"),
    ("Artistic · Brilliant · Stylish", "कलात्मक · प्रतिभाशाली · आकर्षक", "শৈল্পিক · মেধাবী · রুচিশীল"),
    ("Independent · Flexible · Fair", "स्वतंत्र · लचीले · न्यायप्रिय", "স্বাধীন · নমনীয় · ন্যায়পরায়ণ"),
    ("Focused · Ambitious · Passionate", "केंद्रित · महत्वाकांक्षी · उत्साही", "একাগ্র · উচ্চাকাঙ্ক্ষী · উদ্যমী"),
    ("Devoted · Friendly · Balanced", "समर्पित · मिलनसार · संतुलित", "নিবেদিত · বন্ধুত্বপূর্ণ · ভারসাম্যপূর্ণ"),
    ("Protective · Capable · Brave", "रक्षक · सक्षम · बहादुर", "রক্ষাকর্তা · দক্ষ · সাহসী"),
    ("Truth-seeking · Deep · Fearless", "सत्य-खोजी · गहरे · निडर", "সত্যসন্ধানী · গভীর · নির্ভীক"),
    ("Inspiring · Confident · Persuasive", "प्रेरक · आत्मविश्वासी · प्रभावशाली", "অনুপ্রেরণাদায়ী · আত্মবিশ্বাসী · প্রভাবশালী"),
    ("Principled · Steady · Victorious", "सिद्धांतवादी · स्थिर · विजयी", "নীতিবান · স্থির · বিজয়ী"),
    ("Attentive · Wise · Connected", "सजग · ज्ञानी · जुड़े हुए", "মনোযোগী · জ্ঞানী · সংযুক্ত"),
    ("Rhythmic · Generous · Ambitious", "लयबद्ध · उदार · महत्वाकांक्षी", "ছন্দময় · উদার · উচ্চাকাঙ্ক্ষী"),
    ("Healing · Independent · Visionary", "उपचारक · स्वतंत्र · दूरदर्शी", "নিরাময়কারী · স্বাধীন · দূরদর্শী"),
    ("Idealistic · Intense · Spiritual", "आदर्शवादी · गहन · आध्यात्मिक", "আদর্শবাদী · তীব্র · আধ্যাত্মিক"),
    ("Calm · Wise · Compassionate", "शांत · ज्ञानी · करुणामय", "শান্ত · জ্ঞানী · সহানুভূতিশীল"),
    ("Gentle · Caring · Imaginative", "कोमल · स्नेही · कल्पनाशील", "কোমল · যত্নশীল · কল্পনাপ্রবণ"),
]
FALLBACK_THOUGHT = [
    ("Begin gently; steady steps make strong weeks.", "धीरे से शुरुआत करें; स्थिर कदम मज़बूत सप्ताह बनाते हैं।",
     "ধীরে শুরু করুন; স্থির পদক্ষেপেই সপ্তাহ মজবুত হয়।"),
    ("Courage is simply doing the next right thing.", "साहस का अर्थ है अगला सही कदम उठाना।",
     "সাহস মানে পরের সঠিক কাজটি করা।"),
    ("Speak kindly and listen fully; words build bridges.", "प्रेम से बोलें और ध्यान से सुनें; शब्द पुल बनाते हैं।",
     "ভালোবেসে বলুন, মন দিয়ে শুনুন; কথাই সেতু গড়ে।"),
    ("Learn one new thing today; wisdom grows quietly.", "आज कुछ नया सीखें; ज्ञान चुपचाप बढ़ता है।",
     "আজ নতুন কিছু শিখুন; জ্ঞান নীরবে বাড়ে।"),
    ("Make room for beauty, music and the people you love.", "सुंदरता, संगीत और अपनों के लिए समय निकालें।",
     "সৌন্দর্য, সংগীত আর প্রিয়জনদের জন্য সময় রাখুন।"),
    ("Patient effort today becomes lasting strength tomorrow.", "आज का धैर्यपूर्ण प्रयास कल की स्थायी शक्ति बनता है।",
     "আজকের ধৈর্যশীল প্রচেষ্টাই কালকের স্থায়ী শক্তি।"),
    ("Rest, reflect and let your inner light recharge.", "आराम करें, विचार करें और अपनी भीतरी रोशनी को फिर से भरें।",
     "বিশ্রাম নিন, ভাবুন, আর ভেতরের আলোকে নতুন করে জ্বালান।"),
]
FESTIVALS = {
    "goodmorning": {"name": ("Good morning", "सुप्रभात", "সুপ্রভাত"), "bg": (38, 33, 92), "motif": "sunrise",
                    "msg": ("A new day, a fresh start. Wishing you a calm and happy day.",
                            "नया दिन, नई शुरुआत। आपका दिन शांत और सुखद हो।",
                            "নতুন দিন, নতুন শুরু। আপনার দিন শান্ত ও আনন্দময় হোক।")},
    "diwali": {"name": ("Shubh Deepavali", "शुभ दीपावली", "শুভ দীপাবলি"), "bg": (65, 36, 2), "motif": "diya",
               "msg": ("May your home glow with light, love and new beginnings.",
                       "आपका घर रोशनी, प्रेम और नई शुरुआत से जगमगाए।",
                       "আপনার ঘর আলো, ভালোবাসা আর নতুন শুরুতে ভরে উঠুক।")},
    "bhaidooj": {"name": ("Happy Bhai Dooj", "भाई दूज की शुभकामनाएँ", "শুভ ভাইফোঁটা"), "bg": (75, 21, 40),
                 "motif": "diya",
                 "msg": ("To the bond that grows stronger every year.",
                         "हर साल और मज़बूत होते इस रिश्ते के नाम।",
                         "প্রতি বছর আরও মজবুত হওয়া এই বন্ধনের জন্য।")},
    "chhath": {"name": ("Chhath Puja", "छठ पूजा", "ছট পূজা"), "bg": (74, 27, 12), "motif": "sunwater",
               "msg": ("May the rising sun bless you with health, strength and joy.",
                       "उगता सूरज आपको स्वास्थ्य, शक्ति और आनंद का आशीर्वाद दे।",
                       "উদীয়মান সূর্য আপনাকে স্বাস্থ্য, শক্তি ও আনন্দের আশীর্বাদ দিক।")},
    "durga": {"name": ("Shubho Durga Puja", "दुर्गा पूजा की शुभकामनाएँ", "শুভ দুর্গাপূজা"), "bg": (80, 19, 19),
              "motif": "lotus",
              "msg": ("May Maa Durga fill your life with courage, joy and protection.",
                      "माँ दुर्गा आपके जीवन को साहस, आनंद और सुरक्षा से भर दें।",
                      "মা দুর্গা আপনার জীবন সাহস, আনন্দ ও সুরক্ষায় ভরিয়ে দিন।")},
    "navratri": {"name": ("Happy Navratri", "शुभ नवरात्रि", "শুভ নবরাত্রি"), "bg": (60, 52, 137), "motif": "lotus",
                 "msg": ("Nine nights of devotion, nine blessings of strength.",
                         "भक्ति की नौ रातें, शक्ति के नौ आशीर्वाद।",
                         "ভক্তির নয় রাত, শক্তির নয় আশীর্বাদ।")},
    "holi": {"name": ("Happy Holi", "होली की शुभकामनाएँ", "হোলির শুভেচ্ছা"), "bg": (4, 52, 44), "motif": "dots",
             "msg": ("May your life be as bright and joyful as the colours of Holi.",
                     "आपका जीवन होली के रंगों जैसा उज्ज्वल और खुशहाल हो।",
                     "আপনার জীবন হোলির রঙের মতো উজ্জ্বল ও আনন্দময় হোক।")},
    "rakhi": {"name": ("Happy Raksha Bandhan", "रक्षाबंधन की शुभकामनाएँ", "রাখিবন্ধনের শুভেচ্ছা"),
              "bg": (75, 21, 40), "motif": "lotus",
              "msg": ("A thread of love, a promise of care.", "प्रेम का धागा, साथ निभाने का वादा।",
                      "ভালোবাসার সুতো, পাশে থাকার প্রতিশ্রুতি।")},
    "sankranti": {"name": ("Happy Makar Sankranti", "मकर संक्रांति की शुभकामनाएँ", "মকর সংক্রান্তির শুভেচ্ছা"),
                  "bg": (12, 68, 124), "motif": "kite",
                  "msg": ("May your dreams fly high like kites in the winter sky.",
                          "आपके सपने सर्दियों के आसमान में पतंगों की तरह ऊँचे उड़ें।",
                          "আপনার স্বপ্ন শীতের আকাশে ঘুড়ির মতো উঁচুতে উড়ুক।")},
}

def sign_l(i, lang):
    return pl((SIGNS[i], SIGNS_HI[i], SIGNS_BN[i]), lang)

def nak_l(i, lang):
    return pl((NAKSHATRAS[i], NAK_HI[i], NAK_BN[i]), lang)

def date_line(day, lang):
    wd = day.weekday()
    if lang == "en":
        return f"{EN_WD[wd]}, {day.day} {EN_MON[day.month - 1]}"
    if lang == "hi":
        return f"{VARA_T[wd][1]}, {day.day} {MON_HI[day.month - 1]}"
    return f"{VARA_T[wd][2]}, {day.day} {MON_BN[day.month - 1]}"

def daily_sky(ref):
    jd = julian_day(ref)
    moon, _ = sidereal_lon(jd, swe.MOON)
    sun, _ = sidereal_lon(jd, swe.SUN)
    tithi = int(((moon - sun) % 360) // 12)
    return {"moon_sign": int(moon // 30), "nak": int(moon // NAK_LEN),
            "tithi_name": 14 if tithi == 14 else 15 if tithi == 29 else tithi % 15,
            "paksha": 0 if tithi < 15 else 1}

def daily_cards_prompt(day, ref, lang):
    sky = daily_sky(ref)
    lang_name = ANSWER_LANG[lang]
    rashi_lines = "\n".join(f"{i + 1}. {SIGNS[i]}: today's Moon is in the "
                            f"{ordinal((sky['moon_sign'] - i) % 12 + 1)} sign from it" for i in range(12))
    nak_list = ", ".join(NAKSHATRAS)
    fest_list = ", ".join(FESTIVALS)
    return f"""You write short, warm, positive daily messages for Dishara, a Vedic astrology app.
Date: {day:%d %B %Y}, {EN_WD[day.weekday()]}. Today's Moon: {SIGNS[sky['moon_sign']]}, nakshatra
{NAKSHATRAS[sky['nak']]}, tithi {PAKSHA_T[sky['paksha']][0]} {TITHI_T[sky['tithi_name']][0]}.

Write everything in {lang_name}, natural and everyday, in {lang_name}'s own script.
Rules: no emojis, no hashtags, no predictions of specific events, no fear, no promises about health,
money or relationships, never mention death, illness or accidents. Keep every line positive and practical.

Return ONLY JSON with exactly this shape:
{{"thought": [3 different strings, max 14 words each, inspired by today's nakshatra and weekday],
  "rashi": [12 items in the order below; each item is a list of 3 different strings, max 9 words each,
            a gentle message for that Moon sign today based on the Moon's position from it],
  "nakshatra": [27 items in the order below; each item is a list of 2 strings, max 12 words each,
                about that nakshatra's natural strengths and how to use them today],
  "festival": {{one key for each of: {fest_list}; each value is a list of 2 warm greeting wishes,
               max 18 words each, suitable to send to family and friends}}}}

Rashis (Moon signs) in order, with today's Moon position from each:
{rashi_lines}

Nakshatras in order: {nak_list}"""

def daily_content(day, lang):
    key = f"{day.isoformat()}|{lang}"
    cache = st.session_state.setdefault("daily_cards", {})
    if key not in cache:
        row = get_daily_cards(day.isoformat(), lang)
        if row:
            cache[key] = row
    return cache.get(key)

def pick_variant(content, path, var, fallback):
    try:
        node = content
        for p in path:
            node = node[p]
        if isinstance(node, list) and node:
            return str(node[var % len(node)])
        if isinstance(node, str) and node:
            return node
    except Exception:
        pass
    return fallback

# ---------------- SHAREABLE CARDS: DRAWING ----------------
CW, CH = 1080, 1350
C_BG, C_BG2 = (38, 33, 92), (60, 52, 137)
C_GOLD, C_ORANGE = (250, 199, 117), (239, 159, 39)
C_LAV, C_MUTED, C_WHITE, C_LINE = (206, 203, 246), (175, 169, 236), (238, 237, 254), (127, 119, 221)
CARD_FONT_URLS = {
    "en": ("https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
           "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf"),
    "hi": ("https://github.com/google/fonts/raw/main/ofl/hind/Hind-Regular.ttf",
           "https://github.com/google/fonts/raw/main/ofl/hind/Hind-SemiBold.ttf"),
    "bn": ("https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-Regular.ttf",
           "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-SemiBold.ttf"),
}
try:
    RAQM_OK = bool(features.check_feature("raqm"))
except Exception:
    RAQM_OK = False

@st.cache_resource(show_spinner=False)
def font_data(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

def lang_ok(lang):
    if lang == "en":
        return True
    return RAQM_OK and all(font_data(u) for u in CARD_FONT_URLS[lang])

def card_font(size, bold, lang):
    data = font_data(CARD_FONT_URLS[lang][1 if bold else 0])
    if data is None:
        if lang != "en":
            return card_font(size, bold, "en")
        return ImageFont.load_default(size=size)
    if lang != "en":
        return ImageFont.truetype(io.BytesIO(data), size, layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.truetype(io.BytesIO(data), size)

class Card:
    def __init__(self, lang, bg=C_BG):
        self.lang = lang
        self.img = Image.new("RGB", (CW, CH), bg)
        self.d = ImageDraw.Draw(self.img)

    def f(self, size, bold=False):
        return card_font(size, bold, self.lang)

    def center(self, y, text, size, fill, bold=False):
        f = self.f(size, bold)
        w = self.d.textlength(text, font=f)
        self.d.text(((CW - w) / 2, y), text, font=f, fill=fill)

    def left(self, x, y, text, size, fill, bold=False):
        self.d.text((x, y), text, font=self.f(size, bold), fill=fill)

    def wrap(self, text, size, bold, max_w):
        f = self.f(size, bold)
        lines, cur_l = [], ""
        for word in str(text).split():
            test = (cur_l + " " + word).strip()
            if self.d.textlength(test, font=f) <= max_w:
                cur_l = test
            else:
                if cur_l:
                    lines.append(cur_l)
                cur_l = word
        if cur_l:
            lines.append(cur_l)
        return lines

    def block(self, y, text, size, fill, bold=False, max_w=CW - 200, gap=1.35):
        for ln in self.wrap(text, size, bold, max_w):
            self.center(y, ln, size, fill, bold)
            y += int(size * gap)
        return y

    def png(self):
        buf = io.BytesIO()
        self.img.save(buf, format="PNG")
        return buf.getvalue()

def draw_sunrise(d, cx, cy, r):
    for deg in (20, 55, 90, 125, 160):
        a = math.radians(deg)
        d.line([(cx + (r + r * 0.25) * math.cos(a), cy - (r + r * 0.25) * math.sin(a)),
                (cx + (r + r * 0.55) * math.cos(a), cy - (r + r * 0.55) * math.sin(a))],
               fill=C_GOLD, width=max(3, r // 14))
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=C_ORANGE)
    r2 = int(r * 0.58)
    d.pieslice([cx - r2, cy - r2, cx + r2, cy + r2], 180, 360, fill=C_GOLD)
    d.line([(cx - r * 1.8, cy), (cx + r * 1.8, cy)], fill=C_LINE, width=3)

def draw_star(d, cx, cy, r_out, r_in, fill):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)

def draw_emblem(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=C_GOLD, width=4)
    ri = int(r * 0.72)
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=C_BG)
    draw_star(d, cx, cy, r * 0.5, r * 0.2, C_GOLD)
    for a in (0, 90, 180, 270):
        ar = math.radians(a)
        x, y = cx + (r + 18) * math.cos(ar), cy + (r + 18) * math.sin(ar)
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=C_ORANGE)

def draw_diya(d, cx, cy, s):
    d.polygon([(cx, cy - s * 1.35), (cx + s * 0.32, cy - s * 0.62), (cx, cy - s * 0.3),
               (cx - s * 0.32, cy - s * 0.62)], fill=C_GOLD)
    d.polygon([(cx, cy - s * 1.0), (cx + s * 0.16, cy - s * 0.6), (cx, cy - s * 0.42),
               (cx - s * 0.16, cy - s * 0.6)], fill=C_ORANGE)
    d.chord([cx - s, cy - s * 0.55, cx + s, cy + s * 0.55], 0, 180, fill=(186, 117, 23))
    d.line([(cx - s * 0.85, cy + s * 0.08), (cx + s * 0.85, cy + s * 0.08)], fill=C_GOLD, width=5)

def draw_lotus(d, cx, cy, s):
    for off, col in ((-0.62, (237, 147, 177)), (0.62, (237, 147, 177)), (-0.32, (244, 192, 209)),
                     (0.32, (244, 192, 209)), (0.0, (251, 234, 240))):
        top = cy - s * (0.95 - abs(off) * 0.45)
        d.ellipse([cx + off * s - s * 0.24, top, cx + off * s + s * 0.24, cy + s * 0.12], fill=col)
    d.chord([cx - s * 1.1, cy - s * 0.1, cx + s * 1.1, cy + s * 0.5], 0, 180, fill=(29, 158, 117))

def draw_kite(d, cx, cy, s):
    d.polygon([(cx, cy - s), (cx + s * 0.7, cy), (cx, cy + s), (cx - s * 0.7, cy)], fill=C_ORANGE)
    d.line([(cx, cy - s), (cx, cy + s)], fill=C_GOLD, width=4)
    d.line([(cx - s * 0.7, cy), (cx + s * 0.7, cy)], fill=C_GOLD, width=4)
    pts = [(cx, cy + s)]
    for i in range(1, 7):
        pts.append((cx + (25 if i % 2 else -25), cy + s + i * 30))
    d.line(pts, fill=C_LAV, width=3)
    for x, y in pts[2::2]:
        d.polygon([(x - 12, y - 8), (x + 12, y - 8), (x, y + 10)], fill=C_GOLD)

def draw_dots(d, cx, cy, s):
    spots = [(-0.8, -0.3, 0.32, (212, 83, 126)), (0.7, -0.5, 0.28, (239, 159, 39)),
             (0.0, 0.25, 0.36, (93, 202, 165)), (-0.4, 0.75, 0.22, (127, 119, 221)),
             (0.85, 0.55, 0.24, (250, 199, 117)), (0.15, -0.75, 0.18, (240, 153, 123))]
    for dx, dy, rr, col in spots:
        x, y, r = cx + dx * s, cy + dy * s, rr * s
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)

def draw_sunwater(d, cx, cy, s):
    draw_sunrise(d, cx, cy, int(s * 0.8))
    for i in range(3):
        y = cy + s * 0.25 + i * s * 0.18
        pts = [(cx - s * 1.3 + k * s * 0.26, y + (8 if k % 2 else -8)) for k in range(11)]
        d.line(pts, fill=C_LAV, width=4)

MOTIFS = {"sunrise": lambda d, cx, cy, s: draw_sunrise(d, cx, cy, int(s * 0.8)),
          "diya": draw_diya, "lotus": draw_lotus, "kite": draw_kite, "dots": draw_dots,
          "sunwater": draw_sunwater}

def card_frame(c, cta, header=True):
    if header:
        draw_sunrise(c.d, CW // 2, 150, 60)
        c.center(172, pl(CARD_T["wordmark"], c.lang), 44, C_GOLD, True)
    c.d.line([(140, 1205), (CW - 140, 1205)], fill=(83, 74, 183), width=2)
    c.center(1222, f"{pl(CARD_T['wordmark'], c.lang)} · {cta}", 30, C_LAV)
    c.center(1272, APP_URL.replace("https://", ""), 32, C_ORANGE, True)

def identity_card(lang, label, name, traits, line, ruled, from_line, cta):
    c = Card(lang)
    card_frame(c, cta)
    c.center(285, label, 38, C_MUTED)
    y = c.block(335, name, 80, C_GOLD, True, max_w=CW - 160, gap=1.15)
    draw_emblem(c.d, CW // 2, y + 125, 95)
    y += 270
    c.center(y, traits, 38, C_LAV, True)
    y = c.block(y + 75, line, 42, C_WHITE, False, max_w=CW - 220)
    c.center(y + 20, ruled, 32, C_MUTED)
    if from_line:
        c.center(1135, from_line, 34, C_GOLD, True)
    return c

def message_card(lang, title, sub, msg, from_line, cta):
    c = Card(lang)
    card_frame(c, cta)
    c.center(290, title, 48, C_GOLD, True)
    c.center(360, sub, 32, C_MUTED)
    c.block(500, msg, 60, C_WHITE, True, max_w=CW - 200, gap=1.3)
    draw_sunrise(c.d, CW // 2, 1075, 70)
    if from_line:
        c.center(1112, from_line, 32, C_GOLD, True)
    return c

def guide_card(lang, title, sub, lines12, from_line, cta):
    c = Card(lang)
    card_frame(c, cta)
    c.center(265, title, 46, C_GOLD, True)
    c.center(330, sub, 28, C_MUTED)
    top, rowh = 395, 120
    for i in range(12):
        col, row = i % 2, i // 2
        x, y = (80 if col == 0 else 560), top + row * rowh
        c.d.line([(x, y), (x + 440, y)], fill=(83, 74, 183), width=2)
        c.left(x, y + 10, sign_l(i, lang), 30, C_GOLD, True)
        ly = y + 52
        for ln in c.wrap(lines12[i], 25, False, 440)[:2]:
            c.left(x, ly, ln, 25, C_LAV)
            ly += 32
    if from_line:
        c.center(1150, from_line, 30, C_GOLD, True)
    return c

def festival_card(lang, key, msg, sender, cta):
    fest = FESTIVALS[key]
    c = Card(lang, fest["bg"])
    card_frame(c, cta, header=False)
    y = c.block(150, pl(fest["name"], lang), 76, C_GOLD, True, max_w=CW - 160, gap=1.15)
    MOTIFS[fest["motif"]](c.d, CW // 2, max(y + 230, 560), 150)
    y = c.block(790, msg, 44, (250, 238, 218), False, max_w=CW - 220)
    if sender:
        c.center(max(y + 30, 1060), pl(CARD_T["with_love"], lang).format(n=sender), 42, C_GOLD, True)
    return c

def share_tab(chart, pname, today, day_ref):
    st.markdown(f"<h3 style='margin:0'>{t('sh_title')}</h3><p class='muted'>{t('sh_sub')} · "
                f"{date_line(today, L())}</p>", unsafe_allow_html=True)
    kinds = ["my_rashi", "my_nak", "today_me", "guide", "thought", "festival"]
    kind = st.segmented_control("card_kind", kinds, default="guide", key="card_kind",
                                format_func=lambda k: t("k_" + k), label_visibility="collapsed")
    kind = kind or "guide"
    pc, cc = st.columns([1.15, 1])
    with cc:
        codes = list(LANG_CODES)
        card_lang = st.radio(t("sh_lang"), codes, horizontal=True, key="card_lang",
                             index=codes.index(L()), format_func=lambda c: LANG_CODES[c])
        lang = card_lang if lang_ok(card_lang) else "en"
        if lang != card_lang:
            st.caption(t("sh_lang_off"))
        fest_key = None
        if kind == "festival":
            fest_key = st.selectbox(t("sh_fest"), list(FESTIVALS), key="card_fest",
                                    format_func=lambda k: pick(FESTIVALS[k]["name"]))
        if st.button(t("sh_another"), key="sh_another_btn"):
            st.session_state.card_var = st.session_state.get("card_var", 0) + 1
        var = st.session_state.get("card_var", 0)
        sender = st.text_input(t("sh_name"), key="card_name").strip()

    content = daily_content(today, lang)
    if content is None:
        st.session_state.need_cards = (today.isoformat(), lang)
    sky = daily_sky(day_ref)
    my_rashi = chart["planets"]["Moon"]["sign"]
    my_nak = chart["planets"]["Moon"]["nak"]

    def rashi_msg(i):
        fb = pl(MOON_HOUSE_T[(sky["moon_sign"] - i) % 12 + 1], lang)
        return pick_variant(content, ["rashi", i], var, fb)

    from_line = pl(CARD_T["from"], lang).format(n=sender) if sender else ""
    day_sub = date_line(today, lang)
    moon_sub = f"{day_sub} · {pl(CARD_T['moon_in'], lang).format(n=nak_l(sky['nak'], lang))}"
    if kind == "my_rashi":
        card = identity_card(lang, pl(CARD_T["my_moon"], lang), sign_l(my_rashi, lang),
                             pl(RASHI_TRAITS[my_rashi], lang), rashi_msg(my_rashi),
                             pl(CARD_T["ruled"], lang).format(p=pl(PLANET_T[SIGN_LORDS[my_rashi]], lang)),
                             from_line, pl(CARD_T["cta_rashi"], lang))
    elif kind == "my_nak":
        trait = pl(NAK_TRAITS[my_nak], lang).split(" · ")[0]
        trait = trait.lower() if lang == "en" else trait
        fb = pl(CARD_T["nak_fallback"], lang).format(t=trait)
        card = identity_card(lang, pl(CARD_T["my_nak"], lang), nak_l(my_nak, lang),
                             pl(NAK_TRAITS[my_nak], lang), pick_variant(content, ["nakshatra", my_nak], var, fb),
                             pl(CARD_T["ruled"], lang).format(p=pl(PLANET_T[DASHA_ORDER[my_nak % 9][0]], lang)),
                             from_line, pl(CARD_T["cta_nak"], lang))
    elif kind == "today_me":
        card = message_card(lang, pl(CARD_T["today_for"], lang).format(s=sign_l(my_rashi, lang)), day_sub,
                            rashi_msg(my_rashi), from_line, pl(CARD_T["cta_rashi"], lang))
    elif kind == "guide":
        card = guide_card(lang, pl(CARD_T["guide"], lang), moon_sub, [rashi_msg(i) for i in range(12)],
                          from_line, pl(CARD_T["cta_rashi"], lang))
    elif kind == "thought":
        fb = pl(FALLBACK_THOUGHT[today.weekday()], lang)
        card = message_card(lang, pl(CARD_T["thought"], lang), moon_sub,
                            pick_variant(content, ["thought"], var, fb), from_line, pl(CARD_T["cta_day"], lang))
    else:
        fb = pl(FESTIVALS[fest_key]["msg"], lang)
        card = festival_card(lang, fest_key, pick_variant(content, ["festival", fest_key], var, fb),
                             sender, pl(CARD_T["cta_day"], lang))
    png = card.png()
    with pc:
        st.image(png, use_container_width=True)
    with cc:
        st.download_button(t("sh_download"), data=png, file_name=f"dishara-{kind}-{today}.png",
                           mime="image/png", use_container_width=True)
        msg = t("sh_wa_msg", url=APP_URL)
        st.markdown(f"<a href='https://wa.me/?text={urllib.parse.quote(msg)}' target='_blank' "
                    f"style='display:block;text-align:center;background:#25D366;color:#ffffff;border-radius:999px;"
                    f"padding:0.5rem 1rem;text-decoration:none;font-weight:500;margin-top:8px'>{t('sh_whatsapp')}</a>",
                    unsafe_allow_html=True)
        st.caption(t("sh_hint"))
        if content is None:
            st.caption(t("sh_fresh"))

# ---------------- SCREENS ----------------
def hero():
    st.markdown(f"""<div style="text-align:center;padding:16px 0 4px">
      <svg viewBox="0 0 200 120" width="200"><g stroke="#FAC775" stroke-width="2" stroke-linecap="round">
      <line x1="100" y1="8" x2="100" y2="26"/><line x1="40" y1="33" x2="53" y2="46"/><line x1="160" y1="33" x2="147" y2="46"/>
      <line x1="14" y1="90" x2="31" y2="90"/><line x1="186" y1="90" x2="169" y2="90"/></g>
      <path d="M45 98 A55 55 0 0 1 155 98 Z" fill="#EF9F27"/><path d="M68 98 A32 32 0 0 1 132 98 Z" fill="#FAC775"/>
      <line x1="10" y1="98" x2="190" y2="98" stroke="#7F77DD" stroke-width="1.5"/></svg>
      <h1 style="font-size:48px;margin:0">Dishara</h1>
      <p class="gold" style="margin:0">दिशारा · দিশারা</p>
      <p style="color:#CECBF6;font-size:15px">{t("tagline")}</p>
    </div>""", unsafe_allow_html=True)

def lang_picker(uid=None, key="lang_pick"):
    codes = list(LANG_CODES)
    cur_l = L()
    choice = st.selectbox("Language · भाषा · ভাষা", codes, index=codes.index(cur_l),
                          format_func=lambda c: LANG_CODES[c], key=key)
    if choice != cur_l:
        st.session_state.ui_lang = choice
        if uid:
            save_user_lang(uid, choice)
        st.rerun()

def reset_conversation():
    st.session_state.conv_id = None
    st.session_state.conv_msgs = []
    st.session_state.conv_nonce = st.session_state.get("conv_nonce", 0) + 1

def auth_screen():
    hero()
    lang_picker(key="lang_pick_auth")
    st.markdown(f"<p class='muted' style='text-align:center'>{t('signin_intro')}</p>", unsafe_allow_html=True)
    tab_in, tab_up = st.tabs([t("tab_signin"), t("tab_signup")])
    logged_in = None
    with tab_in:
        with st.form("signin_form", border=False):
            email = st.text_input(t("email"), key="si_email", autocomplete="email")
            pw = st.text_input(t("password"), type="password", key="si_pw", autocomplete="current-password")
            submitted = st.form_submit_button(t("tab_signin"))
        if submitted:
            if not email.strip() or not pw:
                st.warning(t("autofill"))
            else:
                try:
                    res = auth_client().auth.sign_in_with_password({"email": email.strip(), "password": pw})
                    logged_in = {"email": res.user.email}
                except Exception:
                    st.error(t("signin_failed"))
        st.caption(t("email_hint"))
    with tab_up:
        email2 = st.text_input(t("email"), key="su_email", autocomplete="email")
        pw2 = st.text_input(t("password_new"), type="password", key="su_pw", autocomplete="new-password")
        consent = st.checkbox(t("consent"))
        if st.button(t("tab_signup"), key="su_btn"):
            if len(pw2) < 8:
                st.error(t("pw_short"))
            elif not consent:
                st.error(t("need_consent"))
            else:
                try:
                    res = auth_client().auth.sign_up({"email": email2.strip(), "password": pw2})
                    if res.session:
                        logged_in = {"email": res.user.email}
                    else:
                        st.success(t("check_email"))
                except Exception as ex:
                    st.error(t("signup_failed", err=ex))
    st.markdown(f"<p class='muted' style='text-align:center'><a href='?page=privacy' target='_blank' "
                f"style='color:#AFA9EC'>{t('privacy_link')}</a></p>", unsafe_allow_html=True)
    if logged_in:
        st.session_state.user = logged_in
        st.rerun()

def chart_form(uid, existing):
    hero()
    ex = existing or {}
    first_chart = not st.session_state.get("charts")
    st.markdown("### " + (t("edit_birth") if ex else t("add_chart_title")))
    name = st.text_input(t("name"), value=ex.get("name", ""))
    rel_default = RELATIONS.index(ex["relation"]) if ex.get("relation") in RELATIONS else (0 if first_chart else 1)
    rel = st.selectbox(t("whose_chart"), RELATIONS, index=rel_default, format_func=lambda r: pick(RELATION_T[r]))
    bdate = st.date_input(t("birth_date"), value=date.fromisoformat(ex["birth_date"]) if ex else None,
                          min_value=date(1900, 1, 1), max_value=date.today(), format="DD/MM/YYYY")

    unknown = st.checkbox(t("unknown_time"), value=ex.get("time_unknown", False))
    hour = minute = ampm = None
    if not unknown:
        ih = im = iap = None
        if ex and not ex.get("time_unknown"):
            tm = datetime.strptime(ex["birth_time"][:5], "%H:%M")
            ih, im, iap = (tm.hour % 12 or 12) - 1, tm.minute, 0 if tm.hour < 12 else 1
        st.markdown(f"<p class='muted'>{t('time_hint')}</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        hour = c1.selectbox(t("hour"), list(range(1, 13)), index=ih, placeholder=t("hour"))
        minute = c2.selectbox(t("minute"), [f"{m:02d}" for m in range(60)], index=im, placeholder=t("minute"))
        ampm = c3.selectbox(t("ampm"), ["AM", "PM"], index=iap, placeholder=t("ampm"))
    else:
        st.caption(t("unknown_caption"))

    place = (ex["place"], ex["lat"], ex["lon"]) if ex else None
    if ex:
        st.markdown(f"<p class='muted'>{t('current_place', place=html.escape(ex['place']))}</p>",
                    unsafe_allow_html=True)
    query = st.text_input(t("place_label"), placeholder=t("place_ph"))
    if len(query.strip()) >= 3:
        with st.spinner(t("finding_places")):
            options = search_places(query.strip())
        if options:
            labels = [o[0] for o in options]
            pk = st.selectbox(t("select_place"), labels, index=None, placeholder=t("choose_place"))
            if pk:
                place = options[labels.index(pk)]
        else:
            st.warning(t("no_match"))

    if st.button(t("save_chart")):
        problems = []
        if not name.strip():
            problems.append(t("p_name"))
        if not bdate:
            problems.append(t("p_date"))
        if not unknown and (hour is None or minute is None or ampm is None):
            problems.append(t("p_time"))
        if not place:
            problems.append(t("p_place"))
        if problems:
            st.error(t("please_add", items=", ".join(problems)))
            return
        h24, mins = (12, 0) if unknown else (hour % 12 + (12 if ampm == "PM" else 0), int(minute))
        row = {"user_id": uid, "name": name.strip(), "relation": rel,
               "birth_date": bdate.isoformat(), "birth_time": f"{h24:02d}:{mins:02d}",
               "time_unknown": unknown, "place": place[0], "lat": place[1], "lon": place[2],
               "language": ANSWER_LANG[L()]}
        saved = None
        try:
            if ex:
                saved = (db().table("profiles").update(row).eq("id", ex["id"])
                         .eq("user_id", uid).execute().data[0])
            else:
                saved = db().table("profiles").insert(row).execute().data[0]
        except Exception as ex2:
            st.error(t("save_failed", err=ex2))
        if saved:
            st.session_state.charts = list_charts(uid)
            st.session_state.active_id = saved["id"]
            st.session_state.mode = None
            reset_conversation()
            st.rerun()

    if not first_chart:
        if st.button(t("cancel")):
            st.session_state.mode = None
            st.rerun()
    if ex:
        st.markdown("---")
        confirm = st.checkbox(t("delete_confirm", name=ex["name"]))
        if confirm and st.button(t("delete_chart")):
            db().table("profiles").delete().eq("id", ex["id"]).eq("user_id", uid).execute()
            st.session_state.charts = list_charts(uid)
            st.session_state.active_id = None
            st.session_state.mode = None
            reset_conversation()
            st.rerun()

# ---------------- APP FLOW ----------------
if "user" not in st.session_state:
    auth_screen()
    st.stop()

user_email = st.session_state.user["email"]
if "uid" not in st.session_state:
    uid0, saved_lang = get_or_create_user(user_email, None, L())
    st.session_state.uid = uid0
    st.session_state.ui_lang = saved_lang if saved_lang in LANG_CODES else "en"
uid = st.session_state.uid

if "charts" not in st.session_state:
    st.session_state.charts = list_charts(uid)
    reset_conversation()
charts = st.session_state.charts
mode = st.session_state.get("mode")

if not charts or mode == "new":
    lang_picker(uid, key="lang_pick_form")
    chart_form(uid, None)
    st.stop()

by_id = {c["id"]: c for c in charts}
if st.session_state.get("active_id") not in by_id:
    self_chart = next((c for c in charts if c["relation"] == "Self"), charts[0])
    st.session_state.active_id = self_chart["id"]

if mode == "edit":
    chart_form(uid, by_id[st.session_state.active_id])
    st.stop()

def chart_label(i):
    c = by_id[i]
    return f"{c['name']} ({pick(RELATION_T.get(c['relation'], (c['relation'],) * 3))})"

me = next((c for c in charts if c["relation"] == "Self"), charts[0])
g1, g2 = st.columns([3, 1])
g1.markdown(f"<p class='muted'>{t('shubh_din')}</p><h2 style='margin-top:0'>"
            f"{t('namaste', name=html.escape(me['name']))}</h2>", unsafe_allow_html=True)
with g2:
    lang_picker(uid, key="lang_pick_main")

ids = [c["id"] for c in charts]
c1, c2 = st.columns([3, 1])
picked = c1.selectbox(t("viewing_chart"), ids, index=ids.index(st.session_state.active_id),
                      format_func=chart_label)
if picked != st.session_state.active_id:
    st.session_state.active_id = picked
    reset_conversation()
c2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
if c2.button(t("add_chart_btn")):
    st.session_state.mode = "new"
    st.rerun()

profile = by_id[st.session_state.active_id]
pid, pname, prel = profile["id"], profile["name"], profile["relation"]
chart = get_chart(profile)
now = datetime.now(timezone.utc).replace(tzinfo=None)
today = (now + timedelta(hours=IST)).date()
day_ref = datetime.combine(today, datetime.min.time()) + timedelta(hours=6 - IST)
cur = next(d for d in chart["dashas"] if d["start"] <= now < d["end"])

home, chat, kundali, match, share = st.tabs([t("tab_home"), t("tab_ask"), t("tab_kundali"),
                                             t("tab_match"), t("tab_share")])

# ----- HOME -----
with home:
    ind = daily_indicators(chart, day_ref)
    if ind["good_tara"]:
        tara_word = t("tw_support")
    elif ind["tara"] == "Janma":
        tara_word = t("tw_reflect")
    else:
        tara_word = t("tw_gentle")
    chandra_word = t("cw_good") if ind["good_chandra"] else t("cw_patience")
    av_line = t("av_line", b=ind["bindus"]) if ind["bindus"] is not None else ""
    band_label, _ = pick(BAND_T[ind["label"]])
    why = t("why_score", nak=nak_name(ind["nak_idx"]), name=html.escape(pname),
            tara=pick(TARA_T[ind["tara"]]), tara_word=tara_word, ch=ord_l(ind["chandra"]),
            ch_word=chandra_word, house=ord_l(ind["house"]))
    st.markdown(f"""<div class="card"><p class="muted">{t('todays_energy', date=f'{today:%d %b %Y}')}</p>
      <p style="{BIG_NUMBER}">{ind['score']}<span style="{SMALL_SUFFIX}"> / 100 · {band_label}</span></p>
      <p class="big">{pick(MOON_HOUSE_T[ind['house']])}</p>
      <p class="muted">{why}{av_line}</p></div>""", unsafe_allow_html=True)

    with st.expander(t("score_expander")):
        for lo, hi, band_key in SCORE_BANDS:
            bl, bm = pick(BAND_T[band_key])
            if lo <= ind["score"] <= hi:
                st.markdown(f"**→ {lo}–{hi} · {bl} ({t('today_tag')}):** {bm}")
            else:
                st.markdown(f"{lo}–{hi} · {bl}: {bm}")
        st.markdown(f"**{t('about_score')}**")
        st.caption(t("about1"))
        st.caption(t("about2"))

    tips_cache = st.session_state.setdefault("tips", {})
    tip_key = f"{pid}|{today}|{L()}"
    if tip_key not in tips_cache:
        saved_tip = get_saved_tip(uid, pid, today, L())
        if saved_tip:
            tips_cache[tip_key] = saved_tip
    st.markdown(f"<div class='card'><p class='muted'>{t('todays_tips')}</p></div>", unsafe_allow_html=True)
    tips_slot = st.empty()
    if tip_key in tips_cache:
        tips_slot.markdown(tips_cache[tip_key])
    else:
        tips_slot.caption(t("preparing_tips"))

    pct = int(100 * (now - cur["start"]) / (cur["end"] - cur["start"]))
    st.markdown(f"""<div class="card"><p class="muted">{t('current_chapter', date=f"{cur['end']:%b %Y}")}</p>
      <p class="big">{t('mahadasha', lord=planet_name(cur['lord']), theme=pick(CHAPTER_THEME_T[cur['lord']]))}</p>
      <div class="bar"><div style="width:{pct}%"></div></div></div>""", unsafe_allow_html=True)
    sub = upcoming_subperiods(chart, now, 1)[0]
    st.markdown(f"""<div class="card"><p class="muted">{t('current_sub', date=f"{sub['end']:%b %Y}")}</p>
      <p class="big">{planet_name(sub['md'])}–{planet_name(sub['lord'])}: {pick(CHAPTER_THEME_T[sub['lord']])}</p></div>""",
                unsafe_allow_html=True)
    if chart["time_unknown"]:
        st.caption(t("moon_chart_caption"))
    panchang_section(profile, now)

# ----- ASK DISHARA -----
with chat:
    convs = list_conversations(uid, pid)
    titles = {c["id"]: f"{c['created_at'][:10]} · {c['title']}" for c in convs}
    b1, b2 = st.columns([1, 2])
    if b1.button(t("new_conv")):
        reset_conversation()
        st.rerun()
    pk = b2.selectbox("past", list(titles), index=None, format_func=lambda i: titles[i],
                      placeholder=t("past_conv", n=len(convs)),
                      key=f"conv_pick_{pid}_{st.session_state.conv_nonce}", label_visibility="collapsed")
    if pk and pk != st.session_state.conv_id:
        st.session_state.conv_id = pk
        st.session_state.conv_msgs = load_conversation(uid, pk)

    if st.session_state.conv_id and st.session_state.conv_id in titles:
        st.markdown(f"<p class='muted'>{html.escape(titles[st.session_state.conv_id])}</p>", unsafe_allow_html=True)
    elif not st.session_state.conv_msgs:
        st.markdown(f"<p class='muted'>{t('ask_intro', name=html.escape(pname))}</p>", unsafe_allow_html=True)

    for m in st.session_state.conv_msgs:
        with st.chat_message(m["role"], avatar="🌅" if m["role"] == "assistant" else None):
            st.markdown(m["content"])

    q = st.chat_input(t("chat_ph"))
    if q:
        if not st.session_state.conv_id:
            st.session_state.conv_id = new_conversation(uid, pid, q)
        cid = st.session_state.conv_id
        st.session_state.conv_msgs.append({"role": "user", "content": q})
        save_message(uid, cid, "user", q)
        with st.chat_message("user"):
            st.markdown(q)
        if any(w in q.lower() for w in CRISIS_WORDS):
            answer = t("crisis_reply")
        else:
            with st.spinner(t("thinking")):
                past_topics = [c["title"] for c in convs if c["id"] != cid][:8]
                current = "\n".join(f"{m['role']}: {m['content']}"
                                    for m in st.session_state.conv_msgs[-11:-1])
                topic_text = q + " " + " ".join(m["content"] for m in st.session_state.conv_msgs[-5:-1]
                                                if m["role"] == "user")
                keys = detect_areas(topic_text)
                if keys:
                    area_txt = "\n\n".join(area_block(area_analysis(chart, k, now)) for k in keys[:3])
                else:
                    area_txt = "OVERVIEW OF ALL LIFE AREAS:\n" + areas_summary(chart, now)
                prompt = (f"BIRTH CHART:\n{chart_text(chart, now)}\n\n"
                          f"AREA ANALYSIS (calculated by Dishara's engine):\n{area_txt}\n\n"
                          f"TOPICS FROM EARLIER CONVERSATIONS: {'; '.join(past_topics) or 'None'}\n\n"
                          f"THIS CONVERSATION SO FAR:\n{current or 'None'}\n\nQUESTION: {q}")
                answer = ask_dishara(prompt, pname, prel) or t("resting")
        st.session_state.conv_msgs.append({"role": "assistant", "content": answer})
        save_message(uid, cid, "assistant", answer)
        with st.chat_message("assistant", avatar="🌅"):
            st.markdown(answer)

# ----- KUNDALI -----
with kundali:
    varga_opts = [VARGA_LIST[0]] if chart["time_unknown"] else VARGA_LIST
    n = st.selectbox(t("chart_select"), [v[0] for v in varga_opts],
                     format_func=lambda num: pick(dict(VARGA_LIST)[num]))
    st.markdown(kundali_svg(chart, n), unsafe_allow_html=True)
    st.caption(t("chart_caption") + (t("chart_caption_moon") if chart["time_unknown"] else ""))
    nb_set = neecha_bhanga(chart)
    rows = [{t("col_planet"): planet_name(nm), t("col_sign"): sign_name(p["sign"]),
             t("col_degree"): f"{p['deg']:.2f}°", t("col_house"): p["house"],
             t("col_role"): pick(ROLE_T[chart["roles"][nm]]),
             t("col_notes"): ", ".join(pick(NOTE_T[x]) for x in planet_notes(chart, nm, nb_set)) or "-",
             t("col_nak"): f"{nak_name(p['nak'])} {p['pada']}",
             "D9": short_sign(p["vargas"][9]), "D10": short_sign(p["vargas"][10])}
            for nm, p in chart["planets"].items()]
    st.dataframe(rows, hide_index=True)
    with st.expander(t("glossary_title")):
        st.markdown(
            "- **Lagna lord:** the ruler of your ascendant; always supportive, it represents you.\n"
            "- **Yogakaraka:** rules both a kendra and a trikona for your Lagna; the most "
            "beneficial planet in your chart.\n"
            "- **Functional benefic:** supportive for your Lagna; its periods tend to help.\n"
            "- **Neutral:** mixed; results depend on its placement and company.\n"
            "- **Functional malefic:** brings results through effort and patience for your Lagna. "
            "Not 'bad', just demanding.\n"
            "- **Combust:** very close to the Sun, so its qualities are partly hidden.\n"
            "- **Vargottama:** same sign in D1 and D9; extra strength and consistency.\n"
            "- **Debilitation cancelled:** a weak placement that turns into strength (Neecha Bhanga).")
        if L() != "en":
            st.caption(t("en_detail_note"))
        if chart["time_unknown"]:
            st.caption(t("roles_moon"))

    st.markdown(f"#### {t('life_areas')}")
    area_rows = []
    for key in AREAS:
        an = area_analysis(chart, key, now)
        area_rows.append({t("col_area"): pick(AREA_T[key]), t("col_outlook"): pick(VERDICT_T[an["verdict"]]),
                          t("col_strength"): an["supportive"][0] if an["supportive"] else "-",
                          t("col_dt"): (fmt_windows(an["windows"][:1]) or t("not_2y"))})
    st.dataframe(area_rows, hide_index=True)
    st.caption(t("areas_caption"))
    if L() != "en":
        st.caption(t("en_detail_note"))

    av = chart.get("av")
    if av:
        st.markdown(f"#### {t('av_title')}")
        av_rows = []
        for h in range(1, 13):
            s = (chart["asc_sign"] + h - 1) % 12
            pts = av["sav"][s]
            av_rows.append({t("col_house"): h, t("col_sign"): short_sign(s), t("col_points"): pts,
                            t("col_av_strength"): t("av_strong") if pts >= 28 else
                            t("av_avg") if pts >= 25 else t("av_build")})
        st.dataframe(av_rows, hide_index=True)
        st.caption(t("av_caption", total=sum(av["sav"])))

    ys = find_yogas(chart)
    if ys:
        st.markdown(f"#### {t('yogas')}")
        for y in ys:
            st.markdown(f"- {y}")
        if L() != "en":
            st.caption(t("en_detail_note"))
    st.markdown(f"#### {t('life_chapters')}")
    for d in chart["dashas"]:
        mark = f"  ← {t('now')}" if d is cur else ""
        st.markdown(f"**{planet_name(d['lord'])}** · {d['start']:%b %Y} – {d['end']:%b %Y}{mark}")

# ----- MATCH MAKING -----
with match:
    if len(charts) < 2:
        st.info(t("add_partner"))
    else:
        m1, m2 = st.columns(2)
        a = m1.selectbox(t("partner1"), ids, index=0, format_func=chart_label, key="m_a")
        b = m2.selectbox(t("partner2"), ids, index=1, format_func=chart_label, key="m_b")
        if a == b:
            st.warning(t("choose_two"))
        else:
            if st.button(t("check_compat")):
                ca, cb = get_chart(by_id[a]), get_chart(by_id[b])
                st.session_state.match = {"a": a, "b": b, "rows": ashtakoot(ca, cb),
                                          "manglik": (manglik(ca), manglik(cb)), "reading": None}
            mres = st.session_state.get("match")
            if mres and mres["a"] == a and mres["b"] == b:
                total = sum(r[1] for r in mres["rows"])
                vkey = ("v_excellent" if total >= 32 else "v_vgood" if total >= 25
                        else "v_good" if total >= 18 else "v_effort")
                st.markdown(f"""<div class="card"><p class="muted">{t('guna_milan')}</p>
                  <p style="{BIG_NUMBER}">{total:g}<span style="{SMALL_SUFFIX}"> / 36</span></p>
                  <p class="big">{t(vkey)}</p>
                  <p class="muted">{t('match_note')}</p></div>""", unsafe_allow_html=True)
                st.dataframe([{t("col_koota"): pick(KOOTA_T[r[0]]), t("col_score"): f"{r[1]:g} / {r[2]}",
                               t("col_reflects"): r[3]} for r in mres["rows"]], hide_index=True)
                if L() != "en":
                    st.caption(t("en_detail_note"))
                (la, ma), (lb, mb) = mres["manglik"]
                st.markdown(f"**{t('manglik_title')}**  \n"
                            f"{html.escape(by_id[a]['name'])}: {manglik_text_ui(la, ma)}  \n"
                            f"{html.escape(by_id[b]['name'])}: {manglik_text_ui(lb, mb)}")
                st.caption(t("manglik_caption"))
                if st.button(t("detailed_btn")):
                    ca, cb = get_chart(by_id[a]), get_chart(by_id[b])
                    koota_txt = "\n".join(f"{r[0]}: {r[1]:g}/{r[2]} ({r[3]})" for r in mres["rows"])
                    marr_a = area_block(area_analysis(ca, "marriage", now))
                    marr_b = area_block(area_analysis(cb, "marriage", now))
                    prompt = (
                        f"COMPATIBILITY REQUEST between {by_id[a]['name']} (Partner 1) and "
                        f"{by_id[b]['name']} (Partner 2).\n\nPARTNER 1 CHART:\n{chart_text(ca, now)}\n\n"
                        f"PARTNER 1 MARRIAGE ANALYSIS:\n{marr_a}\n\n"
                        f"PARTNER 2 CHART:\n{chart_text(cb, now)}\n\n"
                        f"PARTNER 2 MARRIAGE ANALYSIS:\n{marr_b}\n\nASHTAKOOT ({total:g}/36):\n{koota_txt}\n\n"
                        f"MANGLIK: Partner 1 {manglik_text(la, ma)}; Partner 2 {manglik_text(lb, mb)}\n\n"
                        f"Write a detailed, balanced compatibility reading with bold headings (translated into "
                        f"the reply language): Overall (2 lines putting the score in context), Where you "
                        f"naturally connect (3 bullets citing kootas and chart factors such as 7th houses, Venus, "
                        f"Moon and D9), Where you'll need understanding (2-3 bullets framed as growth areas with "
                        f"practical advice), Making it work (3 practical tips). Never predict divorce or call the "
                        f"match doomed. Under 350 words.")
                    with st.spinner(t("comparing")):
                        mres["reading"] = ask_dishara(prompt, pname, "Self") or t("resting")
                if mres.get("reading"):
                    st.markdown(mres["reading"])

# ----- SHARE -----
with share:
    share_tab(chart, pname, today, day_ref)

# ----- FOOTER -----
st.divider()
if "paste-your-link" not in FEEDBACK_URL:
    st.markdown(f"<p class='muted' style='text-align:center'>{t('feedback')} "
                f"<a href='{FEEDBACK_URL}' style='color:#FAC775'>{t('feedback_link')}</a></p>",
                unsafe_allow_html=True)
st.markdown(f"<p class='muted' style='text-align:center;margin-bottom:20px'>"
            f"{t('signed_in', email=html.escape(user_email))} · "
            f"<a href='?page=privacy' target='_blank' style='color:#AFA9EC'>{t('privacy_link')}</a></p>",
            unsafe_allow_html=True)
_, f1, f2, _ = st.columns([1, 2, 2, 1])
if f1.button(t("edit_chart"), use_container_width=True):
    st.session_state.mode = "edit"
    st.rerun()
if f2.button(t("sign_out"), use_container_width=True):
    try:
        auth_client().auth.sign_out()
    except Exception:
        pass
    keep_lang = L()
    st.session_state.clear()
    st.session_state.ui_lang = keep_lang
    st.rerun()

# ----- DAILY TIPS: generated last, so the rest of the page appears first -----
tried = st.session_state.setdefault("tips_tried", set())
if tip_key not in st.session_state.tips and tip_key not in tried:
    tried.add(tip_key)
    ind_text = (f"Moon today in {ind['moon_sign']}, nakshatra {NAKSHATRAS[ind['nak_idx']]}; "
                f"Tara: {ind['tara']} ({'good' if ind['good_tara'] else 'challenging'}); "
                f"Moon is {ordinal(ind['chandra'])} from natal Moon "
                f"({'favourable' if ind['good_chandra'] else 'less favourable'}); "
                f"Moon transits house {ind['house']} from Lagna; "
                + (f"Moon's Ashtakavarga points today: {ind['bindus']}/8; " if ind["bindus"] is not None else "")
                + f"day score {ind['score']}/100 ({ind['label']}).")
    tip = ask_dishara(
        f"BIRTH CHART:\n{chart_text(chart, now)}\n\nTODAY'S INDICATORS:\n{ind_text}\n\n"
        f"DAILY TIPS REQUEST for {today:%d %b %Y}: Start with one bold line naming today's "
        f"theme. Then exactly 3 bullets: Work, Relationships, Wellbeing (translate these labels "
        f"and make them bold), each one practical action with a short reason from today's Moon, "
        f"Tara or the current dasha. Under 120 words.", pname, prel, fast=True)
    if tip:
        save_tip(uid, pid, today, L(), tip)
        st.session_state.tips[tip_key] = tip
        tips_slot.markdown(tip)
    else:
        tips_slot.caption(t("tips_soon"))

# ----- DAILY SHARE-CARD MESSAGES: generated once per day per language, shared by all users -----
need = st.session_state.get("need_cards")
if need:
    st.session_state.need_cards = None
    cards_tried = st.session_state.setdefault("cards_tried", set())
    if need not in cards_tried:
        cards_tried.add(need)
        day_iso, lang_c = need
        if get_daily_cards(day_iso, lang_c) is None:
            data = ai_json(daily_cards_prompt(today, day_ref, lang_c))
            if data:
                save_daily_cards(day_iso, lang_c, data)
                st.session_state.setdefault("daily_cards", {})[f"{day_iso}|{lang_c}"] = data
