import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai
import os

# --- CONFIGURATION ---
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454]

# AI Setup
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

user_data = {}
SYSTEM_INSTRUCTION = "You are DCW SUPPORT BOT. Help with complaints only. Talk in user's language."

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("<b>DCW Support Bot Online!</b>\nHow can I help you?")

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

    try:
        response = ai_model.generate_content(f"{SYSTEM_INSTRUCTION}\nUser: {msg_text}")
        reply = response.text
    except:
        reply = "Please describe your issue and click Submit."

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Submit ✅", callback_data="sub"),
        InlineKeyboardButton("Clear ❌", callback_data="clr")
    )
    await message.reply(reply, reply_markup=kb)

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
    await call.message.edit_text("Cleared. Write again.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
