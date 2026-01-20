import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import uvicorn

# .env yuklash
load_dotenv()

# Konfiguratsiya
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Bot va Dispatcher obyektlari
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Foydalanuvchi qaysi link egasiga yozayotganini saqlash (DB-siz vaqtincha xotira)
# Kalit: yozayotgan odam ID, Qiymat: qabul qiluvchi ID
active_sessions = {}

# --- LIFESPAN HANDLER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dastur ishga tushganda (Startup)
    await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True
    )
    logging.info("Webhook muvaffaqiyatli o'rnatildi")

    yield  # Shu yerda FastAPI ishlaydi

    # Dastur to'xtaganda (Shutdown)
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Sessiya yopildi")

app = FastAPI(lifespan=lifespan)

# --- BOT LOGIKASI ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()

    # 1. Agar foydalanuvchi birovning linki orqali kirgan bo'lsa
    if len(args) > 1:
        receiver_id = int(args[1])
        if receiver_id == message.from_user.id:
            await message.answer("O'zingizga o'zingiz xabar yoza olmaysiz! 😅")
            return

        active_sessions[message.from_user.id] = receiver_id
        await message.answer(
            "Siz hozir anonim xabar yuborish rejimidasiz. 🤫\n"
            "Xabaringizni yozing, men uni egasiga yetkazaman!"
        )
        return

    # 2. Onboarding (Yangi foydalanuvchi uchun)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    welcome_msg = (
        f"Salom, {message.from_user.full_name}! 👋\n\n"
        "Bu anonim xabarlar botiga xush kelibsiz.\n"
        "Sizga ham anonim xabar yozishlarini istasangiz, quyidagi linkni do'stlariga ulashing:\n\n"
        f"🔗 `{link}`\n\n"
        "Xabar kelganida, men sizga yuboruvchining ma'lumotlarini ham ko'rsataman! ✅"
    )
    await message.answer(welcome_msg, parse_mode="Markdown")

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_incoming_messages(message: types.Message):
    user_id = message.from_user.id

    # A. Anonim xabarga javob qaytarish logikasi
    if message.reply_to_message and "Yuboruvchi ID:" in message.reply_to_message.text:
        try:
            # Xabardan yuboruvchi ID sini qirqib olish
            original_sender_id = int(message.reply_to_message.text.split("ID:")[1].strip())
            await bot.send_message(
                original_sender_id,
                f"Siz yuborgan anonim xabarga javob keldi:\n\n💬 {message.text}"
            )
            await message.answer("Javobingiz yetkazildi! ✅")
        except Exception as e:
            await message.answer("Xatolik: Xabarni yetkazib bo'lmadi. Foydalanuvchi botni bloklagan bo'lishi mumkin.")
        return

    # B. Anonim xabar yuborish
    if user_id in active_sessions:
        receiver_id = active_sessions[user_id]

        # Maxsus funksiya: Yuboruvchi ma'lumotlarini qo'shish
        sender_info = (
            f"👤 Ismi: {message.from_user.full_name}\n"
            f"🆔 Yuboruvchi ID: {user_id}"
        )

        try:
            await bot.send_message(
                receiver_id,
                f"Sizda yangi anonim xabar! 📩\n\n"
                f"📝 Xabar: {message.text}\n\n"
                f"--- Ma'lumotlar ---\n{sender_info}"
            )
            await message.answer("Xabaringiz anonim tarzda yuborildi! 🚀")
            # Bir marta yuborgandan keyin sessiyani o'chirish (ixtiyoriy)
            # del active_sessions[user_id]
        except Exception:
            await message.answer("Xabarni yuborishda xatolik yuz berdi.")
    else:
        await message.answer("Xabar yuborish uchun avval birovning linki orqali kiring.")

# --- FASTAPI WEBHOOK ---

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST"), port=int(os.getenv("PORT")))
