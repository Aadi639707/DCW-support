import os
import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai

# --- DUMMY SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is Alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

# --- CONFIGURATION ---
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454]

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

user_data = {}

SYSTEM_INSTRUCTION = "You are DCW SUPPORT BOT. Only help with complaints. Reply in the user's language. Ask for details and screenshots."

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("<b>Welcome to DCW Support!</b>\nHow can I help you? / Main aapki kaise madad kar sakta hoon?")

@dp.message_handler(content_types=['text', 'photo'])
async def handle_all(message: types.Message):
    uid = message.from_user.id
    if uid not in user_data: user_data[uid] = {"text": "", "photo": None}

    if message.photo:
        user_data[uid]["photo"] = message.photo[-1].file_id
        msg_text = "[Photo Sent]"
    else:
        user_data[uid]["text"] += f" {message.text}"
        msg_text = message.text

    response = ai_model.generate_content(f"{SYSTEM_INSTRUCTION}\nUser: {msg_text}")
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Submit ✅", callback_data="sub"),
        InlineKeyboardButton("Clear ❌", callback_data="clr")
    )
    await message.reply(response.text, reply_markup=kb)

@dp.callback_query_handler(text="sub")
async def sub(call: types.CallbackQuery):
    uid = call.from_user.id
    data = user_data.get(uid, {"text": "No details", "photo": None})
    
    report = f"🚨 <b>New Complaint!</b>\n👤 <b>User:</b> @{call.from_user.username}\n🆔 <b>ID:</b> {uid}\n📝 <b>Details:</b> {data['text']}"
    
    for admin in ADMIN_IDS:
        try:
            if data["photo"]: await bot.send_photo(admin, data["photo"], caption=report)
            else: await bot.send_message(admin, report)
        except: pass

    await call.message.edit_text("<b>Done! Sent to Admins.</b>")
    user_data.pop(uid, None)

@dp.callback_query_handler(text="clr")
async def clr(call: types.CallbackQuery):
    user_data.pop(call.from_user.id, None)
    await call.message.edit_text("Cleared. Type again.")

if __name__ == '__main__':
    # Start Dummy Server
    Thread(target=run).start()
    # Start Telegram Bot
    executor.start_polling(dp, skip_updates=True)
    
