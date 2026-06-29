from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points, get_user, get_points_stats
from config import POINTS
from datetime import date, datetime

# ============ STATS ============
stats_router = Router()

def stats_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Bugungi", callback_data="stats_today"),
         InlineKeyboardButton(text="📊 Haftalik", callback_data="stats_week")],
        [InlineKeyboardButton(text="🗓 Oylik", callback_data="stats_month"),
         InlineKeyboardButton(text="🌟 Yillik", callback_data="stats_year")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@stats_router.callback_query(F.data == "stats_menu")
async def stats_menu_handler(call: CallbackQuery):
    await call.message.edit_text("📊 *Statistika*\nQaysi davr?", parse_mode="Markdown", reply_markup=stats_menu())

@stats_router.callback_query(F.data.startswith("stats_"))
async def show_stats(call: CallbackQuery):
    period_map = {"stats_today": "today", "stats_week": "week", "stats_month": "month", "stats_year": "year"}
    period = period_map.get(call.data, "week")
    period_names = {"today": "Bugungi", "week": "Haftalik", "month": "Oylik", "year": "Yillik"}

    p = await get_pool()
    async with p.acquire() as conn:
        if period == "today":
            interval = "1 day"
        elif period == "week":
            interval = "7 days"
        elif period == "month":
            interval = "30 days"
        else:
            interval = "365 days"

        points = await conn.fetchval(
            f"SELECT COALESCE(SUM(points), 0) FROM points_log WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '{interval}'",
            call.from_user.id
        )
        goals_done = await conn.fetchval(
            f"SELECT COUNT(*) FROM goals WHERE user_id = $1 AND is_completed = TRUE AND created_at >= NOW() - INTERVAL '{interval}'",
            call.from_user.id
        )
        prayers_done = await conn.fetchval(
            f"SELECT COUNT(*) FROM prayers WHERE user_id = $1 AND is_done = TRUE AND created_at >= NOW() - INTERVAL '{interval}'",
            call.from_user.id
        )
        habits_done = await conn.fetchval(
            f"SELECT COUNT(*) FROM habit_logs WHERE user_id = $1 AND is_done = TRUE AND created_at >= NOW() - INTERVAL '{interval}'",
            call.from_user.id
        )
        pomodoros = await conn.fetchval(
            f"SELECT COUNT(*) FROM pomodoro_sessions WHERE user_id = $1 AND is_completed = TRUE AND started_at >= NOW() - INTERVAL '{interval}'",
            call.from_user.id
        )
        user = await conn.fetchrow("SELECT total_points FROM users WHERE user_id = $1", call.from_user.id)

    text = f"📊 *{period_names[period]} statistika*\n\n"
    text += f"🌟 Jami ballar: *{points}*\n"
    text += f"🏆 Umumiy ballar: *{user['total_points']}*\n\n"
    text += f"🎯 Bajarilgan maqsadlar: *{goals_done}*\n"
    text += f"🕌 Namozlar: *{prayers_done}*\n"
    text += f"✅ Odatlar: *{habits_done}*\n"
    text += f"⏱ Pomodoro: *{pomodoros}* sessiya\n"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=stats_menu())


# ============ POMODORO ============
pomodoro_router = Router()

class PomodoroStates(StatesGroup):
    waiting_task = State()

def pomodoro_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Pomodoro boshlash", callback_data="pomo_start")],
        [InlineKeyboardButton(text="📊 Bugungi sessiyalar", callback_data="pomo_today")],
        [InlineKeyboardButton(text="🏆 Jami fokus vaqti", callback_data="pomo_total")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@pomodoro_router.callback_query(F.data == "pomodoro_menu")
async def pomodoro_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "⏱ *Pomodoro Timer*\n\n25 daqiqa fokus + 5 daqiqa dam 🎯",
        parse_mode="Markdown", reply_markup=pomodoro_menu()
    )

@pomodoro_router.callback_query(F.data == "pomo_start")
async def pomo_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(PomodoroStates.waiting_task)
    await call.message.edit_text("⏱ *Pomodoro*\n\nNima qilmoqchisiz? Yozing:", parse_mode="Markdown")

