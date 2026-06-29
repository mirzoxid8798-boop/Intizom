from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points
from config import POINTS
from datetime import date

router = Router()

class HabitStates(StatesGroup):
    waiting_title = State()
    waiting_emoji = State()

def habits_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi odat", callback_data="habit_add")],
        [InlineKeyboardButton(text="✅ Bugungi odatlar", callback_data="habits_today")],
        [InlineKeyboardButton(text="🔥 Streak hisobi", callback_data="habits_streak")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="habits_stats")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@router.callback_query(F.data == "habits_menu")
async def habits_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "✅ *Odatlar bo'limi*\n\nKunlik odatlaringizni kuzatib boring! 🔥",
        parse_mode="Markdown",
        reply_markup=habits_menu()
    )

@router.callback_query(F.data == "habit_add")
async def habit_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(HabitStates.waiting_title)
    await call.message.edit_text(
        "✅ *Yangi odat*\n\nOdat nomini yozing:\n_Misol: Kitob o'qish, Sport, Erta turish_",
        parse_mode="Markdown"
    )

@router.message(HabitStates.waiting_title)
async def habit_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(HabitStates.waiting_emoji)
    await message.answer(
        "😊 Odat uchun emoji tanlang:\n\n"
        "📚 Kitob | 💪 Sport | 🧘 Meditatsiya\n"
        "💧 Suv | 🌅 Erta turish | 🎯 Boshqa\n\n"
        "Emoji yuboring yoki /skip bosing:"
    )

@router.message(HabitStates.waiting_emoji)
async def habit_emoji(message: Message, state: FSMContext):
    emoji = "✅" if message.text == "/skip" else message.text
    data = await state.get_data()
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO habits (user_id, title, emoji) VALUES ($1, $2, $3)",
            message.from_user.id, data["title"], emoji
        )
    await state.clear()
    await message.answer(
        f"✅ *Odat qo'shildi!*\n\n{emoji} {data['title']}\n\nHar kuni belgilab boring! 🔥",
        parse_mode="Markdown",
        reply_markup=habits_menu()
    )

@router.callback_query(F.data == "habits_today")
async def habits_today(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        habits = await conn.fetch(
            "SELECT * FROM habits WHERE user_id = $1 AND is_active = TRUE",
            call.from_user.id
        )
        logs_today = await conn.fetch(
            "SELECT * FROM habit_logs WHERE user_id = $1 AND log_date = $2",
            call.from_user.id, date.today()
        )

    if not habits:
        await call.message.edit_text(
            "✅ *Bugungi odatlar*\n\n📭 Hali odat qo'shilmagan.",
            parse_mode="Markdown",
            reply_markup=habits_menu()
        )
        return

    done_habits = [l["habit_id"] for l in logs_today if l["is_done"]]
    buttons = []
    text = "✅ *Bugungi odatlar:*\n\n"

    for h in habits:
        is_done = h["id"] in done_habits
        status = "✅" if is_done else "⭕"
        text += f"{status} {h['emoji']} {h['title']} (🔥{h['streak']})\n"
        if not is_done:
            buttons.append([InlineKeyboardButton(
                text=f"✅ {h['emoji']} {h['title'][:25]}",
                callback_data=f"habit_check_{h['id']}"
            )])

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="habits_menu")])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("habit_check_"))
async def habit_check(call: CallbackQuery):
    habit_id = int(call.data.replace("habit_check_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM habit_logs WHERE habit_id = $1 AND user_id = $2 AND log_date = $3",
            habit_id, call.from_user.id, date.today()
        )
        if not existing:
            await conn.execute(
                "INSERT INTO habit_logs (habit_id, user_id, is_done) VALUES ($1, $2, TRUE)",
                habit_id, call.from_user.id
            )
            await conn.execute(
                "UPDATE habits SET streak = streak + 1, best_streak = GREATEST(best_streak, streak + 1) WHERE id = $1",
                habit_id
            )
            habit = await conn.fetchrow("SELECT * FROM habits WHERE id = $1", habit_id)
            await add_points(call.from_user.id, POINTS["habit"], f"Odat: {habit['title']}")
            await call.answer(f"✅ Bajarildi! 🔥 Streak: {habit['streak']} kun! +{POINTS['habit']} bal")

    await habits_today(call)

@router.callback_query(F.data == "habits_streak")
async def habits_streak(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        habits = await conn.fetch(
            "SELECT * FROM habits WHERE user_id = $1 ORDER BY streak DESC",
            call.from_user.id
        )

    if not habits:
        await call.message.edit_text("📭 Hali odat yo'q.", reply_markup=habits_menu())
        return

    text = "🔥 *Streak hisobi:*\n\n"
    for h in habits:
        fire = "🔥" * min(h["streak"] // 7 + 1, 5)
        text += f"{h['emoji']} {h['title']}\n"
        text += f"{fire} Hozir: {h['streak']} kun | 🏆 Eng yaxshi: {h['best_streak']} kun\n\n"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=habits_menu())
