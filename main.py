import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db, add_user, get_user
from handlers.goals import router as goals_router
from handlers.prayer import router as prayer_router
from handlers.reminders import router as reminders_router
from handlers.habits import router as habits_router
from handlers.brain import router as brain_router
from handlers.daily_plan import router as plan_router
from handlers.other import (
    stats_router, pomodoro_router, journal_router,
    ideas_router, debt_router, achievements_router,
    settings_router, routine_router, profile_router, group_router
)
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Routerlarni ro'yxatdan o'tkazish
dp.include_router(goals_router)
dp.include_router(prayer_router)
dp.include_router(reminders_router)
dp.include_router(habits_router)
dp.include_router(brain_router)
dp.include_router(plan_router)
dp.include_router(stats_router)
dp.include_router(pomodoro_router)
dp.include_router(journal_router)
dp.include_router(ideas_router)
dp.include_router(debt_router)
dp.include_router(achievements_router)
dp.include_router(settings_router)
dp.include_router(routine_router)
dp.include_router(profile_router)
dp.include_router(group_router)

def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Maqsadlar", callback_data="goals_menu"),
            InlineKeyboardButton(text="📅 Kunlik Reja", callback_data="daily_plan_menu"),
        ],
        [
            InlineKeyboardButton(text="🔔 Eslatmalar", callback_data="reminders_menu"),
            InlineKeyboardButton(text="✅ Odatlar", callback_data="habits_menu"),
        ],
        [
            InlineKeyboardButton(text="🕌 Ibodat", callback_data="prayer_menu"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="stats_menu"),
        ],
        [
            InlineKeyboardButton(text="👤 Profil", callback_data="profile_menu"),
            InlineKeyboardButton(text="💰 Qarz Daftari", callback_data="debt_menu"),
        ],
        [
            InlineKeyboardButton(text="🌅 Kunlik Routin", callback_data="routine_menu"),
            InlineKeyboardButton(text="🏆 Yutuqlar", callback_data="achievements_menu"),
        ],
        [
            InlineKeyboardButton(text="📝 Kundalik", callback_data="journal_menu"),
            InlineKeyboardButton(text="⏱ Pomodoro", callback_data="pomodoro_menu"),
        ],
        [
            InlineKeyboardButton(text="💡 G'oyalar", callback_data="ideas_menu"),
            InlineKeyboardButton(text="🧠 Aql Charxlash", callback_data="brain_menu"),
        ],
        [
            InlineKeyboardButton(text="👨‍👩‍👧 Guruh Rejimi", callback_data="group_menu"),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="settings_menu"),
        ],
    ])

@dp.message(Command("start"))
async def start_handler(message: Message):
    await add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )
    user = await get_user(message.from_user.id)
    name = user["full_name"] or message.from_user.first_name or "Do'stim"

    await message.answer(
        f"Assalomu alaykum, *{name}*! 👋\n\n"
        f"🤖 *Intizom Botiga xush kelibsiz!*\n\n"
        f"Bu bot sizga:\n"
        f"• 🎯 Maqsadlarga erishishda\n"
        f"• ✅ Odatlar shakllantirishda\n"
        f"• 🕌 Ibodatni nazorat qilishda\n"
        f"• 📊 O'zingizni tahlil qilishda\n"
        f"yordam beradi!\n\n"
        f"Quyidagi bo'limlardan birini tanlang 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

@dp.message(Command("menu"))
async def menu_handler(message: Message):
    await message.answer(
        "📋 *Bosh Menyu*\n\nBo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

@dp.callback_query(lambda c: c.data == "main_menu")
async def main_menu_callback(call: CallbackQuery):
    await call.message.edit_text(
        "📋 *Bosh Menyu*\n\nBo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "📖 *Yordam*\n\n"
        "/start — Botni boshlash\n"
        "/menu — Bosh menyu\n"
        "/help — Yordam\n\n"
        "Barcha bo'limlar menyuda mavjud 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def main():
    logger.info("Bot ishga tushmoqda...")
    await init_db()
    asyncio.create_task(start_scheduler(bot))
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