@pomodoro_router.message(PomodoroStates.waiting_task)
async def pomo_task(message: Message, state: FSMContext):
    p = await get_pool()
    async with p.acquire() as conn:
        record = await conn.fetchrow(
            "INSERT INTO pomodoro_sessions (user_id, task_name) VALUES ($1, $2) RETURNING id",
            message.from_user.id, message.text
        )
    await state.clear()
    await message.answer(
        f"✅ *Pomodoro boshlandi!*\n\n📌 Vazifa: {message.text}\n⏱ 25 daqiqa fokusda bo'ling!\n\n"
        f"Taymer tugaganda xabar yuboriladi 🔔",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tugatdim", callback_data=f"pomo_done_{record['id']}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"pomo_cancel_{record['id']}")],
        ])
    )

@pomodoro_router.callback_query(F.data.startswith("pomo_done_"))
async def pomo_done(call: CallbackQuery):
    session_id = int(call.data.replace("pomo_done_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE pomodoro_sessions SET is_completed = TRUE WHERE id = $1", session_id)
    await add_points(call.from_user.id, POINTS["pomodoro"], "Pomodoro sessiya tugallandi")
    await call.message.edit_text(
        f"🎉 *Barakalla!* Pomodoro tugallandi!\n\n5 daqiqa dam oling ☕\n+{POINTS['pomodoro']} bal oldiniz! 🌟",
        parse_mode="Markdown", reply_markup=pomodoro_menu()
    )

@pomodoro_router.callback_query(F.data.startswith("pomo_cancel_"))
async def pomo_cancel(call: CallbackQuery):
    session_id = int(call.data.replace("pomo_cancel_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM pomodoro_sessions WHERE id = $1", session_id)
    await call.message.edit_text("❌ Pomodoro bekor qilindi.", reply_markup=pomodoro_menu())

@pomodoro_router.callback_query(F.data == "pomo_today")
async def pomo_today(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        sessions = await conn.fetch(
            "SELECT * FROM pomodoro_sessions WHERE user_id = $1 AND DATE(started_at) = $2 ORDER BY started_at DESC",
            call.from_user.id, date.today()
        )
    if not sessions:
        await call.message.edit_text("📊 Bugun hali pomodoro yo'q.", reply_markup=pomodoro_menu())
        return
    text = "📊 *Bugungi pomodoro sessiyalari:*\n\n"
    total_done = 0
    for s in sessions:
        status = "✅" if s["is_completed"] else "❌"
        text += f"{status} {s['task_name']}\n"
        if s["is_completed"]:
            total_done += 1
    text += f"\n🏆 Tugatilgan: {total_done}/{len(sessions)}"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=pomodoro_menu())


# ============ JOURNAL ============
journal_router = Router()

class JournalStates(StatesGroup):
    writing = State()

def journal_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Yangi yozuv", callback_data="journal_add")],
        [InlineKeyboardButton(text="📖 Mening yozuvlarim", callback_data="journal_list")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@journal_router.callback_query(F.data == "journal_menu")
async def journal_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("📝 *Kundalik*\n\nFikrlaringizni yozing 💭", parse_mode="Markdown", reply_markup=journal_menu())

@journal_router.callback_query(F.data == "journal_add")
async def journal_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(JournalStates.writing)
    moods = [["😊 Baxtli", "😐 Oddiy", "😔 Xafa"], ["😤 G'azablangan", "😴 Charchagan", "🤩 Hayajonli"]]
    buttons = [[InlineKeyboardButton(text=m, callback_data=f"mood_{m}") for m in row] for row in moods]
    await call.message.edit_text(
        "📝 *Bugungi kayfiyatingiz?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@journal_router.callback_query(F.data.startswith("mood_"))
async def mood_selected(call: CallbackQuery, state: FSMContext):
    mood = call.data.replace("mood_", "")
    await state.update_data(mood=mood)
    await state.set_state(JournalStates.writing)
    await call.message.edit_text(f"📝 Kayfiyat: {mood}\n\nBugun nima bo'ldi? Yozing:")

@journal_router.message(JournalStates.writing)
async def journal_write(message: Message, state: FSMContext):
    data = await state.get_data()
    mood = data.get("mood", "")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO journal (user_id, content, mood) VALUES ($1, $2, $3)",
            message.from_user.id, message.text, mood
        )
    await add_points(message.from_user.id, POINTS["journal"], "Kundalik yozildi")
    await state.clear()
    await message.answer(
        f"📝 *Yozuv saqlandi!*\n\nKayfiyat: {mood}\n+{POINTS['journal']} bal! 🌟",
        parse_mode="Markdown", reply_markup=journal_menu()
    )

@journal_router.callback_query(F.data == "journal_list")
async def journal_list(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        entries = await conn.fetch(
            "SELECT * FROM journal WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
            call.from_user.id
        )
    if not entries:
        await call.message.edit_text("📖 Hali yozuv yo'q.", reply_markup=journal_menu())
        return
    text = "📖 *So'nggi yozuvlar:*\n\n"
    for e in entries:
        date_str = e["created_at"].strftime("%d.%m %H:%M")
        text += f"*{date_str}* {e['mood']}\n{e['content'][:100]}...\n\n" if len(e["content"]) > 100 else f"*{date_str}* {e['mood']}\n{e['content']}\n\n"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=journal_menu())


# ============ IDEAS ============
ideas_router = Router()

class IdeaStates(StatesGroup):
    waiting_title = State()
    waiting_content = State()

def ideas_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Yangi g'oya", callback_data="idea_add")],
        [InlineKeyboardButton(text="📋 G'oyalarim", callback_data="idea_list")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@ideas_router.callback_query(F.data == "ideas_menu")
async def ideas_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("💡 *G'oyalar Daftarchasi*\n\nG'oyangizni yozing!", parse_mode="Markdown", reply_markup=ideas_menu())

@ideas_router.callback_query(F.data == "idea_add")
async def idea_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(IdeaStates.waiting_title)
    await call.message.edit_text("💡 *Yangi g'oya*\n\nG'oya sarlavhasini yozing:", parse_mode="Markdown")

@ideas_router.message(IdeaStates.waiting_title)
async def idea_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(IdeaStates.waiting_content)
    await message.answer("📝 G'oya haqida batafsil yozing (yoki /skip):")

@ideas_router.message(IdeaStates.waiting_content)
async def idea_content(message: Message, state: FSMContext):
    data = await state.get_data()
    content = None if message.text == "/skip" else message.text
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO ideas (user_id, title, content) VALUES ($1, $2, $3)",
            message.from_user.id, data["title"], content
        )
    await add_points(message.from_user.id, POINTS["idea"], "Yangi g'oya yozildi")
    await state.clear()
    await message.answer(
        f"💡 *G'oya saqlandi!*\n\n{data['title']}\n+{POINTS['idea']} bal! 🌟",
        parse_mode="Markdown", reply_markup=ideas_menu()
    )

@ideas_router.callback_query(F.data == "idea_list")
async def idea_list(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        ideas = await conn.fetch(
            "SELECT * FROM ideas WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
            call.from_user.id
        )
    if not ideas:
        await call.message.edit_text("💡 Hali g'oya yo'q.", reply_markup=ideas_menu())
        return
    text = "💡 *G'oyalarim:*\n\n"
    for i in ideas:
        date_str = i["created_at"].strftime("%d.%m")
        text += f"📌 *{i['title']}* ({date_str})\n"
        if i["content"]:
            text += f"_{i['content'][:80]}_\n"
        text += "\n"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=ideas_menu())


# ============ DEBT ============
debt_router = Router()

class DebtStates(StatesGroup):
    waiting_person = State()
    waiting_amount = State()
    waiting_type = State()
    waiting_desc = State()

def debt_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data="debt_add")],
        [InlineKeyboardButton(text="💸 Men berdim (berdi)", callback_data="debt_gave_list"),
         InlineKeyboardButton(text="💰 Menga berdi", callback_data="debt_took_list")],
        [InlineKeyboardButton(text="✅ To'langan qarzlar", callback_data="debt_paid_list")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@debt_router.callback_query(F.data == "debt_menu")
async def debt_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("💰 *Qarz Daftari*", parse_mode="Markdown", reply_markup=debt_menu())

@debt_router.callback_query(F.data == "debt_add")
async def debt_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(DebtStates.waiting_type)
    await call.message.edit_text(
        "💰 *Qarz turi:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Men berdim", callback_data="dtype_gave"),
             InlineKeyboardButton(text="💰 Menga berdi", callback_data="dtype_took")],
        ])
    )

