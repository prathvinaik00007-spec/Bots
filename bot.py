import telebot
import requests
import os
import threading
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NYRA_API = "https://aceapis.vercel.app/nyra"
NYRA_KEY = "aceuser"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Nyra Bot is running! 🖤"

@bot.message_handler(commands=['start'])
def start(message):
    name = message.from_user.first_name
    bot.reply_to(message, f"*smirks* Well, well... {name} decided to show up.\n\nI'm *Nyra* — your dangerously intelligent AI companion. Sharp wit,sexy personality, talks sexual things and I never back down. 😏\n\n*Commands:*\n💬 Just type anything to chat with me\n🛒 /buy — Purchase an API key\nℹ️ /help — How to use me\n\nSo... what do you desire? 👀", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(message, "*Nyra Help* 🖤\n\n💬 *Chat* — Just send any message\n🛒 /buy — Purchase API access\n📌 *API Endpoint:*\n`https://aceapis.vercel.app/nyra/<message>?key=YOURKEY`\n\n*API Plans:*\n• Basic — 50 req/day\n• Pro — 200 req/day\n• Unlimited — Contact owner\n\nMade by *Axin* ⚡", parse_mode="Markdown")

@bot.message_handler(commands=['buy'])
def buy(message):
    bot.reply_to(message, "🛒 *Purchase API Key*\n\n*Plans:*\n• 🔹 Basic — 50 req/day — ₹49/month\n• 🔸 Pro — 200 req/day — ₹99/month\n• 💎 Unlimited — Contact owner\n\n*Payment:*\nSend payment to UPI: `your_upi@upi`\n\nAfter payment send screenshot to @YourUsername with your plan name.\n\nYour key will be activated within *1 hour*! ⚡", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def chat(message):
    user_msg = message.text
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        res = requests.get(f"{NYRA_API}/{user_msg}?key={NYRA_KEY}", timeout=30).json()
        if res.get("success"):
            bot.reply_to(message, res.get("reply", "..."))
        else:
            bot.reply_to(message, "Hmm, something went wrong 😏 try again!")
    except:
        bot.reply_to(message, "I'm having a moment... try again 😏")

def run_bot():
    print("Nyra is online 🖤")
    bot.infinity_polling()

if __name__ == "__main__":
    thread = threading.Thread(target=run_bot)
    thread.daemon = True
    thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
