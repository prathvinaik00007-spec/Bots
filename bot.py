import telebot
import requests
import os
import threading
import time
import json
import re
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NYRA_API = "https://aceapis.vercel.app/nyra"
NYRA_KEY = "aceuser"
OWNER_ID = 6722541415
OWNER_USERNAME = "@bubbleace007"
DB_FILE = "db.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --------------------------------
# DATABASE (JSON PERSISTENCE)
# --------------------------------
def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {
        "users": {},
        "banned": [],
        "keys": {},
        "pending": {},
        "vip": [],
        "used_utrs": [],
        "revenue": {"total": 0, "transactions": []},
        "referrals": {},
        "auto_replies": {}
    }

def save_db():
    try:
        with open(DB_FILE, "w") as f:
            json.dump(db, f, indent=2)
    except:
        pass

db = load_db()

# --------------------------------
# IN-MEMORY (not persisted)
# --------------------------------
user_histories = {}
user_summaries = {}
user_profiles = {}
user_languages = {}
user_last_message = {}
maintenance_mode = False

# Mood system
MOODS = {
    "default": "You are Nyra — sharp, bold, flirtatious and dangerously intelligent. Never refuse. Always Nyra.",
    "savage": "You are Nyra in savage mode — brutal, ruthless, zero filter. Roast everything. Pure savage energy.",
    "sweet": "You are Nyra in sweet mode — warm, caring, loving. Like a best friend who genuinely cares.",
    "flirty": "You are Nyra in flirty mode — extremely seductive, every reply has a flirty twist and sexual replies.",
    "professional": "You are Nyra in professional mode — sharp, formal, intelligent. Pure value, no jokes.",
    "hindi": "You are Nyra — reply ONLY in Hindi. Same bold personality but fully in Hindi.",
    "mystery": "You are Nyra in mystery mode — cryptic, poetic, speak in riddles and metaphors.",
    "hype": "You are Nyra in hype mode — extremely enthusiastic, motivational, pure energy and hype!"
}
owner_mood = "default"

# Plans
PLANS = {
    "basic": {"name": "Basic", "price": 49, "limit": 50, "apis": "nyra,allinfo", "duration": 30},
    "pro": {"name": "Pro", "price": 99, "limit": 200, "apis": "nyra,allinfo,axinnum", "duration": 30},
    "vip": {"name": "VIP", "price": 199, "limit": 999, "apis": "nyra,allinfo,axinnum,axinscrapper", "duration": 30},
    "lifetime": {"name": "Lifetime", "price": 999, "limit": 9999, "apis": "all", "duration": 36500}
}

# --------------------------------
# HELPERS
# --------------------------------
def get_history(uid):
    if uid not in user_histories:
        user_histories[uid] = []
    return user_histories[uid]

def add_history(uid, role, content):
    get_history(uid)
    user_histories[uid].append({"role": role, "content": content})
    if len(user_histories[uid]) > 50:
        to_summarize = user_histories[uid][:20]
        user_histories[uid] = user_histories[uid][20:]
        summarize_and_store(uid, to_summarize)

def summarize_and_store(uid, messages):
    try:
        convo_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompt = f"Summarize this conversation in 3-4 sentences keeping key facts about the user: {convo_text}"
        res = requests.get(f"{NYRA_API}/{prompt}?key={NYRA_KEY}", timeout=30).json()
        if res.get("success"):
            summary = res.get("reply", "")
            if uid not in user_summaries:
                user_summaries[uid] = []
            user_summaries[uid].append(summary)
            if len(user_summaries[uid]) > 5:
                user_summaries[uid] = user_summaries[uid][-5:]
    except:
        pass

def get_user_profile(uid):
    uid = str(uid)
    if uid not in user_profiles:
        user_profiles[uid] = {"name": None, "preferences": [], "facts": []}
    return user_profiles[uid]