@debt_router.callback_query(F.data.startswith("dtype_"))
async def debt_type(call: CallbackQuery, state: FSMContext):
    dtype = call.data.replace("dtype_", "")
    await state.update_data(debt_type=dtype)
    await state.set_state(DebtStates.waiting_person)
    await call.message.edit_text("👤 Kim uchun/kimdan? Ismini yozing:")

@debt_router.message(DebtStates.waiting_person)
async def debt_person(message: Message, state: FSMContext):
    await state.update_data(person_name=message.text)
    await state.set_state(DebtStates.waiting_amount)
    await message.answer("💵 Miqdorni yozing (raqam):\nMisol: 500000")

@debt_router.message(DebtStates.waiting_amount)
async def debt_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
        await state.update_data(amount=amount)
        await state.set_state(DebtStates.waiting_desc)
        await message.answer("📝 Izoh yozing (yoki /skip):")
    except:
        await message.answer("❌ Raqam kiriting!")

@debt_router.message(DebtStates.waiting_desc)
async def debt_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = None if message.text == "/skip" else message.text
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO debts (user_id, person_name, amount, debt_type, description) VALUES ($1,$2,$3,$4,$5)",
            message.from_user.id, data["person_name"], data["amount"], data["debt_type"], desc
        )
    type_text = "berdingiz" if data["debt_type"] == "gave" else "oldingiz"
    await state.clear()
    await message.answer(
        f"✅ *Qarz saqlandi!*\n\n"
        f"👤 {data['person_name']}\n"
        f"💵 {data['amount']:,.0f} so'm\n"
        f"📌 {type_text}",
        parse_mode="Markdown", reply_markup=debt_menu()
    )

