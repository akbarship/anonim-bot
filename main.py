import logging
import os
import json
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command

# .env faylini yuklash
load_dotenv()

# Konfiguratsiya
API_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID"))
JSON_FILE = "privileged_users.json"

# Loggingni sozlash
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher obyektlari
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Foydalanuvchi qaysi link egasiga yozayotganini saqlash (Vaqtincha xotira)
active_sessions = {}

# --- JSON MA'LUMOTLAR BAZASI BILAN ISHLASH ---

def load_privileged_users():
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(JSON_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

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

# --- ADMIN KOMANDALARI (Faqat Asosiy Admin uchun) ---

@dp.message(Command("add_privilege"), F.from_user.id == MAIN_ADMIN_ID)
async def cmd_add_privilege(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        if save_privileged_user(user_id):
            await message.answer(f"✅ Foydalanuvchi {user_id} endi yuboruvchi ma'lumotlarini ko'ra oladi.")
        else:
            await message.answer("ℹ️ Bu foydalanuvchi allaqachon ro'yxatda bor.")
    except (IndexError, ValueError):
        await message.answer("❌ Xato! Format: `/add_privilege ID`")

@dp.message(Command("remove_privilege"), F.from_user.id == MAIN_ADMIN_ID)
async def cmd_remove_privilege(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        if remove_privileged_user(user_id):
            await message.answer(f"🗑 Foydalanuvchi {user_id} ro'yxatdan o'chirildi.")
        else:
            await message.answer("❌ Bu foydalanuvchi ro'yxatda topilmadi.")
    except (IndexError, ValueError):
        await message.answer("❌ Xato! Format: `/remove_privilege ID`")

# --- ASOSIY BOT LOGIKASI ---

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()

    # 1. Agar foydalanuvchi anonim link orqali kirsa
    if len(args) > 1:
        receiver_id = int(args[1])
        if receiver_id == message.from_user.id:
            await message.answer("O'zingizga o'zingiz xabar yoza olmaysiz! 😅")
            return

        active_sessions[message.from_user.id] = receiver_id
        await message.answer("Siz hozir anonim rejimdasiz. 🤫\nXabaringizni yozing, uni egasiga yetkazaman!")
        return

    # 2. Onboarding (Yangi foydalanuvchi uchun)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    welcome_text = (
        f"Salom, {message.from_user.full_name}! 👋\n\n"
        "Sizga ham anonim xabarlar yozishlarini istaysizmi?\n"
        "Unda quyidagi shaxsiy havolangizni ulashing:\n\n"
        f"🔗 `{link}`\n\n"
        "Xabar kelganida, kim yozganini ko'rishingiz mumkin (agar sizga ruxsat berilgan bo'lsa)!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_text_messages(message: types.Message):
    user_id = message.from_user.id

    # A. Anonim xabarga javob qaytarish (Reply)
    if message.reply_to_message and "Yuboruvchi ID:" in message.reply_to_message.text:
        try:
            # Xabardan yashirin ID ni ajratib olish
            target_id = int(message.reply_to_message.text.split("ID:")[1].strip())
            await bot.send_message(
                target_id,
                f"Siz yuborgan anonim xabarga javob keldi:\n\n💬 {message.text}"
            )
            await message.answer("Javobingiz yetkazildi! ✅")
        except Exception:
            await message.answer("Xatolik: Xabarni yetkazish imkoni bo'lmadi.")
        return

    # B. Anonim xabar yuborish
    if user_id in active_sessions:
        receiver_id = active_sessions[user_id]
        privileged_list = load_privileged_users()

        # Ruxsat borligiga qarab ma'lumotlarni ko'rsatish
        if receiver_id in privileged_list:
            sender_data = (
                f"\n\n--- Ma'lumotlar ---\n"
                f"👤 Ismi: {message.from_user.full_name}\n"
                f"📧 Yuboruvchi USER: @{message.from_user.username}\n"
                f"🆔 Yuboruvchi ID: {user_id}"
            )
        else:
            sender_data = f""

        try:
            await bot.send_message(
                receiver_id,
                f"📩 Yangi anonim xabar keldi:\n\n📝 {message.text}{sender_data}"
            )
            await message.answer("Xabaringiz anonim tarzda yuborildi! 🚀")
        except Exception:
            await message.answer("Xabar yuborishda xatolik yuz berdi.")
    else:
        await message.answer("Xabar yuborish uchun avval birovning havolasiga bosing.")

# --- ISHGA TUSHIRISH ---

async def main():
    # Webhookni o'chirish (agar avval ishlatilgan bo'lsa)
    await bot.delete_webhook(drop_pending_updates=True)
    # Pollingni boshlash
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi")
