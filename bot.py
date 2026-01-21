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
# 5 Admins List
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

# Gemini Setup (Fixed Model Name)
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await message.reply("<b>DCW AI Support Assistant</b> 🛠\n\nHello! Main aapki kaise madad kar sakta hoon? Kripya apni problem detail mein batayein.")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    
    # AI response
    try:
        prompt = f"User reported: {message.text}. Reply politely in their language and ask for a screenshot/proof. If they don't have one, tell them to type /skip."
        response = ai_model.generate_content(prompt)
        bot_reply = response.text
    except:
        bot_reply = "Theek hai, main samajh gaya. Kya aapke paas koi screenshot hai? (Bhejein ya /skip likhein)"
    
    await ComplaintState.waiting_for_photo.set()
    await message.reply(bot_reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        await message.reply("Kripya ek photo bhejein ya aage badhne ke liye /skip likhein.")
        return

    data = await state.get_data()
    ticket_id = random.randint(111111, 999999)
    await state.update_data(ticket_id=ticket_id)
    
    # AI Summary
    try:
        summary_prompt = f"Summarize this complaint: {data['issue_text']}. Ask user to check and click Submit."
        summary = ai_model.generate_content(summary_prompt)
        summary_text = summary.text
    except:
        summary_text = f"Aapki complaint: {data['issue_text'][:50]}..."

    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        InlineKeyboardButton("Edit / Restart ❌", callback_data="restart")
    )
    
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{ticket_id}</b>\n\n{summary_text}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def send_to_admins(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id
    tid = data['ticket_id']
    
    report = (
        f"📩 <b>NEW CASE: #{tid}</b>\n"
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

    await call.message.edit_text(f"<b>Success! ✅ Ticket #{tid} Admins ko bhej diya gaya hai.</b>")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Shuru se shuru karte hain. Apni pareshani likhiye.")

if __name__ == '__main__':
    Thread(target=run).start()
    # Conflict error se bachne ke liye webhook delete
    async def on_startup(dp):
        await bot.delete_webhook()
    
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
