import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import google.generativeai as genai

# --- VARIABLES ---
API_TOKEN = '8390111066:AAGP8GQZWBA0MnHiJN5ZMpTK2UgQb2xm100'
GEMINI_KEY = 'AIzaSyBO5AKWQIckPzKDXgHOaSMqFzbs7ogbtvQ'
ADMIN_IDS = [8369001361, 906332891, 8306853454]
GC_ID = -1002517438543

# AI Setup
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Temporary storage for complaints {user_id: {"text": "", "photo": ""}}
user_data = {}

SYSTEM_INSTRUCTION = (
    "You are the DCW SUPPORT BOT. Your only job is to collect complaints from members. "
    "Be polite and professional. Always reply in the same language the user uses. "
    "If they report an issue, ask for full details and a screenshot if possible. "
    "Once they give details, ask them to 'Submit' using the buttons."
)

# --- HANDLERS ---

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    # Sirf personal chat mein chale ya group mein filter kare
    welcome_text = "<b>Welcome to DCW Support!</b>\n\nHow can I help you today? Please describe your issue."
    await message.reply(welcome_text)

@dp.message_handler(content_types=['text', 'photo'])
async def handle_input(message: types.Message):
    uid = message.from_user.id
    
    if uid not in user_data:
        user_data[uid] = {"text": "", "photo_id": None}

    # Handling Media
    if message.photo:
        user_data[uid]["photo_id"] = message.photo[-1].file_id
        text_to_ai = "[User sent a photo/screenshot]"
    else:
        user_data[uid]["text"] += f"\n{message.text}"
        text_to_ai = message.text

    # AI Response
    try:
        chat = ai_model.start_chat(history=[])
        response = chat.send_message(f"{SYSTEM_INSTRUCTION}\nUser says: {text_to_ai}")
        bot_reply = response.text
    except:
        bot_reply = "Please provide your complaint details. (Kripya apni complaint likhein)"

    # Keyboard
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Submit ✅", callback_data="confirm_sub"),
        InlineKeyboardButton("Edit/Clear ✏️", callback_data="clear_data")
    )

    await message.reply(bot_reply, reply_markup=kb)

@dp.callback_query_handler(text="confirm_sub")
async def final_submit(call: types.CallbackQuery):
    uid = call.from_user.id
    data = user_data.get(uid)

    if not data:
        await call.answer("No data found!", show_alert=True)
        return

    # Admin Report Layout
    report = (
        f"🚨 <b>New Complaint Received!</b>\n\n"
        f"👤 <b>User:</b> <a href='tg://user?id={uid}'>{call.from_user.full_name}</a>\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"📝 <b>Details:</b> {data['text']}"
    )

    # Sending to all Admins
    for admin_id in ADMIN_IDS:
        try:
            if data['photo_id']:
                await bot.send_photo(admin_id, data['photo_id'], caption=report)
            else:
                await bot.send_message(admin_id, report)
        except Exception as e:
            print(f"Error sending to {admin_id}: {e}")

    await call.message.edit_text("<b>Done! ✅ Your complaint has been sent to admins.</b>")
    user_data.pop(uid, None)

@dp.callback_query_handler(text="clear_data")
async def clear_data(call: types.CallbackQuery):
    user_data.pop(call.from_user.id, None)
    await call.message.edit_text("Data cleared. Please write your complaint again.")

if __name__ == '__main__':
    print("DCW Support Bot is Online...")
    executor.start_polling(dp, skip_updates=True)
              