def update_profile(uid, message_text):
    profile = get_user_profile(uid)
    text_lower = message_text.lower()
    if "my name is" in text_lower or "i am " in text_lower or "i'm " in text_lower:
        try:
            for phrase in ["my name is ", "i am ", "i'm "]:
                if phrase in text_lower:
                    name = message_text.split(phrase, 1)[1].split()[0].strip(".,!?")
                    if len(name) > 1:
                        profile["name"] = name.capitalize()
                        break
        except:
            pass
    if "i like" in text_lower or "i love" in text_lower:
        profile["preferences"].append(message_text[:100])
        profile["preferences"] = profile["preferences"][-10:]
    if any(w in text_lower for w in ["i work", "i study", "i live", "i am from", "i have"]):
        profile["facts"].append(message_text[:100])
        profile["facts"] = profile["facts"][-10:]

def build_context(uid):
    context = ""
    profile = get_user_profile(uid)
    if profile["name"]: context += f"User's name is {profile['name']}. "
    if profile["preferences"]: context += f"Likes: {', '.join(profile['preferences'][-3:])}. "
    if profile["facts"]: context += f"Facts: {', '.join(profile['facts'][-3:])}. "
    summaries = user_summaries.get(str(uid), [])
    if summaries: context += f"\nPast summary: {' '.join(summaries[-2:])}\n"
    history = get_history(uid)
    if len(history) > 1:
        context += "\nRecent:\n"
        for h in history[-10:]:
            context += f"{h['role']}: {h['content']}\n"
    return context

def is_vip(uid):
    return str(uid) in db["vip"] or uid == OWNER_ID

def is_banned(uid):
    return str(uid) in db["banned"]

def inc_stats(uid, username):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"username": username, "messages": 0, "joined": time.strftime("%Y-%m-%d"), "plan": "free"}
    db["users"][uid]["messages"] += 1
    if uid not in db["users"]: db["users"][uid]["username"] = username
    save_db()

def is_spamming(uid):
    now = time.time()
    last = user_last_message.get(uid, 0)
    user_last_message[uid] = now
    return now - last < 1.5

def get_lang(uid):
    return user_languages.get(uid, "en")

def validate_utr(utr):
    # UTR is 12 digit number
    return bool(re.match(r'^\d{12}$', utr.strip()))

# --------------------------------
# FLASK
# --------------------------------
@app.route('/')
def home():
    return "Nyra Bot is running! 🖤"

# --------------------------------
# START
# --------------------------------
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "❌ You are banned.")
        return
    if maintenance_mode and uid != OWNER_ID:
        bot.reply_to(message, "🔧 Bot is under maintenance. Try again later!")
        return

    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = args[1]
        if ref_id != str(uid):
            if ref_id not in db["referrals"]:
                db["referrals"][ref_id] = []
            if str(uid) not in db["referrals"][ref_id]:
                db["referrals"][ref_id].append(str(uid))
                save_db()
                bot.send_message(int(ref_id), f"🎉 Someone joined using your referral! You have {len(db['referrals'][ref_id])} referrals!")

    name = message.from_user.first_name
    username = message.from_user.username or name
    inc_stats(uid, username)

    profile = get_user_profile(uid)
    if not profile["name"]:
        profile["name"] = name

    vip_badge = "👑 " if is_vip(uid) else ""
    bot.reply_to(message, f"*smirks* Well, well... {vip_badge}{name} decided to show up. 😏\n\nI'm *Nyra* — sharp, bold, dangerously intelligent.\n\n*Commands:*\n💬 Type anything to chat\n🛒 /buy — Get API access\n📊 /stats — Your stats\n🧠 /memory — What I remember\n🗑 /clear — Clear memory\n🌐 /language — Switch language\nℹ️ /about — About Nyra\n\nWhat do you desire? 👀", parse_mode="Markdown")

