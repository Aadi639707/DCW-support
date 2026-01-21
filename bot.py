import os
import random
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
import google.generativeai as genai

# --- CONFIG ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyChxjhkybI0Cx-vsw3K8PQkVQgjIBI27Hk'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

WEBHOOK_HOST = 'https://dcw-support.onrender.com'
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.environ.get('PORT', 8080))

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

SYSTEM_PROMPT = "You are DCW AI. Always reply in the same language as the user (Hindi or English). Be professional and help with complaints."

async def get_ai_reply(prompt_text):
    for _ in range(3): # 3 baar retry karega agar AI fail hua
        try:
            response = await asyncio.to_thread(ai_model.generate_content, f"{SYSTEM_PROMPT}\n\nUser: {prompt_text}")
            if response.text:
                return response.text
        except:
            await asyncio.sleep(1)
    return "I'm listening. Please describe your problem in detail.\n\nMain sun raha hoon. Kripya apni pareshani detail mein batayein."

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    reply = await get_ai_reply("Greet the user and ask for their complaint.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW Support AI</b> 🛠\n\n{reply}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    if message.text.startswith('/'): return
    await state.update_data(issue_text=message.text)
    reply = await get_ai_reply(f"User reported: {message.text}. Ask for proof/photo or /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        return await message.reply("Please send a photo/screenshot or type /skip.")

    data = await state.get_data()
    tid = random.randint(100000, 999999)
    await state.update_data(ticket_id=tid)
    summary = await get_ai_reply(f"Summarize: {data['issue_text']}. Ask to click Submit.")
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Submit ✅", callback_data="final_sub"))
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket: #{tid}</b>\n\n{summary}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def final_step(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    report = f"📩 <b>New Case #{data['ticket_id']}</b>\nUser: {call.from_user.full_name}\nIssue: {data['issue_text']}"
    for admin in ADMIN_IDS:
        try:
            if data.get('photo_id'): await bot.send_photo(admin, data['photo_id'], caption=report)
            else: await bot.send_message(admin, report)
        except: pass
    await call.message.edit_text("✅ Sent to Admins! Your issue will be resolved soon.")
    await state.finish()

# --- RUNNER ---

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
    
