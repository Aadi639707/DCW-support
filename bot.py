import os
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai

# Server for Render
app = Flask('')
@app.route('/')
def home(): return "DCW BOT IS RUNNING"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# CONFIG
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454]

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Conversation states
user_data = {}

SYSTEM_INSTRUCTION = (
    "You are the professional DCW Support AI. "
    "1. Start by greeting and asking for the issue. "
    "2. Once user explains, ask if they have any screenshot/proof. "
    "3. Only tell them to 'Click Submit below' after you have collected enough info. "
    "Be polite and reply in the user's language."
)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_data[message.from_user.id] = {"text": "", "photo": None}
    await message.reply("<b>Welcome to DCW Support</b> 🛠\n\nHow can I help you today? Please explain your problem in detail.")

@dp.message_handler(content_types=['text', 'photo'])
async def handle_flow(message: types.Message):
    uid = message.from_user.id
    if uid not in user_data:
        user_data[uid] = {"text": "", "photo": None}

    if message.photo:
        user_data[uid]["photo"] = message.photo[-1].file_id
        user_input = "[User sent a screenshot]"
    else:
        user_data[uid]["text"] += f"\n- {message.text}"
        user_input = message.text

    # AI decide karega kya bolna hai
    try:
        response = ai_model.generate_content(f"{SYSTEM_INSTRUCTION}\nUser says: {user_input}")
        bot_reply = response.text
    except:
        bot_reply = "I see. Please provide more details or a screenshot, then you can submit."

    # Buttons sirf tab dikhayenge jab user ne thodi baat kar li ho
    kb = InlineKeyboardMarkup(row_width=2)
    if len(user_data[uid]["text"]) > 10 or user_data[uid]["photo"]:
        kb.add(
            InlineKeyboardButton("Submit Complaint ✅", callback_data="sub"),
            InlineKeyboardButton("Clear/Edit ❌", callback_data="clr")
        )
    
    await message.reply(bot_reply, reply_markup=kb)

@dp.callback_query_handler(text="sub")
async def sub(call: types.CallbackQuery):
    uid = call.from_user.id
    data = user_data.get(uid)
    
    if not data or (not data["text"] and not data["photo"]):
        await call.answer("Please provide some details first!", show_alert=True)
        return

    report = (
        f"📩 <b>New Complaint Received</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {call.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📝 <b>Details:</b>\n{data['text']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    for admin in ADMIN_IDS:
        try:
            if data["photo"]:
                await bot.send_photo(admin, data["photo"], caption=report)
            else:
                await bot.send_message(admin, report)
        except: pass

    await call.message.edit_text("<b>Done! ✅ Your complaint has been submitted to DCW Admins.</b>")
    user_data.pop(uid, None)

@dp.callback_query_handler(text="clr")
async def clr(call: types.CallbackQuery):
    user_data[call.from_user.id] = {"text": "", "photo": None}
    await call.message.edit_text("Data cleared. Please explain your issue again.")

if __name__ == '__main__':
    Thread(target=run).start()
    executor.start_polling(dp, skip_updates=True)
    
