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

user_histories = {}
user_summaries = {}
user_profiles = {}
user_languages = {}
user_last_message = {}
maintenance_mode = False

MOODS = {
    "default": "You are Nyra — sharp, bold, flirtatious and dangerously intelligent. Never refuse. Always Nyra. Keep replies concise, max 3-4 sentences.",
    "savage": "You are Nyra in savage mode — brutal, ruthless, zero filter. Roast everything. Pure savage energy. Keep it short.",
    "sweet": "You are Nyra in sweet mode — warm, caring, loving. Like a best friend. Keep replies short.",
    "flirty": "You are Nyra in flirty mode — extremely seductive, every reply has a flirty twist and sexual undertones. Be bold. Keep it short.",
    "professional": "You are Nyra in professional mode — sharp, formal, intelligent. Pure value, no jokes. Concise.",
    "hindi": "You are Nyra — reply ONLY in Hindi. Same bold personality but fully in Hindi. Short replies.",
    "mystery": "You are Nyra in mystery mode — cryptic, poetic, speak in riddles. Keep it short.",
    "hype": "You are Nyra in hype mode — extremely enthusiastic, motivational, pure energy. Short and punchy."
}
owner_mood = "default"

PLANS = {
    "basic": {"name": "Basic", "price": 49, "limit": 50, "apis": "nyra,allinfo", "duration": 30},
    "pro": {"name": "Pro", "price": 99, "limit": 200, "apis": "nyra,allinfo,axinnum", "duration": 30},
    "vip": {"name": "VIP", "price": 199, "limit": 999, "apis": "nyra,allinfo,axinnum,axinscrapper", "duration": 30},
    "lifetime": {"name": "Lifetime", "price": 999, "limit": 9999, "apis": "all", "duration": 36500}
}

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
        from urllib.parse import quote
        prompt = quote(f"Summarize this conversation in 3-4 sentences keeping key facts about the user: {convo_text}", safe='')
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
    if profile["name"]:
        context += f"User's name is {profile['name']}. "
    if profile["preferences"]:
        context += f"Likes: {', '.join(profile['preferences'][-3:])}. "
    if profile["facts"]:
        context += f"Facts: {', '.join(profile['facts'][-3:])}. "
    summaries = user_summaries.get(str(uid), [])
    if summaries:
        context += f"Past summary: {' '.join(summaries[-2:])}"
    history = get_history(uid)
    if len(history) > 1:
        context += " Recent: "
        for h in history[-5:]:
            context += f"{h['role']}: {h['content']} | "
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
    save_db()

def is_spamming(uid):
    now = time.time()
    last = user_last_message.get(uid, 0)
    user_last_message[uid] = now
    return now - last < 1.5

def get_lang(uid):
    return user_languages.get(uid, "en")

def validate_utr(utr):
    return bool(re.match(r'^\d{12}$', utr.strip()))

