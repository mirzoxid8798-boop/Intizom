from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points, get_user, update_user
from config import POINTS, UZBEKISTAN_REGIONS
import aiohttp
from datetime import datetime, date

router = Router()

PRAYER_NAMES = {
    "Fajr": "🌙 Bomdod",
    "Sunrise": "🌅 Quyosh",
    "Dhuhr": "☀️ Peshin",
    "Asr": "🌤 Asr",
    "Maghrib": "🌆 Shom",
    "Isha": "🌙 Xufton"
}

class PrayerStates(StatesGroup):
    waiting_location_type = State()
    waiting_region = State()
    waiting_city = State()

def prayer_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕌 Bugungi namoz vaqtlari", callback_data="prayer_today")],
        [InlineKeyboardButton(text="✅ Namoz belgilash", callback_data="prayer_mark")],
        [InlineKeyboardButton(text="📊 Namoz statistikasi", callback_data="prayer_stats")],
        [InlineKeyboardButton(text="📿 Tasbeh", callback_data="tasbeh_menu")],
        [InlineKeyboardButton(text="🤲 Shukronalik", callback_data="gratitude_menu")],
        [InlineKeyboardButton(text="📍 Shahar o'zgartirish", callback_data="prayer_change_city")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

async def get_prayer_times(city: str, country: str = "Uzbekistan"):
    url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method=3"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get("code") == 200:
                return data["data"]["timings"]
    return None

@router.callback_query(F.data == "prayer_menu")
async def prayer_menu_handler(call: CallbackQuery):
    await call.message.edit_text(
        "🕌 *Ibodat bo'limi*\n\nNamoz, tasbeh va shukronalik",
        parse_mode="Markdown",
        reply_markup=prayer_menu()
    )

@router.callback_query(F.data == "prayer_today")
async def prayer_today(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    city = user["city"] if user else "Tashkent"
    timings = await get_prayer_times(city)
    if not timings:
        await call.message.edit_text("❌ Namoz vaqtlarini olishda xatolik. Keyinroq urinib ko'ring.")
        return

    today = datetime.now().strftime("%d.%m.%Y")
    text = f"🕌 *Namoz vaqtlari — {city}*\n📅 {today}\n\n"
    for key, name in PRAYER_NAMES.items():
        if key in timings and key != "Sunrise":
            text += f"{name}: `{timings[key]}`\n"

    p = await get_pool()
    async with p.acquire() as conn:
        prayers_today = await conn.fetch(
            "SELECT * FROM prayers WHERE user_id = $1 AND prayer_date = $2",
            call.from_user.id, date.today()
        )
        done_prayers = [p["prayer_name"] for p in prayers_today if p["is_done"]]

    text += "\n*Bugungi holat:*\n"
    prayer_list = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    for p_name in prayer_list:
        status = "✅" if p_name in done_prayers else "⭕"
        text += f"{status} {PRAYER_NAMES.get(p_name, p_name)}\n"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=prayer_menu())

@router.callback_query(F.data == "prayer_mark")
async def prayer_mark(call: CallbackQuery):
    prayer_list = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    p = await get_pool()
    async with p.acquire() as conn:
        prayers_today = await conn.fetch(
            "SELECT * FROM prayers WHERE user_id = $1 AND prayer_date = $2",
            call.from_user.id, date.today()
        )
        done_prayers = [pr["prayer_name"] for pr in prayers_today if pr["is_done"]]

    buttons = []
    for p_name in prayer_list:
        status = "✅" if p_name in done_prayers else "⭕"
        buttons.append([InlineKeyboardButton(
            text=f"{status} {PRAYER_NAMES.get(p_name, p_name)}",
            callback_data=f"prayer_toggle_{p_name}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")])

    await call.message.edit_text(
        "🕌 *Namoz belgilash*\n\nBajargan namozing ustiga bosing:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("prayer_toggle_"))
async def prayer_toggle(call: CallbackQuery):
    prayer_name = call.data.replace("prayer_toggle_", "")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM prayers WHERE user_id = $1 AND prayer_name = $2 AND prayer_date = $3",
            call.from_user.id, prayer_name, date.today()
        )
        if existing:
            new_status = not existing["is_done"]
            await conn.execute(
                "UPDATE prayers SET is_done = $1 WHERE id = $2",
                new_status, existing["id"]
            )
            if new_status:
                await add_points(call.from_user.id, POINTS["prayer"], f"{prayer_name} namozi o'qildi")
                await call.answer(f"✅ {PRAYER_NAMES.get(prayer_name)} — bajarildi! +{POINTS['prayer']} bal 🌟")
            else:
                await call.answer(f"⭕ {PRAYER_NAMES.get(prayer_name)} — bekor qilindi")
        else:
            await conn.execute(
                "INSERT INTO prayers (user_id, prayer_name, is_done) VALUES ($1, $2, TRUE)",
                call.from_user.id, prayer_name
            )
            await add_points(call.from_user.id, POINTS["prayer"], f"{prayer_name} namozi o'qildi")
            await call.answer(f"✅ {PRAYER_NAMES.get(prayer_name)} — bajarildi! +{POINTS['prayer']} bal 🌟")

    await prayer_mark(call)

@router.callback_query(F.data == "prayer_stats")
async def prayer_stats(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        week_stats = await conn.fetch(
            """SELECT prayer_name, COUNT(*) as total, 
               SUM(CASE WHEN is_done THEN 1 ELSE 0 END) as done
               FROM prayers WHERE user_id = $1 
               AND prayer_date >= CURRENT_DATE - INTERVAL '7 days'
               GROUP BY prayer_name""",
            call.from_user.id
        )

    text = "📊 *Haftalik namoz statistikasi*\n\n"
    total_possible = 35
    total_done = 0
    for stat in week_stats:
        done = stat["done"] or 0
        total_done += done
        bar = "█" * done + "░" * (7 - done)
        text += f"{PRAYER_NAMES.get(stat['prayer_name'], stat['prayer_name'])}\n"
        text += f"`{bar}` {done}/7\n\n"

    percentage = int((total_done / total_possible) * 100) if total_possible > 0 else 0
    text += f"📈 Jami: {total_done}/{total_possible} ({percentage}%)"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=prayer_menu())

@router.callback_query(F.data == "prayer_change_city")
async def prayer_change_city(call: CallbackQuery, state: FSMContext):
    regions = list(UZBEKISTAN_REGIONS.keys())
    buttons = [[InlineKeyboardButton(text=r, callback_data=f"region_{r}")] for r in regions]
    buttons.append([InlineKeyboardButton(text="📍 Joylashuvimni yuborish", callback_data="prayer_location")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")])

    await call.message.edit_text(
        "📍 *Viloyatingizni tanlang:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("region_"))
async def region_selected(call: CallbackQuery):
    region = call.data.replace("region_", "")
    city = UZBEKISTAN_REGIONS.get(region, "Tashkent")
    await update_user(call.from_user.id, city=city, region=region)
    await call.message.edit_text(
        f"✅ Shahar yangilandi: *{region}*\n\nEndi namoz vaqtlari shu shaharga ko'ra ko'rsatiladi.",
        parse_mode="Markdown",
        reply_markup=prayer_menu()
    )

# Tasbeh
@router.callback_query(F.data == "tasbeh_menu")
async def tasbeh_menu(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        tasbeh = await conn.fetchrow(
            "SELECT * FROM tasbeh WHERE user_id = $1 AND log_date = $2",
            call.from_user.id, date.today()
        )

    if not tasbeh:
        buttons = [
            [InlineKeyboardButton(text="SubhanAllah (33)", callback_data="tasbeh_start_SubhanAllah_33")],
            [InlineKeyboardButton(text="Alhamdulillah (33)", callback_data="tasbeh_start_Alhamdulillah_33")],
            [InlineKeyboardButton(text="Allahu Akbar (33)", callback_data="tasbeh_start_AllahuAkbar_33")],
            [InlineKeyboardButton(text="✏️ O'z tasbehi", callback_data="tasbeh_custom")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")],
        ]
        await call.message.edit_text(
            "📿 *Tasbeh*\n\nQaysi tasbehni hisoblaysiz?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    else:
        remaining = tasbeh["target_count"] - tasbeh["current_count"]
        progress = "█" * min(tasbeh["current_count"] // 3, 10) + "░" * max(10 - tasbeh["current_count"] // 3, 0)
        await call.message.edit_text(
            f"📿 *{tasbeh['text']}*\n\n`{progress}`\n\n"
            f"Hozir: *{tasbeh['current_count']}* / {tasbeh['target_count']}\n"
            f"Qoldi: {remaining}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📿 +1", callback_data=f"tasbeh_count_{tasbeh['id']}")],
                [InlineKeyboardButton(text="🔄 Yangi tasbeh", callback_data="tasbeh_new")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")],
            ])
        )

@router.callback_query(F.data.startswith("tasbeh_start_"))
async def tasbeh_start(call: CallbackQuery):
    parts = call.data.replace("tasbeh_start_", "").split("_")
    text = parts[0]
    target = int(parts[1])
    p = await get_pool()
    async with p.acquire() as conn:
        result = await conn.fetchrow(
            "INSERT INTO tasbeh (user_id, text, target_count, current_count) VALUES ($1, $2, $3, 0) RETURNING id",
            call.from_user.id, text, target
        )
    await call.message.edit_text(
        f"📿 *{text}*\n\n`░░░░░░░░░░`\n\nHozir: *0* / {target}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📿 +1", callback_data=f"tasbeh_count_{result['id']}")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")],
        ])
    )

@router.callback_query(F.data.startswith("tasbeh_count_"))
async def tasbeh_count(call: CallbackQuery):
    tasbeh_id = int(call.data.replace("tasbeh_count_", ""))
    p = await get_pool()
    async with p.acquire() as conn:
        tasbeh = await conn.fetchrow(
            "UPDATE tasbeh SET current_count = current_count + 1 WHERE id = $1 RETURNING *",
            tasbeh_id
        )

    if tasbeh["current_count"] >= tasbeh["target_count"]:
        await add_points(call.from_user.id, 5, "Tasbeh tugallandi")
        await call.message.edit_text(
            f"🎉 *Mashallah! Tasbeh tugallandi!*\n\n"
            f"📿 {tasbeh['text']} — {tasbeh['target_count']} marta\n\n"
            f"+5 bal oldiniz! 🌟",
            parse_mode="Markdown",
            reply_markup=prayer_menu()
        )
    else:
        remaining = tasbeh["target_count"] - tasbeh["current_count"]
        filled = min(tasbeh["current_count"] * 10 // tasbeh["target_count"], 10)
        progress = "█" * filled + "░" * (10 - filled)
        await call.message.edit_text(
            f"📿 *{tasbeh['text']}*\n\n`{progress}`\n\n"
            f"Hozir: *{tasbeh['current_count']}* / {tasbeh['target_count']}\n"
            f"Qoldi: {remaining}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"📿 +1 ({tasbeh['current_count']})", callback_data=f"tasbeh_count_{tasbeh_id}")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="prayer_menu")],
            ])
        )

# Shukronalik
@router.callback_query(F.data == "gratitude_menu")
async def gratitude_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state("gratitude_writing")
    await call.message.edit_text(
        "🤲 *Shukronalik*\n\nBugun nimalarga shukr qilasiz?\n\nYozing (masalan: 'Sog'ligim uchun shukr'):",
        parse_mode="Markdown"
    )

@router.message(F.text, flags={"state": "gratitude_writing"})
async def save_gratitude(message: Message, state: FSMContext):
    current = await state.get_state()
    if current != "gratitude_writing":
        return
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO gratitude (user_id, content) VALUES ($1, $2)",
            message.from_user.id, message.text
        )
    await add_points(message.from_user.id, 3, "Shukronalik yozildi")
    await state.clear()
    await message.answer(
        "🤲 *Shukronaligingiz saqlandi!*\n\nAlloh barchangizdan rozi bo'lsin 🌹\n+3 bal oldiniz!",
        parse_mode="Markdown",
        reply_markup=prayer_menu()
    )
