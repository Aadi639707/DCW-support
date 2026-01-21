import os
import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
import google.generativeai as genai

# --- CONFIG ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyChxjhkybI0Cx-vsw3K8PQkVQgjIBI27Hk' # Nayi Key Updated
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]

# Render Webhook Settings
WEBHOOK_HOST = 'https://dcw-support.onrender.com'
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Port for Render
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

# AI Personality
SYSTEM_PROMPT = (
    "You are the DCW Support AI. RULE: Always reply in the same language as the user. "
    "If they use Hindi, reply in Hindi. If English, reply in English. "
    "Ask for details, be empathetic, and act like a real person, not a robot."
)

async def get_ai_reply(prompt_text):
    try:
        response = ai_model.generate_content(f"{SYSTEM_PROMPT}\n\nUser: {prompt_text}")
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return "Please describe your issue. / Kripya apni pareshani batayein."

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    reply = await get_ai_reply("User started the bot. Greet them and ask how you can help with their complaint.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW Support AI</b> 🛠\n\n{reply}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    reply = await get_ai_reply(f"User reported: {message.text}. Acknowledge it and ask for a screenshot/proof or type /skip.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        reply = await get_ai_reply("User sent something else. Tell them to send a screenshot or type /skip to proceed.")
        return await message.reply(reply)

    data = await state.get_data()
    tid = random.randint(100000, 999999)
    await state.update_data(ticket_id=tid)
    
    summary = await get_ai_reply(f"Summarize this problem: {data['issue_text']}. Ask them to click Submit if okay.")
    
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        types.InlineKeyboardButton("Restart ❌", callback_data="restart")
    )
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{tid}</b>\n\n{summary}", reply_markup=kb)

@dp.callback_query_handler(text="final_sub", state=ComplaintState.waiting_for_confirm)
async def final_step(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tid = data['ticket_id']
    report = (f"📩 <b>NEW CASE: #{tid}</b>\n━━━━━━━━━━━━━\n"
              f"👤 <b>User:</b> {call.from_user.full_name}\n"
              f"🆔 <b>ID:</b> <code>{call.from_user.id}</code>\n"
              f"📝 <b>Issue:</b> {data['issue_text']}\n━━━━━━━━━━━━━")

    for admin in ADMIN_IDS:
        try:
            if data.get('photo_id'): await bot.send_photo(admin, data['photo_id'], caption=report)
            else: await bot.send_message(admin, report)
        except: pass

    thanks = await get_ai_reply(f"Complaint submitted. Tell them it's sent to admins. Ticket #{tid}.")
    await call.message.edit_text(f"✅ {thanks}")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart_bot(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Restarted. Please describe your issue.")

# --- WEBHOOK RUNNER ---

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
)
    
