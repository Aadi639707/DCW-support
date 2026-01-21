import os
import random
import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai

# --- RENDER WEB SERVER ---
app = Flask('')
@app.route('/')
def home(): return "DCW BOT IS ACTIVE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# AI ko samjhane ka tarika (System Instruction)
SYSTEM_PROMPT = (
    "You are the DCW Support Assistant. Your rule is: ALWAYS reply in the SAME LANGUAGE as the user. "
    "1. If they say /start, greet them and ask for the issue. "
    "2. If they explain an issue, acknowledge it politely and ask for a screenshot/proof or to type /skip. "
    "3. Be human-like, not robotic."
)

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    # AI se greeting mangna
    response = ai_model.generate_content(f"{SYSTEM_PROMPT}\nUser just started the bot with /start. Greet them in their likely language.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW AI Support</b> 🛠\n\n{response.text}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    # AI se response mangna (Language detect karke)
    response = ai_model.generate_content(f"{SYSTEM_PROMPT}\nUser reported: {message.text}. Acknowledge and ask for a screenshot or /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(response.text)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        # AI se puchna ki user ko kaise kahein ki photo bhejo ya skip karo
        response = ai_model.generate_content(f"{SYSTEM_PROMPT}\nUser sent something else. Tell them to send a photo or type /skip in their language.")
        await message.reply(response.text)
        return

    ticket_id = random.randint(111111, 999999)
    await state.update_data(ticket_id=ticket_id)
    
    # AI se summary mangna review ke liye
    summary_response = ai_model.generate_content(f"{SYSTEM_PROMPT}\nUser issue: {data['issue_text']}. Summarize it and ask them to click Submit to contact admins.")
    
    # Buttons (Inhe humesha same rakhenge taaki functional rahein)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        InlineKeyboardButton("Restart ❌", callback_data="restart")
    )
    
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket: #{ticket_id}</b>\n\n{summary_response.text}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def send_to_admins(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tid = data['ticket_id']
    report = (f"📩 <b>NEW CASE: #{tid}</b>\n━━━━━━━━━━━━━\n"
              f"👤 <b>User:</b> {call.from_user.full_name}\n"
              f"🆔 <b>ID:</b> <code>{call.from_user.id}</code>\n"
              f"📝 <b>Issue:</b> {data['issue_text']}\n━━━━━━━━━━━━━")

    for admin_id in ADMIN_IDS:
        try:
            if data.get('photo_id'): await bot.send_photo(admin_id, data['photo_id'], caption=report)
            else: await bot.send_message(admin_id, report)
        except: pass

    # AI se "Thank You" message mangna
    thanks = ai_model.generate_content(f"{SYSTEM_PROMPT}\nComplaint submitted. Tell the user it's sent to admins and give them their ticket #{tid}.")
    await call.message.edit_text(f"✅ {thanks.text}")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Restarted. Please describe your issue.")

if __name__ == '__main__':
    Thread(target=run).start()
    async def on_startup(dp): await bot.delete_webhook()
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