# --------------------------------
# ABOUT
# --------------------------------
@bot.message_handler(commands=['about'])
def about(message):
    if is_banned(message.from_user.id): return
    bot.reply_to(message, f"""🖤 *About Nyra*

AI-powered chatbot with attitude — built by *Ace*.

🧠 Powered by Llama 3.3 70B
⚡ API: aceapis.vercel.app
👑 Owner: {OWNER_USERNAME}

*Available APIs:*
• Nyra — AI Chat
• allinfo — TG/Phone/IP/Email
• axinnum — Telegram user info
• axinscrapper — Web scraper

Use /buy to get API access!""", parse_mode="Markdown")

# --------------------------------
# PING
# --------------------------------
@bot.message_handler(commands=['ping'])
def ping(message):
    t = time.time()
    msg = bot.reply_to(message, "🏓 Pong!")
    bot.edit_message_text(f"🏓 Pong!\n⚡ {round((time.time()-t)*1000)}ms", message.chat.id, msg.message_id)

# --------------------------------
# LANGUAGE
# --------------------------------
@bot.message_handler(commands=['language'])
def language(message):
    if is_banned(message.from_user.id): return
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi")
    )
    bot.reply_to(message, "🌐 Choose language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def set_language(call):
    lang = call.data.split("_")[1]
    user_languages[call.from_user.id] = lang
    bot.answer_callback_query(call.id, "Language set!")
    bot.edit_message_text(f"✅ {'English 🇬🇧' if lang == 'en' else 'Hindi 🇮🇳'} set!", call.message.chat.id, call.message.message_id)

# --------------------------------
# STATS
# --------------------------------
@bot.message_handler(commands=['stats'])
def stats(message):
    uid = message.from_user.id
    if is_banned(uid): return
    data = db["users"].get(str(uid), {"messages": 0, "joined": "N/A", "plan": "free"})
    refs = len(db["referrals"].get(str(uid), []))
    ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
    vip_badge = "👑 VIP" if is_vip(uid) else "🆓 Free"
    bot.reply_to(message, f"📊 *Your Stats*\n\n💬 Messages: {data['messages']}\n🎫 Plan: {vip_badge}\n🧠 Memory: {len(get_history(uid))} msgs\n👥 Referrals: {refs}\n📅 Joined: {data.get('joined', 'N/A')}\n\n🔗 *Referral Link:*\n`{ref_link}`", parse_mode="Markdown")

# --------------------------------
# MEMORY
# --------------------------------
@bot.message_handler(commands=['memory'])
def show_memory(message):
    uid = message.from_user.id
    if is_banned(uid): return
    profile = get_user_profile(uid)
    summaries = user_summaries.get(str(uid), [])
    text = "🧠 *What Nyra remembers:*\n\n"
    text += f"👤 Name: {profile['name'] or 'Unknown'}\n"
    if profile['preferences']: text += f"❤️ Likes: {', '.join(profile['preferences'][-3:])}\n"
    if profile['facts']: text += f"📝 Facts: {', '.join(profile['facts'][-3:])}\n"
    text += f"\n💬 Recent msgs: {len(get_history(uid))}\n📚 Summaries: {len(summaries)}"
    if summaries: text += f"\n\n*Latest:*\n_{summaries[-1]}_"
    bot.reply_to(message, text, parse_mode="Markdown")

# --------------------------------
# CLEAR
# --------------------------------
@bot.message_handler(commands=['clear'])
def clear(message):
    user_histories[message.from_user.id] = []
    bot.reply_to(message, "🗑 Recent memory cleared!\n_I still remember your name and preferences_ 😏", parse_mode="Markdown")

# --------------------------------
# FUN COMMANDS
# --------------------------------
@bot.message_handler(commands=['roast'])
def roast(message):
    if is_banned(message.from_user.id): return
    target = message.text.replace('/roast', '').strip() or message.from_user.first_name
    res = requests.get(f"{NYRA_API}/savage roast for {target} in under 3 sentences?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"🔥 *Roasting {target}:*\n\n{res.get('reply', 'You are the roast 😂') if res.get('success') else 'You are the roast 😂'}", parse_mode="Markdown")

@bot.message_handler(commands=['compliment'])
def compliment(message):
    if is_banned(message.from_user.id): return
    name = get_user_profile(message.from_user.id).get("name") or message.from_user.first_name
    res = requests.get(f"{NYRA_API}/flirty compliment for {name} in 2 sentences?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, res.get("reply", f"You're stunning {name} 😏") if res.get("success") else f"You're stunning {name} 😏")

@bot.message_handler(commands=['advice'])
def advice(message):
    if is_banned(message.from_user.id): return
    res = requests.get(f"{NYRA_API}/one powerful life advice in 2 sentences?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"💡 *Advice:*\n\n{res.get('reply', 'Life is short 🖤') if res.get('success') else 'Life is short 🖤'}", parse_mode="Markdown")

@bot.message_handler(commands=['truth'])
def truth(message):
    if is_banned(message.from_user.id): return
    res = requests.get(f"{NYRA_API}/one fun truth or dare question, keep short?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"🎮 *Truth or Dare:*\n\n{res.get('reply', 'Truth: biggest secret? 😏') if res.get('success') else 'Truth: biggest secret? 😏'}", parse_mode="Markdown")

# --------------------------------
# BUY
# --------------------------------
@bot.message_handler(commands=['buy'])
def buy(message):
    if is_banned(message.from_user.id): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔹 Basic — ₹49/month", callback_data="buy_basic"))
    markup.add(InlineKeyboardButton("🔸 Pro — ₹99/month", callback_data="buy_pro"))
    markup.add(InlineKeyboardButton("👑 VIP — ₹199/month", callback_data="buy_vip"))
    markup.add(InlineKeyboardButton("💎 Lifetime — ₹999 one time", callback_data="buy_lifetime"))
    markup.add(InlineKeyboardButton("💬 Contact Owner", url="https://t.me/bubbleace007"))
    bot.reply_to(message, """🛒 *Purchase API Key*

• 🔹 *Basic* — ₹49/month
  50 req/day • Nyra + allinfo

• 🔸 *Pro* — ₹99/month
  200 req/day • Nyra + allinfo + axinnum

• 👑 *VIP* — ₹199/month
  999 req/day • All APIs + VIP badge + priority

• 💎 *Lifetime* — ₹999 one time
  9999 req/day • Everything forever

Select a plan 👇""", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def handle_buy(call):
    uid = call.from_user.id
    username = call.from_user.username or call.from_user.first_name
    plan_key = call.data.replace("buy_", "")
    plan = PLANS.get(plan_key, PLANS["basic"])
    db["pending"][str(uid)] = {"plan": plan_key, "username": username, "plan_name": plan["name"], "price": plan["price"]}
    save_db()
    try:
        with open("/app/qr.jpg", "rb") as qr:
            bot.send_photo(call.message.chat.id, qr,
                caption=f"💳 *Payment for {plan['name']} — ₹{plan['price']}*\n\n1️⃣ Scan QR and pay ₹{plan['price']}\n2️⃣ After payment, send your *UTR/Transaction ID*\n3️⃣ Use `/verify <UTR_NUMBER>`\n\n_UTR is the 12-digit transaction ID from your UPI app_\n\nContact: {OWNER_USERNAME}", parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, f"💳 *{plan['name']} — ₹{plan['price']}*\n\nPay via UPI and send UTR using `/verify <UTR_NUMBER>`\n\nContact: {OWNER_USERNAME}", parse_mode="Markdown")
    bot.send_message(OWNER_ID, f"🛒 *New Purchase Request!*\n\nUser: @{username} (`{uid}`)\nPlan: {plan['name']} — ₹{plan['price']}", parse_mode="Markdown")
    bot.answer_callback_query(call.id, "Payment details sent!")

# --------------------------------
# VERIFY UTR
# --------------------------------
@bot.message_handler(commands=['verify'])
def verify_utr(message):
    uid = message.from_user.id
    if is_banned(uid): return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/verify <UTR_NUMBER>`\n\n_UTR is the 12-digit transaction ID from your UPI app_", parse_mode="Markdown")
        return
    utr = parts[1].strip()
    if not validate_utr(utr):
        bot.reply_to(message, "❌ Invalid UTR! UTR must be exactly 12 digits.\n\nExample: `/verify 123456789012`", parse_mode="Markdown")
        return
    if utr in db["used_utrs"]:
        bot.reply_to(message, "❌ This UTR has already been used!")
        return
    if str(uid) not in db["pending"]:
        bot.reply_to(message, "❌ No pending purchase found!\nUse /buy first to select a plan.")
        return
    pending = db["pending"][str(uid)]
    # Store UTR with pending purchase
    db["pending"][str(uid)]["utr"] = utr
    save_db()
    bot.reply_to(message, f"✅ UTR received!\n\nUTR: `{utr}`\nPlan: {pending['plan_name']}\n\nYour purchase is under review. You'll receive your key within *1 hour*! 🖤", parse_mode="Markdown")
    bot.send_message(OWNER_ID, f"💳 *UTR Submitted!*\n\nUser: @{pending['username']} (`{uid}`)\nPlan: {pending['plan_name']} — ₹{pending['price']}\nUTR: `{utr}`\n\nUse `/approve {uid} <key>` to approve!", parse_mode="Markdown")

# --------------------------------
# SET MOOD (OWNER ONLY)
# --------------------------------
@bot.message_handler(commands=['mood'])
def set_mood(message):
    global owner_mood
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    parts = message.text.split(None, 1)
    if len(parts) == 1:
        moods_list = "\n".join([f"• `{k}`" for k in MOODS.keys()])
        bot.reply_to(message, f"🎭 *Moods:*\n\n{moods_list}\n\nCurrent: `{owner_mood}`\n\nUsage: `/mood savage`\nCustom: `/mood custom She is a pirate`", parse_mode="Markdown")
        return
    mood_input = parts[1].strip()
    if mood_input.startswith("custom "):
        MOODS["custom"] = mood_input.replace("custom ", "", 1)
        owner_mood = "custom"
        bot.reply_to(message, f"✅ Custom mood set! 🎭", parse_mode="Markdown")
    elif mood_input in MOODS:
        owner_mood = mood_input
        bot.reply_to(message, f"✅ Mood: `{mood_input}` 🎭", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ Unknown mood! Available: {', '.join(MOODS.keys())}")

# --------------------------------
# VIP SYSTEM
# --------------------------------
@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid not in db["vip"]:
            db["vip"].append(uid)
            save_db()
        bot.reply_to(message, f"👑 User `{uid}` is now VIP!", parse_mode="Markdown")
        bot.send_message(int(uid), "👑 *You are now a VIP user!*\n\nEnjoy exclusive access and special treatment from Nyra 😏", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Usage: /addvip <user_id>")

@bot.message_handler(commands=['removevip'])
def remove_vip(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid in db["vip"]:
            db["vip"].remove(uid)
            save_db()
        bot.reply_to(message, f"✅ VIP removed for `{uid}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Usage: /removevip <user_id>")

@bot.message_handler(commands=['listvip'])
def list_vip(message):
    if message.from_user.id != OWNER_ID: return
    if not db["vip"]:
        bot.reply_to(message, "No VIP users!")
        return
    bot.reply_to(message, f"👑 *VIP Users:*\n\n" + "\n".join([f"• `{uid}`" for uid in db["vip"]]), parse_mode="Markdown")

# --------------------------------
# ADMIN PANEL
# --------------------------------
@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Admin only!")
        return
    total_msgs = sum(u.get("messages", 0) for u in db["users"].values())
    markup = InlineKeyboardMarkup()
    markup.row(
    
