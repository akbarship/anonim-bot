import logging
import os
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
import uvicorn

# .env yuklash
load_dotenv()

# Konfiguratsiya
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID"))
JSON_FILE = "privileged_users.json"

# Bot va Dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Vaqtincha xotira
active_sessions = {}

# --- JSON MA'LUMOTLAR BAZASI BILAN ISHLASH ---

def load_privileged_users():
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def save_privileged_user(user_id: int):
    users = load_privileged_users()
    if user_id not in users:
        users.append(user_id)
        with open(JSON_FILE, "w") as f:
            json.dump(users, f)
        return True
    return False

def remove_privileged_user(user_id: int):
    users = load_privileged_users()
    if user_id in users:
        users.remove(user_id)
        with open(JSON_FILE, "w") as f:
            json.dump(users, f)
        return True
    return False

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logging.info("Webhook o'rnatildi")
    yield
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

# --- ADMIN KOMANDALARI ---

@dp.message(Command("add_privilege"), F.from_user.id == MAIN_ADMIN_ID)
async def cmd_add_privilege(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        if save_privileged_user(user_id):
            await message.answer(f"✅ Foydalanuvchi {user_id} endi yuboruvchi ma'lumotlarini ko'ra oladi.")
        else:
            await message.answer("ℹ️ Bu foydalanuvchi allaqachon ro'yxatda bor.")
    except (IndexError, ValueError):
        await message.answer("❌ Xato! Format: `/add_privilege ID`", parse_mode="Markdown")

@dp.message(Command("remove_privilege"), F.from_user.id == MAIN_ADMIN_ID)
async def cmd_remove_privilege(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        if remove_privileged_user(user_id):
            await message.answer(f"🗑 Foydalanuvchi {user_id} ro'yxatdan o'chirildi.")
        else:
            await message.answer("❌ Bu foydalanuvchi ro'yxatda topilmadi.")
    except (IndexError, ValueError):
        await message.answer("❌ Xato! Format: `/remove_privilege ID`", parse_mode="Markdown")

# --- ASOSIY LOGIKA ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()

    if len(args) > 1:
        receiver_id = int(args[1])
        if receiver_id == message.from_user.id:
            await message.answer("O'zingizga xabar yoza olmaysiz!")
            return

        active_sessions[message.from_user.id] = receiver_id
        await message.answer("Xabaringizni yozing, men uni anonim tarzda yetkazaman! 🤫")
        return

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    await message.answer(
        f"Salom, {message.from_user.full_name}! 👋\n\n"
        f"Sizning anonim havolangiz:\n🔗 `{link}`",
        parse_mode="Markdown"
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    # Javob qaytarish (Reply)
    if message.reply_to_message and "Yuboruvchi ID:" in message.reply_to_message.text:
        try:
            target_id = int(message.reply_to_message.text.split("ID:")[1].strip())
            await bot.send_message(target_id, f"Sizning xabaringizga javob keldi:\n\n💬 {message.text}")
            await message.answer("Javob yuborildi! ✅")
        except:
            await message.answer("Xato: Yuborib bo'lmadi.")
        return

    # Anonim xabar yuborish
    if user_id in active_sessions:
        receiver_id = active_sessions[user_id]
        privileged_list = load_privileged_users()

        # PRIVILEGE TEKSHIRUVI: Qabul qiluvchi ro'yxatda bormi?
        if receiver_id in privileged_list:
            sender_data = f"\n\n--- Ma'lumotlar ---\n👤 Ismi: {message.from_user.full_name}\n🆔 Yuboruvchi ID: {user_id}"
        else:
            sender_data = f"\n\n🆔 Yuboruvchi ID: {user_id}" # Reply ishlashi uchun ID yashirin qolishi kerak

        try:
            await bot.send_message(
                receiver_id,
                f"📩 Yangi anonim xabar:\n\n📝 {message.text}{sender_data}"
            )
            await message.answer("Xabar yetkazildi! 🚀")
        except:
            await message.answer("Xabar yuborishda xatolik.")
    else:
        await message.answer("Xabar yuborish uchun link ustiga bosing.")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST"), port=int(os.getenv("PORT")))
