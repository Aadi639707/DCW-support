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
API_TOKEN = '8036869660:AAEqzNfoe94qQB_7Ua-CsPlRab_Y1r8FYBI'
GEMINI_KEY = 'AIzaSyChxjhkybI0Cx-vsw3K8PQkVQgjIBI27Hk'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

WEBHOOK_HOST = 'https://dcw-support.onrender.com'
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get('PORT', 8080))

# AI Setup (Fixed for 404 Error)
genai.configure(api_key=GEMINI_KEY)
# Using 'gemini-1.5-flash' explicitly without beta version issues
ai_model = genai.GenerativeModel(model_name='gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

class ComplaintState(StatesGroup):
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_confirm = State()

# English Only Instruction
SYSTEM_PROMPT = (
    "You are the DCW Support AI. You must speak ONLY in English. "
    "Do not use Hindi. Be professional and help the user report their group-related issues."
)

async def get_ai_reply(prompt_text):
    try:
        # Standard calling method
        response = await asyncio.to_thread(ai_model.generate_content, f"{SYSTEM_PROMPT}\n\nUser: {prompt_text}")
        return response.text
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "I am analyzing your issue. Please provide more details about your situation."

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    reply = await get_ai_reply("Greet the user in English and ask for their complaint.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW Support AI</b> 🛠\n\n{reply}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    if message.text.startswith('/'): return 
    await state.update_data(issue_text=message.text)
    # AI English reply based on issue
    reply = await get_ai_reply(f"User is saying: {message.text}. Respond in English and ask for a screenshot/proof or type /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        return await message.reply("Please provide a screenshot or type /skip to continue.")

    data = await state.get_data()
    tid = random.randint(100000, 999999)
    await state.update_data(ticket_id=tid)
    
    summary = await get_ai_reply(f"Summarize this issue in English: {data['issue_text']}. Tell them to click the Submit button.")
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"))
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{tid}</b>\n\n{summary}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def final_step(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    report = (f"📩 <b>New Case #{data['ticket_id']}</b>\n"
              f"👤 User: {call.from_user.full_name}\n"
              f"📝 Issue: {data['issue_text']}")
    
    for admin in ADMIN_IDS:
        try:
            if data.get('photo_id'): await bot.send_photo(admin, data['photo_id'], caption=report)
            else: await bot.send_message(admin, report)
        except: pass
        
    await call.message.edit_text("✅ Your case has been successfully forwarded to the admins. We will review it shortly.")
    await state.finish()

# --- WEBHOOK SETUP ---

async def on_startup(dispatcher):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        skip_updates=True,
        host='0.0.0.0',
        port=PORT,
    )
    