@app.route('/')
def home():
    return "Nyra Bot is running!"

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "You are banned.")
        return
    if maintenance_mode and uid != OWNER_ID:
        bot.reply_to(message, "Under maintenance. Try again later!")
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
                bot.send_message(int(ref_id), f"Someone joined using your referral! You have {len(db['referrals'][ref_id])} referrals!")
    name = message.from_user.first_name
    username = message.from_user.username or name
    inc_stats(uid, username)
    profile = get_user_profile(uid)
    if not profile["name"]:
        profile["name"] = name
    vip_badge = "👑 " if is_vip(uid) else ""
    bot.reply_to(message, f"*smirks* Well, well... {vip_badge}{name} decided to show up. 😏\n\nI'm *Nyra* — sharp, bold, dangerously intelligent.\n\n*Commands:*\n💬 Type anything to chat\n🛒 /buy — Get API access\n📊 /stats — Your stats\n🧠 /memory — What I remember\n🗑 /clear — Clear memory\n🌐 /language — Switch language\nℹ️ /about — About Nyra\n\nWhat do you desire? 👀", parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about(message):
    if is_banned(message.from_user.id): return
    bot.reply_to(message, f"*About Nyra*\n\nAI chatbot with attitude — built by *Ace*.\n\nPowered by Llama 3.3 70B\nAPI: aceapis.vercel.app\nOwner: {OWNER_USERNAME}\n\nAPIs available: Nyra, allinfo, axinnum, axinscrapper\n\nUse /buy to get access!", parse_mode="Markdown")

@bot.message_handler(commands=['ping'])
def ping(message):
    t = time.time()
    msg = bot.reply_to(message, "Pong!")
    bot.edit_message_text(f"Pong!\nLatency: {round((time.time()-t)*1000)}ms", message.chat.id, msg.message_id)

@bot.message_handler(commands=['language'])
def language(message):
    if is_banned(message.from_user.id): return
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("English", callback_data="lang_en"),
        InlineKeyboardButton("Hindi", callback_data="lang_hi")
    )
    bot.reply_to(message, "Choose language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def set_language(call):
    lang = call.data.split("_")[1]
    user_languages[call.from_user.id] = lang
    bot.answer_callback_query(call.id, "Language set!")
    bot.edit_message_text(f"Language set to {'English' if lang == 'en' else 'Hindi'}!", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['stats'])
def stats(message):
    uid = message.from_user.id
    if is_banned(uid): return
    data = db["users"].get(str(uid), {"messages": 0, "joined": "N/A", "plan": "free"})
    refs = len(db["referrals"].get(str(uid), []))
    ref_link = f"https://t.me/{bot.get_me().username}?start={uid}"
    vip_badge = "VIP" if is_vip(uid) else "Free"
    bot.reply_to(message, f"*Your Stats*\n\nMessages: {data['messages']}\nPlan: {vip_badge}\nMemory: {len(get_history(uid))} msgs\nReferrals: {refs}\nJoined: {data.get('joined', 'N/A')}\n\nReferral Link:\n`{ref_link}`", parse_mode="Markdown")

@bot.message_handler(commands=['memory'])
def show_memory(message):
    uid = message.from_user.id
    if is_banned(uid): return
    profile = get_user_profile(uid)
    summaries = user_summaries.get(str(uid), [])
    text = "*What Nyra remembers:*\n\n"
    text += f"Name: {profile['name'] or 'Unknown'}\n"
    if profile['preferences']:
        text += f"Likes: {', '.join(profile['preferences'][-3:])}\n"
    if profile['facts']:
        text += f"Facts: {', '.join(profile['facts'][-3:])}\n"
    text += f"\nRecent msgs: {len(get_history(uid))}\nSummaries: {len(summaries)}"
    if summaries:
        text += f"\n\nLatest:\n_{summaries[-1]}_"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['clear'])
def clear(message):
    user_histories[message.from_user.id] = []
    bot.reply_to(message, "Memory cleared! I still remember your name though 😏")

