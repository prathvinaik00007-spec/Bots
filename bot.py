import telebot
import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8434464663:AAGo8JfUAjzoqaN6INDETXOOUZoPy7dPNXU")
NYRA_API = "https://aceapis.vercel.app/nyra"
NYRA_KEY = "aceuser"
OWNER_ID = None  # Set your Telegram user ID here

bot = telebot.TeleBot(BOT_TOKEN)

# --------------------------------
# START
# --------------------------------
@bot.message_handler(commands=['start'])
def start(message):
    name = message.from_user.first_name
    bot.reply_to(message, f"""*smirks* Well, well... {name} decided to show up. 

I'm *Nyra* — your dangerously intelligent AI companion. Sharp wit, bold personality, and I never back down. 😏

*Commands:*
💬 Just type anything to chat with me
🛒 /buy — Purchase an API key
ℹ️ /help — How to use me

So... what do you desire? 👀""", parse_mode="Markdown")

# --------------------------------
# HELP
# --------------------------------
@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(message, """*Nyra Help* 🖤

💬 *Chat* — Just send any message
🛒 /buy — Purchase API access
📌 *API Endpoint:*
`https://aceapis.vercel.app/nyra/<message>?key=YOURKEY`

*API Plans:*
• Basic — 50 req/day
• Pro — 200 req/day
• Unlimited — Contact owner

Made by *Axin* ⚡""", parse_mode="Markdown")

# --------------------------------
# BUY
# --------------------------------
@bot.message_handler(commands=['buy'])
def buy(message):
    bot.reply_to(message, """🛒 *Purchase API Key*

*Plans:*
• 🔹 Basic — 50 req/day — ₹49/month
• 🔸 Pro — 200 req/day — ₹99/month  
• 💎 Unlimited — Contact owner

*Payment:*
Send payment to UPI: `your_upi@upi`

After payment send screenshot to @YourUsername with your plan name.

Your key will be activated within *1 hour*! ⚡""", parse_mode="Markdown")

# --------------------------------
# CHAT WITH NYRA
# --------------------------------
@bot.message_handler(func=lambda message: True)
def chat(message):
    user_msg = message.text
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        res = requests.get(
            f"{NYRA_API}/{user_msg}?key={NYRA_KEY}",
            timeout=30
        ).json()
        
        if res.get("success"):
            reply = res.get("reply", "...")
            bot.reply_to(message, reply)
        else:
            bot.reply_to(message, "Hmm, something went wrong 😏 try again!")
    
    except Exception as e:
        bot.reply_to(message, "I'm having a moment... try again 😏")

# --------------------------------
# RUN
# --------------------------------
if __name__ == "__main__":
    print("Nyra is online 🖤")
    bot.infinity_polling()
  
