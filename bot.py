import os
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

# --- CONFIG ---
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454]

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# Storage aur Bot setup
storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

# States define karna (Steps)
class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish() # Purana data clear
    await ComplaintState.waiting_for_issue.set()
    await message.reply("<b>Hello! DCW AI Support Assistant here.</b> 🛠\n\nPlease describe your problem in detail. What happened?")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    
    # AI response for empathy
    response = ai_model.generate_content(f"User is reporting an issue: {message.text}. Reply politely in the user's language and ask them to send a screenshot or proof if they have any, otherwise type /skip.")
    
    await ComplaintState.waiting_for_photo.set()
    await message.reply(response.text)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        await message.reply("Please send a photo/screenshot or type /skip to continue.")
        return

    # Final Summary creation using AI
    updated_data = await state.get_data()
    summary_prompt = f"Summarize this complaint for the user to review. Issue: {updated_data['issue_text']}. Tell them to check and click Submit."
    ai_summary = ai_model.generate_content(summary_prompt)

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("Confirm & Submit ✅", callback_data="final_sub"),
           InlineKeyboardButton("Restart ❌", callback_data="restart"))
    
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Review your details:</b>\n\n{ai_summary.text}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def send_to_admins(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = call.from_user.id
    
    report = (
        f"🚨 <b>NEW CASE: #{uid}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {call.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
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

    await call.message.edit_text("<b>Success! ✅ Your complaint is now with our Admins.</b>")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Starting again... Please describe your problem.")

if __name__ == '__main__':
    Thread(target=run).start()
    executor.start_polling(dp, skip_updates=True)
    