@debt_router.callback_query(F.data.startswith("debt_gave_list"))
async def debt_gave_list(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        debts = await conn.fetch(
            "SELECT * FROM debts WHERE user_id = $1 AND debt_type = 'gave' AND is_paid = FALSE",
            call.from_user.id
        )
    if not debts:
        await call.message.edit_text("💸 Berilgan qarz yo'q.", reply_markup=debt_menu())
        return
    text = "💸 *Men bergan qarzlar:*\n\n"
    buttons = []
    total = 0
    for d in debts:
        text += f"👤 {d['person_name']}: {d['amount']:,.0f} so'm\n"
        total += d["amount"]
        buttons.append([InlineKeyboardButton(text=f"✅ {d['person_name']} qaytardi", callback_data=f"debt_pay_{d['id']}")])
    text += f"\n💰 Jami: {total:,.0f} so'm"
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="debt_menu")])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@debt_router.callback_query(F.data.startswith("debt_took_list"))
async def debt_took_list(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        debts = await conn.fetch(
            "SELECT * FROM debts WHERE user_id = $1 AND debt_type = 'took' AND is_paid = FALSE",
            call.from_user.id
        )
    if not debts:
        await call.message.edit_text("💰 Olingan qarz yo'q.", reply_markup=debt_menu())
        return
    text = "💰 *Menga berilgan qarzlar:*\n\n"
    buttons = []
    total = 0
    for d in debts:
        text += f"👤 {d['person_name']}: {d['amount']:,.0f} so'm\n"
        total += d["amount"]
        buttons.append([InlineKeyboardButton(text=f"✅ {d['person_name']}ga qaytardim", callback_data=f"debt_pay_{d['id']}")])
    text += f"\n💰 Jami: {total:,.0f} so'm"
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="debt_menu")])
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@debt_router.callback_query(F.data.startswith("debt_pay_"))
async def debt_pay(call: CallbackQuery):
    debt_id = int(call.data.replace("debt_pay_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        debt = await conn.fetchrow("SELECT * FROM debts WHERE id = $1", debt_id)
        await conn.execute("UPDATE debts SET is_paid = TRUE WHERE id = $1", debt_id)
    await add_points(call.from_user.id, POINTS["debt_paid"], "Qarz to'landi")
    await call.answer(f"✅ {debt['person_name']} qarz to'landi! +{POINTS['debt_paid']} bal")
    await debt_menu_handler(call, None)


# ============ ACHIEVEMENTS ============
achievements_router = Router()

ACHIEVEMENT_LIST = [
    {"id": "first_goal", "title": "Birinchi qadam", "desc": "Birinchi maqsad qo'yildi", "emoji": "🎯"},
    {"id": "week_prayers", "title": "Ibodat qiluvchi", "desc": "7 kun ketma-ket namoz", "emoji": "🕌"},
    {"id": "streak_7", "title": "7 kunlik chempion", "desc": "7 kun ketma-ket odat", "emoji": "🔥"},
    {"id": "streak_30", "title": "Oylik chempion", "desc": "30 kun ketma-ket odat", "emoji": "👑"},
    {"id": "points_100", "title": "100 balchi", "desc": "100 bal to'plandi", "emoji": "⭐"},
    {"id": "points_1000", "title": "Ming balchi", "desc": "1000 bal to'plandi", "emoji": "🌟"},
    {"id": "pomodoro_10", "title": "Fokus ustasi", "desc": "10 pomodoro sessiya", "emoji": "⏱"},
    {"id": "journal_7", "title": "Yozuvchi", "desc": "7 kun kundalik", "emoji": "📝"},
]

@achievements_router.callback_query(F.data == "achievements_menu")
async def achievements_menu_handler(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        earned = await conn.fetch("SELECT title FROM achievements WHERE user_id = $1", call.from_user.id)
        user = await conn.fetchrow("SELECT total_points FROM users WHERE user_id = $1", call.from_user.id)

    earned_titles = [e["title"] for e in earned]
    text = f"🏆 *Yutuqlar*\n\n🌟 Jami ballar: *{user['total_points']}*\n\n"

    for a in ACHIEVEMENT_LIST:
        status = "✅" if a["title"] in earned_titles else "🔒"
        text += f"{status} {a['emoji']} *{a['title']}*\n_{a['desc']}_\n\n"

    await call.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")]
        ])
    )


