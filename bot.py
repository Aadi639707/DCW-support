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

# --- RENDER PORT FIX ---
app = Flask('')
@app.route('/')
def home(): return "DCW BOT IS LIVE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG (Updated Admin List) ---
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
# Purane + Naye Admins
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

SYSTEM_INSTRUCTION = (
    "You are DCW Support AI. Be professional. "
    "Step 1: Ask for the issue. Step 2: Ask for screenshot or type /skip. "
    "Step 3: Show summary and ask to Submit. Reply in user's language."
)

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await message.reply("<b>Welcome to DCW Support AI</b> 🛠\n\nPlease describe your problem in detail.")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    response = ai_model.generate_content(f"{SYSTEM_INSTRUCTION}\nUser issue: {message.text}. Ask for proof/screenshot or /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(response.text)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        await message.reply("Please send a screenshot or type /skip.")
        return

    data = await state.get_data()
    ticket_id = random.randint(10000, 99999)
    await state.update_data(ticket_id=ticket_id)
    
    summary = ai_model.generate_content(f"Summarize this for review: {data['issue_text']}. Tell user to click Submit.")
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Submit ✅", callback_data="final_sub"),
        InlineKeyboardButton("Restart ❌", callback_data="restart")
    )
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{ticket_id}</b>\n\n{summary.text}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def send_to_admins(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id
    tid = data['ticket_id']
    
    report = (
        f"📩 <b>NEW COMPLAINT: #{tid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {call.from_user.full_name}\n"
        f"🆔 <b>User ID:</b> <code>{uid}</code>\n"
        f"📝 <b>Issue:</b> {data['issue_text']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    for admin_id in ADMIN_IDS:
        try:
            if data.get('photo_id'):
                await bot.send_photo(admin_id, data['photo_id'], caption=report)
            else:
                await bot.send_message(admin_id, report)
        except: pass

    await call.message.edit_text(f"<b>Done! ✅ Your complaint (Ticket #{tid}) has been sent to all 5 Admins.</b>")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Restarting... Please describe your issue.")

if __name__ == '__main__':
    Thread(target=run).start()
    executor.start_polling(dp, skip_updates=True)
    
