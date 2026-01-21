import os
import random
import asyncio
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import google.generativeai as genai

# --- CONFIG ---
API_TOKEN = '8390111066:AAFGdAV0Wo0gqmw0QDysbbhqDe7jI5IASL8'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454, 1011842896, 8322056037]
WEBHOOK_HOST = 'https://dcw-support.onrender.com'
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

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

app = Flask(__name__)

# AI System Instruction
SYSTEM_PROMPT = "You are DCW Support AI. RULE: Always reply in the same language as the user. If they use English, you use English. If Hindi, you use Hindi. Be polite and human-like."

async def get_ai_reply(prompt_text):
    try:
        response = ai_model.generate_content(f"{SYSTEM_PROMPT}\n\n{prompt_text}")
        return response.text
    except:
        return "Please explain your problem. / Kripya apni pareshani batayein."

# --- BOT HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()
    reply = await get_ai_reply("User started the bot. Greet them professionally and ask for their complaint.")
    await ComplaintState.waiting_for_issue.set()
    await message.reply(f"<b>DCW Support AI</b> 🛠\n\n{reply}")

@dp.message_handler(state=ComplaintState.waiting_for_issue)
async def process_issue(message: types.Message, state: FSMContext):
    await state.update_data(issue_text=message.text)
    reply = await get_ai_reply(f"User said: {message.text}. Acknowledge it and ask for a screenshot or /skip in their language.")
    await ComplaintState.waiting_for_photo.set()
    await message.reply(reply)

@dp.message_handler(content_types=['photo', 'text'], state=ComplaintState.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo_id=message.photo[-1].file_id)
    elif message.text and message.text.lower() == '/skip':
        await state.update_data(photo_id=None)
    else:
        reply = await get_ai_reply("User did not send a photo. Remind them to send a screenshot or type /skip.")
        await message.reply(reply)
        return

    data = await state.get_data()
    tid = random.randint(100000, 999999)
    await state.update_data(ticket_id=tid)
    
    summary = await get_ai_reply(f"User issue: {data['issue_text']}. Summarize it and ask them to click Submit.")
    
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Submit Complaint ✅", callback_data="final_sub"),
        InlineKeyboardButton("Restart ❌", callback_data="restart")
    )
    await ComplaintState.waiting_for_confirm.set()
    await message.reply(f"<b>Ticket ID: #{tid}</b>\n\n{summary}", reply_markup=kb)

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

    thanks = await get_ai_reply(f"Complaint submitted. Tell user it's sent to admins. Ticket #{tid}.")
    await call.message.edit_text(f"✅ {thanks}")
    await state.finish()

@dp.callback_query_handler(text="restart", state="*")
async def restart(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await ComplaintState.waiting_for_issue.set()
    await call.message.edit_text("Restarted. Please describe your issue.")

# --- WEBHOOK SERVER ---

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    update = types.Update.to_object(request.json)
    asyncio.run_coroutine_threadsafe(dp.process_update(update), asyncio.get_event_loop())
    return 'OK', 200

@app.route('/')
def index(): return "DCW AI Bot is running on Webhook!"

if __name__ == '__main__':
    # Set webhook on startup
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.delete_webhook())
    loop.run_until_complete(bot.set_webhook(WEBHOOK_URL))
    
    # Run Flask
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
    