# ============ SETTINGS ============
settings_router = Router()

def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Takrorlash soni", callback_data="set_repeat")],
        [InlineKeyboardButton(text="⏱ Takror oralig'i", callback_data="set_interval")],
        [InlineKeyboardButton(text="🕌 Namoz eslatmalari", callback_data="set_prayer_remind")],
        [InlineKeyboardButton(text="📋 Vazifa eslatmalari", callback_data="set_task_remind")],
        [InlineKeyboardButton(text="🌅 Ertalabki vaqt", callback_data="set_morning")],
        [InlineKeyboardButton(text="🌙 Kechki vaqt", callback_data="set_evening")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

@settings_router.callback_query(F.data == "settings_menu")
async def settings_menu_handler(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    text = (f"⚙️ *Sozlamalar*\n\n"
            f"🔁 Takrorlash: {user['reminder_repeat']} marta\n"
            f"⏱ Oraliq: {user['reminder_interval']} daqiqa\n"
            f"🕌 Namoz eslatma: {'✅' if user['prayer_reminders'] else '❌'}\n"
            f"📋 Vazifa eslatma: {'✅' if user['task_reminders'] else '❌'}\n"
            f"🌅 Ertalabki: {user['morning_time']}\n"
            f"🌙 Kechki: {user['evening_time']}\n")
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=settings_menu())

@settings_router.callback_query(F.data == "set_repeat")
async def set_repeat(call: CallbackQuery):
    await call.message.edit_text(
        "🔁 *Necha marta eslatsin?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 marta", callback_data="repeat_1"),
             InlineKeyboardButton(text="2 marta", callback_data="repeat_2"),
             InlineKeyboardButton(text="3 marta", callback_data="repeat_3")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="settings_menu")],
        ])
    )

