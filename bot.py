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

# --- CONFIG (Naya Token Updated) ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

# States (Steps)
class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await message.reply("<b>Welcome to DCW Support AI</b> 🛠\n\nMain aapki kaise madad kar sakta hoon? Kripya apni pareshani detail mein batayein.")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    
    # AI response to build trust
    prompt = f"User reported: {message.text}. Reply politely in their language and ask for a screenshot/proof. If they don't have one, tell them to type /skip."
    response = ai_model.generate_content(prompt)
    
    await ComplaintState.waiting_for_photo.set()
    await message.reply(response.text)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        await message.reply("Kripya ek screenshot bhejein ya aage badhne ke liye /skip type karein.")
        return

    data = await state.get_data()
    ticket_id = random.randint(100000, 999999)
    await state.update_data(ticket_id=ticket_id)
    
    # AI summary for the final step
    summary_prompt = f"Create a short professional summary of this complaint: {data['issue_text']}. Ask the user to click 'Submit' if everything is correct."
    summary = ai_model.generate_content(summary_prompt)
    
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        InlineKeyboardButton("Restart / Edit ❌", callback_data="restart")
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

    await call.message.edit_text(f"<b>Done! ✅ Aapki complaint (Ticket #{tid}) Admins ko bhej di gayi hai.</b>")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Theek hai, shuru se shuru karte hain. Apni pareshani likhiye.")

if __name__ == '__main__':
    Thread(target=run).start()
    print("DCW Bot is starting with new token...")
    executor.start_polling(dp, skip_updates=True)
    
