from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points
from datetime import datetime

router = Router()

class ReminderStates(StatesGroup):
    waiting_title = State()
    waiting_datetime = State()

def reminders_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi eslatma", callback_data="reminder_add")],
        [InlineKeyboardButton(text="📋 Mening eslatmalarim", callback_data="reminder_list")],
        [InlineKeyboardButton(text="✅ Bajarilganlar", callback_data="reminder_done_list")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@router.callback_query(F.data == "reminders_menu")
async def reminders_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🔔 *Eslatmalar*\n\nAniq vaqtga eslatma qo'ying!",
        parse_mode="Markdown",
        reply_markup=reminders_menu()
    )

@router.callback_query(F.data == "reminder_add")
async def reminder_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(ReminderStates.waiting_title)
    await call.message.edit_text(
        "🔔 *Yangi eslatma*\n\nEslatma nomini yozing:\n\n_Misol: Shifokorga borish_",
        parse_mode="Markdown"
    )

@router.message(ReminderStates.waiting_title)
async def reminder_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(ReminderStates.waiting_datetime)
    await message.answer(
        "📅 *Vaqtni kiriting:*\n\n"
        "Format: `KK.OO.YYYY SS:MM`\n"
        "Misol: `25.07.2025 09:00`",
        parse_mode="Markdown"
    )

@router.message(ReminderStates.waiting_datetime)
async def reminder_datetime(message: Message, state: FSMContext):
    try:
        remind_at = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        if remind_at < datetime.now():
            await message.answer("❌ Vaqt o'tib ketgan. Kelajakdagi vaqt kiriting:")
            return
        data = await state.get_data()
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute(
                "INSERT INTO reminders (user_id, title, remind_at) VALUES ($1, $2, $3)",
                message.from_user.id, data["title"], remind_at
            )
        await state.clear()
        await message.answer(
            f"✅ *Eslatma qo'shildi!*\n\n"
            f"📌 {data['title']}\n"
            f"⏰ {remind_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Aniq shu vaqtda xabar yuboriladi! 🔔",
            parse_mode="Markdown",
            reply_markup=reminders_menu()
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n\n"
            "To'g'ri format: `25.07.2025 09:00`",
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "reminder_list")
async def reminder_list(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        reminders = await conn.fetch(
            "SELECT * FROM reminders WHERE user_id = $1 AND is_done = FALSE AND remind_at > NOW() ORDER BY remind_at LIMIT 10",
            call.from_user.id
        )

    if not reminders:
        await call.message.edit_text(
            "🔔 *Eslatmalar*\n\n📭 Hozircha faol eslatma yo'q.",
            parse_mode="Markdown",
            reply_markup=reminders_menu()
        )
        return

    text = "🔔 *Faol eslatmalar:*\n\n"
    buttons = []
    for r in reminders:
        time_str = r["remind_at"].strftime("%d.%m %H:%M")
        text += f"📌 {r['title']}\n⏰ {time_str}\n\n"
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {r['title'][:25]} o'chirish",
            callback_data=f"reminder_del_{r['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reminders_menu")])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("reminder_del_"))
async def reminder_delete(call: CallbackQuery):
    rid = int(call.data.replace("reminder_del_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM reminders WHERE id = $1", rid)
    await call.answer("✅ Eslatma o'chirildi")
    await reminder_list(call)

@router.callback_query(F.data.startswith("reminder_done_"))
async def reminder_done(call: CallbackQuery):
    rid = int(call.data.replace("reminder_done_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        reminder = await conn.fetchrow("SELECT * FROM reminders WHERE id = $1", rid)
        await conn.execute("UPDATE reminders SET is_done = TRUE WHERE id = $1", rid)
    await add_points(call.from_user.id, 5, "Eslatma bajarildi")
    await call.message.edit_text(
        f"🎉 *Barakalla!*\n\n✅ '{reminder['title']}' bajarildi!\n\n+5 bal oldiniz! 🌟",
        parse_mode="Markdown",
        reply_markup=reminders_menu()
    )

@router.callback_query(F.data.startswith("reminder_snooze_"))
async def reminder_snooze(call: CallbackQuery):
    rid = int(call.data.replace("reminder_snooze_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        reminder = await conn.fetchrow("SELECT * FROM reminders WHERE id = $1", rid)
        count = (reminder["reminder_count"] or 0) + 1
        await conn.execute(
            "UPDATE reminders SET reminder_count = $1 WHERE id = $2",
            count, rid
        )
    await call.answer("⏰ Keyinroq eslatiladi")
    await call.message.edit_reply_markup(reply_markup=None)