@settings_router.callback_query(F.data.startswith("repeat_"))
async def set_repeat_value(call: CallbackQuery):
    from database import update_user
    value = int(call.data.replace("repeat_", ""))
    await update_user(call.from_user.id, reminder_repeat=value)
    await call.answer(f"✅ {value} marta eslatish o'rnatildi")
    await settings_menu_handler(call)

@settings_router.callback_query(F.data == "set_prayer_remind")
async def toggle_prayer_remind(call: CallbackQuery):
    from database import update_user
    user = await get_user(call.from_user.id)
    new_val = not user["prayer_reminders"]
    await update_user(call.from_user.id, prayer_reminders=new_val)
    await call.answer(f"{'✅ Yoqildi' if new_val else '❌ O\'chirildi'}")
    await settings_menu_handler(call)

@settings_router.callback_query(F.data == "set_task_remind")
async def toggle_task_remind(call: CallbackQuery):
    from database import update_user
    user = await get_user(call.from_user.id)
    new_val = not user["task_reminders"]
    await update_user(call.from_user.id, task_reminders=new_val)
    await call.answer(f"{'✅ Yoqildi' if new_val else '❌ O\'chirildi'}")
    await settings_menu_handler(call)


# ============ ROUTINE ============
routine_router = Router()

@routine_router.callback_query(F.data == "routine_menu")
async def routine_menu_handler(call: CallbackQuery):
    await call.message.edit_text(
        "🌅 *Kunlik Routin*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌅 Ertalabki routin", callback_data="morning_routine")],
            [InlineKeyboardButton(text="🌙 Kechki tahlil", callback_data="evening_routine")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
        ])
    )

@routine_router.callback_query(F.data == "morning_routine")
async def morning_routine(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        goals_today = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2",
            call.from_user.id, date.today()
        )
    text = (f"🌅 *Xayrli tong!*\n\n"
            f"Yangi kun — yangi imkoniyat! 💪\n\n"
            f"📋 Bugungi rejalaringiz: {goals_today} ta\n\n"
            f"Bugun ham barcha maqsadlaringizga erishishingizni tilayaman! 🎯")
    await add_points(call.from_user.id, POINTS["morning_routine"], "Ertalabki routin bajarildi")
    await call.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Reja qo'shish", callback_data="daily_plan_menu")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
        ])
    )

@routine_router.callback_query(F.data == "evening_routine")
async def evening_routine(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        done = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2 AND is_completed = TRUE",
            call.from_user.id, date.today()
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2",
            call.from_user.id, date.today()
        )
        prayers_done = await conn.fetchval(
            "SELECT COUNT(*) FROM prayers WHERE user_id = $1 AND prayer_date = $2 AND is_done = TRUE",
            call.from_user.id, date.today()
        )
    pct = int(done / total * 100) if total > 0 else 0
    text = (f"🌙 *Kechki tahlil*\n\n"
            f"📋 Rejalar: {done}/{total} ({pct}%)\n"
            f"🕌 Namozlar: {prayers_done}/5\n\n"
            f"{'🎉 Ajoyib kun!' if pct >= 80 else '💪 Ertaga yanada yaxshiroq bo\'ladi!'}\n\n"
            f"Uxlashdan oldin shukrona aiting 🤲")
    await add_points(call.from_user.id, POINTS["evening_routine"], "Kechki tahlil bajarildi")
    await call.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤲 Shukronalik", callback_data="gratitude_menu")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
        ])
    )


# ============ PROFILE ============
profile_router = Router()

class ProfileStates(StatesGroup):
    waiting_name = State()