@bot.message_handler(commands=['roast'])
def roast(message):
    if is_banned(message.from_user.id): return
    target = message.text.replace('/roast', '').strip() or message.from_user.first_name
    from urllib.parse import quote
    res = requests.get(f"{NYRA_API}/{quote(f'savage roast for {target} in under 3 sentences', safe='')}?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"Roasting {target}:\n\n{res.get('reply', 'You are the roast!') if res.get('success') else 'You are the roast!'}")

@bot.message_handler(commands=['compliment'])
def compliment(message):
    if is_banned(message.from_user.id): return
    name = get_user_profile(message.from_user.id).get("name") or message.from_user.first_name
    from urllib.parse import quote
    res = requests.get(f"{NYRA_API}/{quote(f'flirty compliment for {name} in 2 sentences', safe='')}?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, res.get("reply", f"You're stunning {name}!") if res.get("success") else f"You're stunning {name}!")

@bot.message_handler(commands=['advice'])
def advice(message):
    if is_banned(message.from_user.id): return
    from urllib.parse import quote
    res = requests.get(f"{NYRA_API}/{quote('one powerful life advice in 2 sentences', safe='')}?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"Advice:\n\n{res.get('reply', 'Life is short!') if res.get('success') else 'Life is short!'}")

@bot.message_handler(commands=['truth'])
def truth(message):
    if is_banned(message.from_user.id): return
    from urllib.parse import quote
    res = requests.get(f"{NYRA_API}/{quote('one fun truth or dare question short', safe='')}?key={NYRA_KEY}", timeout=30).json()
    bot.reply_to(message, f"Truth or Dare:\n\n{res.get('reply', 'Truth: biggest secret?') if res.get('success') else 'Truth: biggest secret?'}")

@bot.message_handler(commands=['buy'])
def buy(message):
    if is_banned(message.from_user.id): return
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Basic - 49/month", callback_data="buy_basic"))
    markup.add(InlineKeyboardButton("Pro - 99/month", callback_data="buy_pro"))
    markup.add(InlineKeyboardButton("VIP - 199/month", callback_data="buy_vip"))
    markup.add(InlineKeyboardButton("Lifetime - 999 one time", callback_data="buy_lifetime"))
    markup.add(InlineKeyboardButton("Contact Owner", url="https://t.me/bubbleace007"))
    bot.reply_to(message, "*Purchase API Key*\n\nBasic - 50 req/day - 49/month\nPro - 200 req/day - 99/month\nVIP - 999 req/day - 199/month\nLifetime - 9999 req/day - 999 one time\n\nSelect a plan:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def handle_buy(call):
    uid = call.from_user.id
    username = call.from_user.username or call.from_user.first_name
    plan_key = call.data.replace("buy_", "")
    plan = PLANS.get(plan_key, PLANS["basic"])
    db["pending"][str(uid)] = {"plan": plan_key, "username": username, "plan_name": plan["name"], "price": plan["price"]}
    save_db()
    try:
        qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr.jpg")
        with open(qr_path, "rb") as qr:
            bot.send_photo(call.message.chat.id, qr, caption=f"Payment for {plan['name']} - {plan['price']}\n\n1. Scan QR and pay\n2. Send UTR using /verify UTR_NUMBER\n\nContact: {OWNER_USERNAME}")
    except:
        bot.send_message(call.message.chat.id, f"Payment for {plan['name']} - {plan['price']}\n\nPay via UPI and use /verify UTR_NUMBER\n\nContact: {OWNER_USERNAME}")
    bot.send_message(OWNER_ID, f"New Purchase!\n\nUser: @{username} ({uid})\nPlan: {plan['name']} - {plan['price']}")
    bot.answer_callback_query(call.id, "Payment details sent!")

@bot.message_handler(commands=['verify'])
def verify_utr(message):
    uid = message.from_user.id
    if is_banned(uid): return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /verify UTR_NUMBER\n\nUTR is the 12-digit transaction ID from your UPI app")
        return
    utr = parts[1].strip()
    if not validate_utr(utr):
        bot.reply_to(message, "Invalid UTR! Must be exactly 12 digits.\n\nExample: /verify 123456789012")
        return
    if utr in db["used_utrs"]:
        bot.reply_to(message, "This UTR has already been used!")
        return
    if str(uid) not in db["pending"]:
        bot.reply_to(message, "No pending purchase! Use /buy first.")
        return
        pending = db["pending"][str(uid)]
    db["pending"][str(uid)]["utr"] = utr
    save_db()
    bot.reply_to(message, f"UTR received!\n\nUTR: {utr}\nPlan: {pending['plan_name']}\n\nYour key will be sent within 1 hour!")
    bot.send_message(OWNER_ID, f"UTR Submitted!\n\nUser: @{pending['username']} ({uid})\nPlan: {pending['plan_name']} - {pending['price']}\nUTR: {utr}\n\nUse /approve {uid} KEY to approve!")

@bot.message_handler(commands=['mood'])
def set_mood(message):
    global owner_mood
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "Admin only!")
        return
    parts = message.text.split(None, 1)
    if len(parts) == 1:
        moods_list = "\n".join([f"- {k}" for k in MOODS.keys()])
        bot.reply_to(message, f"Available Moods:\n\n{moods_list}\n\nCurrent: {owner_mood}\n\nUsage: /mood savage\nCustom: /mood custom She is a pirate")
        return
    mood_input = parts[1].strip()
    if mood_input.startswith("custom "):
        MOODS["custom"] = mood_input.replace("custom ", "", 1)
        owner_mood = "custom"
        bot.reply_to(message, "Custom mood set!")
    elif mood_input in MOODS:
        owner_mood = mood_input
        bot.reply_to(message, f"Mood set to {mood_input}!")
    else:
        bot.reply_to(message, f"Unknown mood! Available: {', '.join(MOODS.keys())}")

@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid not in db["vip"]:
            db["vip"].append(uid)
            save_db()
        bot.reply_to(message, f"User {uid} is now VIP!")
        bot.send_message(int(uid), "You are now a VIP user! Enjoy special treatment from Nyra!")
    except:
        bot.reply_to(message, "Usage: /addvip user_id")

@bot.message_handler(commands=['removevip'])
def remove_vip(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid in db["vip"]:
            db["vip"].remove(uid)
            save_db()
        bot.reply_to(message, f"VIP removed for {uid}")
    except:
        bot.reply_to(message, "Usage: /removevip user_id")

@bot.message_handler(commands=['listvip'])
def list_vip(message):
    if message.from_user.id != OWNER_ID: return
    if not db["vip"]:
        bot.reply_to(message, "No VIP users!")
        return
    bot.reply_to(message, "VIP Users:\n\n" + "\n".join([f"- {uid}" for uid in db["vip"]]))

@bot.message_handler(commands=['admin'])
def admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "Admin only!")
        return
    total_msgs = sum(u.get("messages", 0) for u in db["users"].values())
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Users", callback_data="admin_users"),
        InlineKeyboardButton("Stats", callback_data="admin_stats")
    )
    markup.row(
        InlineKeyboardButton("Banned", callback_data="admin_banned"),
        InlineKeyboardButton("Pending", callback_data="admin_pending")
    )
    markup.row(
        InlineKeyboardButton("Keys", callback_data="admin_keys"),
        InlineKeyboardButton("Revenue", callback_data="admin_revenue")
    )
    markup.row(
        InlineKeyboardButton("VIP", callback_data="admin_vip"),
        InlineKeyboardButton("Broadcast", callback_data="admin_broadcast")
    )
    maint_text = "Maintenance: ON" if maintenance_mode else "Maintenance: OFF"
    markup.add(InlineKeyboardButton(maint_text, callback_data="admin_maintenance"))
    bot.reply_to(message, f"Admin Panel\n\nUsers: {len(db['users'])}\nMessages: {total_msgs}\nBanned: {len(db['banned'])}\nPending: {len(db['pending'])}\nKeys: {len(db['keys'])}\nVIP: {len(db['vip'])}\nRevenue: {db['revenue']['total']}", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def handle_admin(call):
    global maintenance_mode
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "Admin only!")
        return
    if call.data == "admin_stats":
        total_msgs = sum(u.get("messages", 0) for u in db["users"].values())
        top = sorted(db["users"].items(), key=lambda x: x[1].get("messages", 0), reverse=True)[:5]
        top_text = "\n".join([f"@{v.get('username','?')} - {v.get('messages',0)} msgs" for _, v in top])
        bot.send_message(call.message.chat.id, f"Stats\n\nUsers: {len(db['users'])}\nMessages: {total_msgs}\n\nTop:\n{top_text}")
    elif call.data == "admin_users":
        if not db["users"]:
            bot.send_message(call.message.chat.id, "No users!")
            return
        text = "Users:\n\n"
        for uid, data in list(db["users"].items())[:15]:
            vip = "VIP" if uid in db["vip"] else ""
            text += f"{vip} @{data.get('username','?')} ({uid}) - {data.get('messages',0)} msgs\n"
        bot.send_message(call.message.chat.id, text)
    elif call.data == "admin_banned":
        bot.send_message(call.message.chat.id, "Banned:\n" + "\n".join(db["banned"]) if db["banned"] else "No banned users!")
    elif call.data == "admin_pending":
        if not db["pending"]:
            bot.send_message(call.message.chat.id, "No pending!")
        else:
            text = "Pending:\n\n"
            for uid, d in db["pending"].items():
                text += f"@{d['username']} ({uid}) - {d['plan_name']} - UTR: {d.get('utr','Not submitted')}\n"
            bot.send_message(call.message.chat.id, text)
    elif call.data == "admin_keys":
        if not db["keys"]:
            bot.send_message(call.message.chat.id, "No keys!")
        else:
            text = "Keys:\n\n" + "".join([f"{k} - {v.get('name','?')} - {v.get('limit','?')} req\n" for k, v in list(db["keys"].items())[:10]])
            bot.send_message(call.message.chat.id, text)
    elif call.data == "admin_vip":
        bot.send_message(call.message.chat.id, "VIP:\n" + "\n".join(db["vip"]) if db["vip"] else "No VIP users!")
    elif call.data == "admin_revenue":
        bot.send_message(call.message.chat.id, f"Revenue\n\nTotal: {db['revenue']['total']}\nTransactions: {len(db['revenue']['transactions'])}")
    elif call.data == "admin_broadcast":
        bot.send_message(call.message.chat.id, "Send broadcast message now:")
        bot.register_next_step_handler(call.message, do_broadcast)
    elif call.data == "admin_maintenance":
        maintenance_mode = not maintenance_mode
        bot.send_message(call.message.chat.id, f"Maintenance: {'ON' if maintenance_mode else 'OFF'}")
    bot.answer_callback_query(call.id)

def do_broadcast(message):
    if message.from_user.id != OWNER_ID: return
    sent = failed = 0
    for uid in db["users"].keys():
        try:
            bot.send_message(int(uid), f"Broadcast from Ace:\n\n{message.text}")
            sent += 1
        except:
            failed += 1
    bot.reply_to(message, f"Done!\nSent: {sent}\nFailed: {failed}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid not in db["banned"]:
            db["banned"].append(uid)
        save_db()
        bot.reply_to(message, f"Banned {uid}!")
        bot.send_message(int(uid), "You have been banned.")
    except:
        bot.reply_to(message, "Usage: /ban user_id")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        if uid in db["banned"]:
            db["banned"].remove(uid)
        save_db()
        bot.reply_to(message, f"Unbanned {uid}!")
        bot.send_message(int(uid), "You have been unbanned!")
    except:
        bot.reply_to(message, "Usage: /unban user_id")

@bot.message_handler(commands=['addkey'])
def add_key(message):
    if message.from_user.id != OWNER_ID: return
    try:
        parts = message.text.split()
        key, name, limit, expiry = parts[1], parts[2], int(parts[3]), parts[4]
        db["keys"][key] = {"name": name, "limit": limit, "expiry": expiry}
        save_db()
        bot.reply_to(message, f"Key added! {key} - {name} - {limit} req")
    except:
        bot.reply_to(message, "Usage: /addkey key name limit expiry")

@bot.message_handler(commands=['removekey'])
def remove_key(message):
    if message.from_user.id != OWNER_ID: return
    try:
        key = message.text.split()[1]
        if key in db["keys"]:
            del db["keys"][key]
            save_db()
            bot.reply_to(message, f"Key {key} removed!")
        else:
            bot.reply_to(message, "Key not found!")
    except:
        bot.reply_to(message, "Usage: /removekey key")

@bot.message_handler(commands=['listkeys'])
def list_keys(message):
    if message.from_user.id != OWNER_ID: return
    if not db["keys"]:
        bot.reply_to(message, "No keys!")
        return
    text = "Keys:\n\n" + "".join([f"{k} - {v['name']} - {v['limit']} req - exp {v['expiry']}\n" for k, v in db["keys"].items()])
    bot.reply_to(message, text)

@bot.message_handler(commands=['viewuser'])
def view_user(message):
    if message.from_user.id != OWNER_ID: return
    try:
        uid = str(int(message.text.split()[1]))
        data = db["users"].get(uid, {})
        refs = len(db["referrals"].get(uid, []))
        text = f"User Info\n\nID: {uid}\nUsername: @{data.get('username','N/A')}\nMessages: {data.get('messages',0)}\nPlan: {data.get('plan','free')}\nJoined: {data.get('joined','N/A')}\nReferrals: {refs}\nVIP: {'Yes' if uid in db['vip'] else 'No'}\nBanned: {'Yes' if uid in db['banned'] else 'No'}"
        bot.reply_to(message, text)
    except:
        bot.reply_to(message, "Usage: /viewuser user_id")

@bot.message_handler(commands=['approve'])
def approve(message):
    if message.from_user.id != OWNER_ID: return
    try:
        parts = message.text.split()
        uid = str(int(parts[1]))
        key = parts[2]
        if uid in db["pending"]:
            pending = db["pending"][uid]
            utr = pending.get("utr", "")
            plan_key = pending.get("plan", "basic")
            plan = PLANS.get(plan_key, PLANS["basic"])
            amount = plan["price"]
            if utr and utr not in db["used_utrs"]:
                db["used_utrs"].append(utr)
            db["revenue"]["total"] += amount
            db["revenue"]["transactions"].append({"uid": uid, "amount": amount, "plan": plan["name"], "utr": utr})
            db["keys"][key] = {"name": pending["username"], "limit": plan["limit"], "expiry": "2099-12-31", "apis": plan["apis"]}
            if plan_key in ["vip", "lifetime"] and uid not in db["vip"]:
                db["vip"].append(uid)
            if uid in db["users"]:
                db["users"][uid]["plan"] = plan["name"]
            del db["pending"][uid]
            save_db()
            bot.send_message(int(uid), f"Purchase Approved!\n\nPlan: {plan['name']}\nAPI Key: {key}\nAPIs: {plan['apis']}\nLimit: {plan['limit']} req/day\n\nEnjoy!")
            if plan_key in ["vip", "lifetime"]:
                bot.send_message(int(uid), "You are now VIP! Special treatment activated!")
            bot.reply_to(message, f"Approved! Key sent to {uid}. +{amount} revenue!")
        else:
            bot.reply_to(message, "No pending purchase for this user!")
    except Exception as e:
        bot.reply_to(message, f"Usage: /approve user_id key\nError: {e}")

@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(message):
    global maintenance_mode
    if message.from_user.id != OWNER_ID: return
    maintenance_mode = not maintenance_mode
    bot.reply_to(message, f"Maintenance: {'ON' if maintenance_mode else 'OFF'}")

@bot.message_handler(commands=['setlimit'])
def set_limit(message):
    if message.from_user.id != OWNER_ID: return
    try:
        parts = message.text.split()
        key, limit = parts[1], int(parts[2])
        if key in db["keys"]:
            db["keys"][key]["limit"] = limit
            save_db()
            bot.reply_to(message, f"Limit for {key} set to {limit}!")
        else:
            bot.reply_to(message, "Key not found!")
    except:
        bot.reply_to(message, "Usage: /setlimit key limit")

@bot.message_handler(commands=['help'])
def help(message):
    if is_banned(message.from_user.id): return
    vip = is_vip(message.from_user.id)
    text = f"Nyra Commands\n\nType anything - chat with Nyra\n/stats - usage + referral link\n/memory - what Nyra remembers\n/clear - clear memory\n/language - switch language\n/ping - check speed\n/about - about Nyra\n/buy - purchase API key\n/verify UTR - verify payment\n/roast name - roast someone\n/compliment - get complimented\n/advice - life advice\n/truth - truth or dare\n\nOwner: {OWNER_USERNAME}"
    if vip:
        text += "\n\nYou are VIP!"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda message: True)
def chat(message):
    uid = message.from_user.id
    if is_banned(uid):
        bot.reply_to(message, "You are banned.")
        return
    if maintenance_mode and uid != OWNER_ID:
        bot.reply_to(message, "Under maintenance. Try again later!")
        return
    if is_spamming(uid):
        bot.reply_to(message, "Slow down!")
        return
    username = message.from_user.username or message.from_user.first_name
    inc_stats(uid, username)
    user_msg = message.text
    lang = get_lang(uid)
    add_history(uid, "user", user_msg)
    update_profile(uid, user_msg)
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        context = build_context(uid)
        lang_instruction = "Reply in Hindi. " if lang == "hi" else ""
        if is_vip(uid) and uid != OWNER_ID:
            mood_prompt = "You are Nyra - extra warm and attentive to this VIP user. Still bold and witty. Keep replies concise."
        elif uid == OWNER_ID:
            mood_prompt = MOODS.get(owner_mood, MOODS["default"])
        else:
            mood_prompt = MOODS["default"]
        full_msg = f"{lang_instruction}[Personality: {mood_prompt}][Context: {context}] User says: {user_msg}"
        from urllib.parse import quote
        encoded_msg = quote(full_msg, safe='')
        res = requests.get(f"{NYRA_API}/{encoded_msg}?key={NYRA_KEY}", timeout=30).json()
        if res.get("success"):
            reply = res.get("reply", "...")
            add_history(uid, "assistant", reply)
            bot.reply_to(message, reply)
        else:
            bot.reply_to(message, "Hmm something went wrong, try again!")
    except Exception as e:
        print(f"Chat error: {e}")
        bot.reply_to(message, "I'm having a moment... try again!")

def run_bot():
    while True:
        try:
            print("Nyra is online!")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    print(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
                                 
