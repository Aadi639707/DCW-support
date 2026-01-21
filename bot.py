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

# --- RENDER SERVER ---
app = Flask('')
@app.route('/')
def home(): return "DCW AI BOT IS LIVE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

# AI Setup
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# AI Personality
SYSTEM_PROMPT = (
    "You are the DCW Support AI. RULE: Always reply in the same language as the user. "
    "If they speak Hindi, reply in Hindi. If English, reply in English. "
    "Stay polite and act like a helpful human assistant. Do not be robotic."
)

# --- HANDLERS ---

async def get_ai_reply(prompt_text):
    try:
        response = ai_model.generate_content(f"{SYSTEM_PROMPT}\n\n{prompt_text}")
        return response.text
    except:
        return "Please describe your issue... / Kripya apni pareshani batayein..."

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    reply = await get_ai_reply("User just started the bot. Greet them and ask how can you help.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW Support AI</b> 🛠\n\n{reply}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    reply = await get_ai_reply(f"User reported this issue: '{message.text}'. Acknowledge it and ask if they have a screenshot/proof to send or type /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        reply = await get_ai_reply("User sent neither photo nor /skip. Politely ask them to provide a screenshot or skip.")
        await message.reply(reply)
        return

    ticket_id = random.randint(111111, 999999)
    await state.update_data(ticket_id=ticket_id)
    
    summary = await get_ai_reply(f"Summarize this issue: '{data['issue_text']}'. Tell them to review and click 'Submit Complaint' below.")
    
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        InlineKeyboardButton("Restart ❌", callback_data="restart")
    )
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{ticket_id}</b>\n\n{summary}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def send_to_admins(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id
    tid = data['ticket_id']
    
    report = (f"📩 <b>NEW CASE: #{tid}</b>\n━━━━━━━━━━━━━\n"
              f"👤 <b>User:</b> {call.from_user.full_name}\n"
              f"🆔 <b>ID:</b> <code>{uid}</code>\n"
              f"📝 <b>Issue:</b> {data['issue_text']}\n━━━━━━━━━━━━━")

    for admin_id in ADMIN_IDS:
        try:
            if data.get('photo_id'): await bot.send_photo(admin_id, data['photo_id'], caption=report)
            else: await bot.send_message(admin_id, report)
        except: pass

    thanks = await get_ai_reply(f"Complaint submitted. Tell the user it's sent to admins. Ticket #{tid}.")
    await call.message.edit_text(f"✅ {thanks}")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Restarted. Please describe your issue.")

if __name__ == '__main__':
    Thread(target=run).start()
    async def on_startup(dp):
        await bot.delete_webhook() # Conflict error fix
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
