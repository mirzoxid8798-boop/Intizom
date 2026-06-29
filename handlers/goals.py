from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points
from config import POINTS
from datetime import date

router = Router()

class GoalStates(StatesGroup):
    waiting_type = State()
    waiting_title = State()
    waiting_description = State()
    waiting_deadline = State()

def goals_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi maqsad", callback_data="goal_add")],
        [InlineKeyboardButton(text="📋 Kunlik maqsadlar", callback_data="goals_daily"),
         InlineKeyboardButton(text="📅 Haftalik", callback_data="goals_weekly")],
        [InlineKeyboardButton(text="🗓 Oylik", callback_data="goals_monthly"),
         InlineKeyboardButton(text="🌟 Yillik", callback_data="goals_yearly")],
        [InlineKeyboardButton(text="✅ Bajarilganlar", callback_data="goals_completed")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

def goal_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Kunlik", callback_data="gtype_daily"),
         InlineKeyboardButton(text="📅 Haftalik", callback_data="gtype_weekly")],
        [InlineKeyboardButton(text="🗓 Oylik", callback_data="gtype_monthly"),
         InlineKeyboardButton(text="🌟 Yillik", callback_data="gtype_yearly")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="goals_menu")],
    ])

@router.callback_query(F.data == "goals_menu")
async def goals_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🎯 *Maqsadlar bo'limi*\n\nMaqsad qo'ying va ularga erishing!",
        parse_mode="Markdown",
        reply_markup=goals_menu()
    )

@router.callback_query(F.data == "goal_add")
async def goal_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(GoalStates.waiting_type)
    await call.message.edit_text(
        "🎯 *Yangi maqsad*\n\nQanday muddatli maqsad qo'ymoqchisiz?",
        parse_mode="Markdown",
        reply_markup=goal_type_keyboard()
    )

@router.callback_query(F.data.startswith("gtype_"))
async def goal_type_selected(call: CallbackQuery, state: FSMContext):
    gtype = call.data.replace("gtype_", "")
    type_names = {"daily": "Kunlik", "weekly": "Haftalik", "monthly": "Oylik", "yearly": "Yillik"}
    await state.update_data(goal_type=gtype)
    await state.set_state(GoalStates.waiting_title)
    await call.message.edit_text(
        f"✏️ *{type_names[gtype]} maqsad*\n\nMaqsad nomini yozing:",
        parse_mode="Markdown"
    )

@router.message(GoalStates.waiting_title)
async def goal_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(GoalStates.waiting_description)
    await message.answer(
        "📝 Maqsad haqida qo'shimcha ma'lumot yozing (o'tkazish uchun /skip):"
    )

@router.message(GoalStates.waiting_description)
async def goal_description(message: Message, state: FSMContext):
    desc = None if message.text == "/skip" else message.text
    data = await state.get_data()
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO goals (user_id, title, description, goal_type) VALUES ($1, $2, $3, $4)",
            message.from_user.id, data["title"], desc, data["goal_type"]
        )
    await add_points(message.from_user.id, 2, "Yangi maqsad qo'yildi")
    await state.clear()
    await message.answer(
        f"✅ *Maqsad saqlandi!*\n\n🎯 {data['title']}\n\n+2 bal oldiniz! 🌟",
        parse_mode="Markdown",
        reply_markup=goals_menu()
    )

@router.callback_query(F.data.startswith("goals_"))
async def show_goals(call: CallbackQuery):
    gtype_map = {
        "goals_daily": "daily",
        "goals_weekly": "weekly",
        "goals_monthly": "monthly",
        "goals_yearly": "yearly",
        "goals_completed": None
    }
    gtype = gtype_map.get(call.data)
    p = await get_pool()
    async with p.acquire() as conn:
        if call.data == "goals_completed":
            goals = await conn.fetch(
                "SELECT * FROM goals WHERE user_id = $1 AND is_completed = TRUE ORDER BY created_at DESC LIMIT 20",
                call.from_user.id
            )
            title = "✅ Bajarilgan maqsadlar"
        else:
            goals = await conn.fetch(
                "SELECT * FROM goals WHERE user_id = $1 AND goal_type = $2 AND is_completed = FALSE ORDER BY created_at DESC",
                call.from_user.id, gtype
            )
            type_names = {"daily": "Kunlik", "weekly": "Haftalik", "monthly": "Oylik", "yearly": "Yillik"}
            title = f"🎯 {type_names.get(gtype, '')} maqsadlar"

    if not goals:
        await call.message.edit_text(
            f"{title}\n\n📭 Hozircha maqsad yo'q.",
            reply_markup=goals_menu()
        )
        return

    buttons = []
    text = f"{title}\n\n"
    for g in goals:
        status = "✅" if g["is_completed"] else "⭕"
        text += f"{status} {g['title']}\n"
        if not g["is_completed"]:
            buttons.append([InlineKeyboardButton(
                text=f"✅ {g['title'][:30]} — Bajardim",
                callback_data=f"goal_done_{g['id']}"
            )])

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="goals_menu")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("goal_done_"))
async def goal_done(call: CallbackQuery):
    goal_id = int(call.data.replace("goal_done_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        goal = await conn.fetchrow("SELECT * FROM goals WHERE id = $1", goal_id)
        await conn.execute(
            "UPDATE goals SET is_completed = TRUE WHERE id = $1",
            goal_id
        )
    await add_points(call.from_user.id, POINTS["goal"], "Maqsad bajarildi")
    await call.message.edit_text(
        f"🎉 *Barakalla!*\n\n✅ '{goal['title']}' maqsadini bajardingiz!\n\n+{POINTS['goal']} bal oldiniz! 🏆",
        parse_mode="Markdown",
        reply_markup=goals_menu()
    )