@profile_router.callback_query(F.data == "profile_menu")
async def profile_menu_handler(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    p = await get_pool()
    async with p.acquire() as conn:
        goals_count = await conn.fetchval("SELECT COUNT(*) FROM goals WHERE user_id = $1 AND is_completed = TRUE", call.from_user.id)
        habits_count = await conn.fetchval("SELECT COUNT(*) FROM habits WHERE user_id = $1", call.from_user.id)

    text = (f"👤 *Profil*\n\n"
            f"📛 Ism: {user['full_name'] or 'Noma\\'lum'}\n"
            f"📍 Shahar: {user['region'] or 'Ko\\'rsatilmagan'}\n"
            f"🌟 Jami ballar: {user['total_points']}\n"
            f"🎯 Bajarilgan maqsadlar: {goals_count}\n"
            f"✅ Faol odatlar: {habits_count}\n"
            f"📅 A'zo bo'lgan: {user['created_at'].strftime('%d.%m.%Y')}\n")

    await call.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="profile_edit_name")],
            [InlineKeyboardButton(text="📍 Shaharni o'zgartirish", callback_data="prayer_change_city")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
        ])
    )

@profile_router.callback_query(F.data == "profile_edit_name")
async def profile_edit_name(call: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.waiting_name)
    await call.message.edit_text("✏️ Yangi ismingizni yozing:")

@profile_router.message(ProfileStates.waiting_name)
async def profile_save_name(message: Message, state: FSMContext):
    from database import update_user
    await update_user(message.from_user.id, full_name=message.text)
    await state.clear()
    await message.answer(f"✅ Ism yangilandi: *{message.text}*", parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="👤 Profilga qaytish", callback_data="profile_menu")]
                         ]))


# ============ GROUP ============
group_router = Router()

@group_router.callback_query(F.data == "group_menu")
async def group_menu_handler(call: CallbackQuery):
    await call.message.edit_text(
        "👨‍👩‍👧 *Guruh / Oila Rejimi*\n\nBotni guruhga qo'shing va do'stlar bilan raqobatlashing!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Guruh reytingi", callback_data="group_leaderboard")],
            [InlineKeyboardButton(text="ℹ️ Qanday qo'shish", callback_data="group_howto")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
        ])
    )

@group_router.callback_query(F.data == "group_howto")
async def group_howto(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ *Guruhga qo'shish:*\n\n"
        "1. Botni guruhingizga qo'shing\n"
        "2. Guruhda /start buyrug'ini yuboring\n"
        "3. Har bir a'zo o'z profilidagi ballar guruh reytingiga qo'shiladi\n"
        "4. Har hafta payshanba kuni natijalar e'lon qilinadi 🏆",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="group_menu")]
        ])
    )

@group_router.message(F.text == "/start", F.chat.type.in_({"group", "supergroup"}))
async def group_start(message: Message):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO groups (group_id, group_name) VALUES ($1, $2) ON CONFLICT (group_id) DO NOTHING",
            message.chat.id, message.chat.title
        )
        await conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            message.chat.id, message.from_user.id
        )
    await message.answer(
        f"✅ Bot guruhga qo'shildi!\n\n"
        f"Har hafta payshanba kuni reyting e'lon qilinadi 🏆\n"
        f"Ballar to'plang va yuting! 💪"
    )

@group_router.callback_query(F.data == "group_leaderboard")
async def group_leaderboard(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        members = await conn.fetch(
            """SELECT u.full_name, u.username, u.total_points 
               FROM group_members gm 
               JOIN users u ON gm.user_id = u.user_id
               WHERE gm.group_id IN (SELECT group_id FROM group_members WHERE user_id = $1)
               ORDER BY u.total_points DESC LIMIT 10""",
            call.from_user.id
        )

    if not members:
        await call.message.edit_text(
            "📊 Guruh topilmadi.\n\nBotni guruhga qo'shing!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="group_menu")]
            ])
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Guruh reytingi:*\n\n"
    for i, m in enumerate(members):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = m["full_name"] or m["username"] or "Noma'lum"
        text += f"{medal} {name} — *{m['total_points']}* bal\n"

    await call.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="group_menu")]
        ])
    )
