from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points
from config import POINTS
from datetime import date

router = Router()

class PlanStates(StatesGroup):
    waiting_title = State()
    waiting_time = State()

def plan_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi vazifa", callback_data="plan_add")],
        [InlineKeyboardButton(text="📋 Bugungi reja", callback_data="plan_today")],
        [InlineKeyboardButton(text="✅ Bajarilganlar", callback_data="plan_done_list")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@router.callback_query(F.data == "daily_plan_menu")
async def daily_plan_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    p = await get_pool()
    async with p.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2",
            call.from_user.id, date.today()
        )
        done = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2 AND is_completed = TRUE",
            call.from_user.id, date.today()
        )
    pct = int(done / total * 100) if total > 0 else 0
    text = f"📅 *Kunlik Reja*\n\nBugun: {done}/{total} ({pct}%) ✅"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=plan_menu())

@router.callback_query(F.data == "plan_add")
async def plan_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(PlanStates.waiting_title)
    await call.message.edit_text("📋 *Yangi vazifa*\n\nVazifa nomini yozing:", parse_mode="Markdown")

@router.message(PlanStates.waiting_title)
async def plan_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(PlanStates.waiting_time)
    await message.answer("⏰ Vaqtni kiriting (yoki /skip):\nMisol: 10:00")

@router.message(PlanStates.waiting_time)
async def plan_time(message: Message, state: FSMContext):
    time = None if message.text == "/skip" else message.text
    data = await state.get_data()
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO daily_plans (user_id, title, scheduled_time) VALUES ($1, $2, $3)",
            message.from_user.id, data["title"], time
        )
    await state.clear()
    time_text = f"⏰ {time}" if time else ""
    await message.answer(
        f"✅ *Vazifa qo'shildi!*\n\n📌 {data['title']} {time_text}",
        parse_mode="Markdown", reply_markup=plan_menu()
    )

@router.callback_query(F.data == "plan_today")
async def plan_today(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        plans = await conn.fetch(
            "SELECT * FROM daily_plans WHERE user_id = $1 AND plan_date = $2 ORDER BY scheduled_time NULLS LAST",
            call.from_user.id, date.today()
        )
    if not plans:
        await call.message.edit_text("📋 Bugun reja yo'q.", reply_markup=plan_menu())
        return

    buttons = []
    text = "📋 *Bugungi reja:*\n\n"
    for pl in plans:
        status = "✅" if pl["is_completed"] else "⭕"
        time_str = f" {pl['scheduled_time']}" if pl["scheduled_time"] else ""
        text += f"{status}{time_str} {pl['title']}\n"
        if not pl["is_completed"]:
            buttons.append([InlineKeyboardButton(
                text=f"✅ {pl['title'][:30]}",
                callback_data=f"plan_done_{pl['id']}"
            )])

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="daily_plan_menu")])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("plan_done_"))
async def plan_done(call: CallbackQuery):
    plan_id = int(call.data.replace("plan_done_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        plan = await conn.fetchrow("SELECT * FROM daily_plans WHERE id = $1", plan_id)
        await conn.execute("UPDATE daily_plans SET is_completed = TRUE WHERE id = $1", plan_id)
    await add_points(call.from_user.id, POINTS["daily_plan"], "Kunlik vazifa bajarildi")
    await call.answer(f"✅ '{plan['title']}' bajarildi! +{POINTS['daily_plan']} bal 🌟")
    await plan_today(call)
