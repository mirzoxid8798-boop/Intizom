import asyncio
import logging
from datetime import datetime, date, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool, get_user
from handlers.prayer import get_prayer_times

logger = logging.getLogger(__name__)

PRAYER_NAMES_UZ = {
    "Fajr": "🌙 Bomdod",
    "Dhuhr": "☀️ Peshin",
    "Asr": "🌤 Asr",
    "Maghrib": "🌆 Shom",
    "Isha": "🌙 Xufton"
}

def prayer_keyboard(prayer_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ O'qidim", callback_data=f"prayer_toggle_{prayer_name}"),
            InlineKeyboardButton(text="❌ O'qimadim", callback_data=f"prayer_snooze_{prayer_name}"),
        ]
    ])

def task_keyboard(task_id: int, task_type: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Bajardim", callback_data=f"{task_type}_done_{task_id}"),
            InlineKeyboardButton(text="❌ Bajarmadam", callback_data=f"{task_type}_snooze_{task_id}"),
        ]
    ])

async def send_prayer_reminders(bot: Bot):
    """Namoz vaqtlarida eslatma yuborish"""
    p = await get_pool()
    async with p.acquire() as conn:
        users = await conn.fetch(
            "SELECT * FROM users WHERE prayer_reminders = TRUE"
        )

    now = datetime.now()
    current_time = now.strftime("%H:%M")

    for user in users:
        try:
            city = user["city"] or "Tashkent"
            timings = await get_prayer_times(city)
            if not timings:
                continue

            for prayer_name, uz_name in PRAYER_NAMES_UZ.items():
                prayer_time = timings.get(prayer_name, "")
                if prayer_time and prayer_time == current_time:
                    # Namoz vaqti keldi
                    p2 = await get_pool()
                    async with p2.acquire() as conn2:
                        existing = await conn2.fetchrow(
                            "SELECT * FROM prayers WHERE user_id = $1 AND prayer_name = $2 AND prayer_date = $3",
                            user["user_id"], prayer_name, date.today()
                        )
                        if not existing:
                            await conn2.execute(
                                "INSERT INTO prayers (user_id, prayer_name, is_done) VALUES ($1, $2, FALSE)",
                                user["user_id"], prayer_name
                            )

                    await bot.send_message(
                        user["user_id"],
                        f"{uz_name} vaqti kirdi! 🕌\n\nNamoz o'qidingizmi?",
                        reply_markup=prayer_keyboard(prayer_name)
                    )
        except Exception as e:
            logger.error(f"Prayer reminder error for {user['user_id']}: {e}")

async def send_prayer_followup(bot: Bot):
    """O'qilmagan namozlarga takror eslatma"""
    p = await get_pool()
    async with p.acquire() as conn:
        unread_prayers = await conn.fetch(
            """SELECT pr.*, u.reminder_repeat, u.reminder_interval 
               FROM prayers pr
               JOIN users u ON pr.user_id = u.user_id
               WHERE pr.is_done = FALSE 
               AND pr.prayer_date = $1
               AND pr.reminder_count < u.reminder_repeat
               AND u.prayer_reminders = TRUE""",
            date.today()
        )

    now = datetime.now()
    for prayer in unread_prayers:
        try:
            max_repeats = prayer["reminder_repeat"] or 2
            interval = prayer["reminder_interval"] or 10
            count = prayer["reminder_count"] or 0

            if count < max_repeats:
                p2 = await get_pool()
                async with p2.acquire() as conn2:
                    await conn2.execute(
                        "UPDATE prayers SET reminder_count = reminder_count + 1 WHERE id = $1",
                        prayer["id"]
                    )

                uz_name = PRAYER_NAMES_UZ.get(prayer["prayer_name"], prayer["prayer_name"])
                repeat_text = f"({count + 1}/{max_repeats} eslatma)"

                await bot.send_message(
                    prayer["user_id"],
                    f"🔔 {repeat_text}\n\n{uz_name} namozini o'qidingizmi?",
                    reply_markup=prayer_keyboard(prayer["prayer_name"])
                )
        except Exception as e:
            logger.error(f"Prayer followup error: {e}")

async def send_reminders(bot: Bot):
    """Foydalanuvchi qo'ygan eslatmalarni yuborish"""
    p = await get_pool()
    async with p.acquire() as conn:
        due_reminders = await conn.fetch(
            """SELECT r.*, u.reminder_repeat, u.reminder_interval
               FROM reminders r
               JOIN users u ON r.user_id = u.user_id
               WHERE r.is_sent = FALSE 
               AND r.is_done = FALSE
               AND r.remind_at <= NOW()"""
        )

    for reminder in due_reminders:
        try:
            p2 = await get_pool()
            async with p2.acquire() as conn2:
                await conn2.execute(
                    "UPDATE reminders SET is_sent = TRUE WHERE id = $1",
                    reminder["id"]
                )

            await bot.send_message(
                reminder["user_id"],
                f"🔔 *Eslatma!*\n\n📌 {reminder['title']}",
                parse_mode="Markdown",
                reply_markup=task_keyboard(reminder["id"], "reminder")
            )
        except Exception as e:
            logger.error(f"Reminder send error: {e}")

async def send_reminder_followup(bot: Bot):
    """Bajarilmagan eslatmalarga takror xabar"""
    p = await get_pool()
    async with p.acquire() as conn:
        pending = await conn.fetch(
            """SELECT r.*, u.reminder_repeat, u.reminder_interval
               FROM reminders r
               JOIN users u ON r.user_id = u.user_id
               WHERE r.is_sent = TRUE
               AND r.is_done = FALSE
               AND r.reminder_count < u.reminder_repeat
               AND r.remind_at <= NOW() - (u.reminder_interval || ' minutes')::INTERVAL"""
        )

    for reminder in pending:
        try:
            count = reminder["reminder_count"] or 0
            max_repeats = reminder["reminder_repeat"] or 2

            if count < max_repeats:
                p2 = await get_pool()
                async with p2.acquire() as conn2:
                    await conn2.execute(
                        "UPDATE reminders SET reminder_count = reminder_count + 1 WHERE id = $1",
                        reminder["id"]
                    )

                repeat_text = f"({count + 1}/{max_repeats})"
                await bot.send_message(
                    reminder["user_id"],
                    f"🔔 *Eslatma* {repeat_text}\n\n📌 {reminder['title']}\n\nBajardingizmi?",
                    parse_mode="Markdown",
                    reply_markup=task_keyboard(reminder["id"], "reminder")
                )
        except Exception as e:
            logger.error(f"Reminder followup error: {e}")

async def send_plan_reminders(bot: Bot):
    """Kunlik reja eslatmalari"""
    p = await get_pool()
    async with p.acquire() as conn:
        now_time = datetime.now().strftime("%H:%M")
        plans = await conn.fetch(
            """SELECT dp.*, u.task_reminders, u.reminder_repeat, u.reminder_interval
               FROM daily_plans dp
               JOIN users u ON dp.user_id = u.user_id
               WHERE dp.plan_date = $1
               AND dp.is_completed = FALSE
               AND dp.scheduled_time = $2
               AND u.task_reminders = TRUE""",
            date.today(), now_time
        )

    for plan in plans:
        try:
            await bot.send_message(
                plan["user_id"],
                f"📋 *Kunlik reja eslatmasi!*\n\n📌 {plan['title']}\n\nBajardingizmi?",
                parse_mode="Markdown",
                reply_markup=task_keyboard(plan["id"], "plan")
            )
        except Exception as e:
            logger.error(f"Plan reminder error: {e}")

async def send_morning_routine(bot: Bot):
    """Ertalabki routin xabari"""
    p = await get_pool()
    now_time = datetime.now().strftime("%H:%M")
    async with p.acquire() as conn:
        users = await conn.fetch(
            "SELECT * FROM users WHERE morning_time = $1", now_time
        )

    for user in users:
        try:
            name = user["full_name"] or "Do'stim"
            plans_count = 0
            p2 = await get_pool()
            async with p2.acquire() as conn2:
                plans_count = await conn2.fetchval(
                    "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2",
                    user["user_id"], date.today()
                )

            await bot.send_message(
                user["user_id"],
                f"🌅 *Xayrli tong, {name}!*\n\n"
                f"Yangi kun — yangi imkoniyat! 💪\n\n"
                f"📋 Bugungi rejalar: {plans_count} ta\n\n"
                f"Bugun ham eng yaxshi versiyangiz bo'ling! 🎯",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Rejalarga o'tish", callback_data="daily_plan_menu")],
                    [InlineKeyboardButton(text="🧠 Aql charxlash", callback_data="brain_menu")],
                ])
            )
        except Exception as e:
            logger.error(f"Morning routine error: {e}")

async def send_evening_routine(bot: Bot):
    """Kechki tahlil xabari"""
    p = await get_pool()
    now_time = datetime.now().strftime("%H:%M")
    async with p.acquire() as conn:
        users = await conn.fetch(
            "SELECT * FROM users WHERE evening_time = $1", now_time
        )

    for user in users:
        try:
            p2 = await get_pool()
            async with p2.acquire() as conn2:
                done = await conn2.fetchval(
                    "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2 AND is_completed = TRUE",
                    user["user_id"], date.today()
                )
                total = await conn2.fetchval(
                    "SELECT COUNT(*) FROM daily_plans WHERE user_id = $1 AND plan_date = $2",
                    user["user_id"], date.today()
                )
                prayers_done = await conn2.fetchval(
                    "SELECT COUNT(*) FROM prayers WHERE user_id = $1 AND prayer_date = $2 AND is_done = TRUE",
                    user["user_id"], date.today()
                )

            pct = int(done / total * 100) if total > 0 else 0
            name = user["full_name"] or "Do'stim"

            await bot.send_message(
                user["user_id"],
                f"🌙 *Kechqurun xayrli bo'lsin, {name}!*\n\n"
                f"📊 *Bugungi natijalar:*\n"
                f"📋 Rejalar: {done}/{total} ({pct}%)\n"
                f"🕌 Namozlar: {prayers_done}/5\n\n"
                f"{'🎉 Ajoyib kun o\'tdingiz!' if pct >= 80 else '💪 Ertaga yanada yaxshiroq bo\'ladi!'}\n\n"
                f"Uxlashdan oldin shukrona aiting 🤲",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Statistika", callback_data="stats_menu")],
                    [InlineKeyboardButton(text="🤲 Shukronalik", callback_data="gratitude_menu")],
                ])
            )
        except Exception as e:
            logger.error(f"Evening routine error: {e}")

async def send_weekly_leaderboard(bot: Bot):
    """Har payshanba guruh reytingini yuborish"""
    if datetime.now().weekday() != 3:  # 3 = Payshanba
        return

    p = await get_pool()
    async with p.acquire() as conn:
        groups = await conn.fetch("SELECT * FROM groups")

    for group in groups:
        try:
            p2 = await get_pool()
            async with p2.acquire() as conn2:
                members = await conn2.fetch(
                    """SELECT u.full_name, u.username,
                       COALESCE(SUM(pl.points), 0) as week_points
                       FROM group_members gm
                       JOIN users u ON gm.user_id = u.user_id
                       LEFT JOIN points_log pl ON pl.user_id = u.user_id
                           AND pl.created_at >= NOW() - INTERVAL '7 days'
                       WHERE gm.group_id = $1
                       GROUP BY u.user_id, u.full_name, u.username
                       ORDER BY week_points DESC""",
                    group["group_id"]
                )

            if not members:
                continue

            medals = ["🥇", "🥈", "🥉"]
            text = "🏆 *Haftalik Reyting!*\n\n"
            for i, m in enumerate(members):
                medal = medals[i] if i < 3 else f"{i+1}."
                name = m["full_name"] or m["username"] or "Noma'lum"
                text += f"{medal} {name} — *{m['week_points']}* bal\n"

            text += "\nKelasi hafta ham davom eting! 💪"
            await bot.send_message(group["group_id"], text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")

async def check_achievements(bot: Bot):
    """Yutuqlarni tekshirish"""
    p = await get_pool()
    async with p.acquire() as conn:
        users = await conn.fetch("SELECT * FROM users")

    for user in users:
        try:
            uid = user["user_id"]
            p2 = await get_pool()
            async with p2.acquire() as conn2:
                earned = await conn2.fetch("SELECT title FROM achievements WHERE user_id = $1", uid)
                earned_titles = [e["title"] for e in earned]

                # 100 bal
                if user["total_points"] >= 100 and "100 balchi" not in earned_titles:
                    await conn2.execute(
                        "INSERT INTO achievements (user_id, title, description, emoji) VALUES ($1,$2,$3,$4)",
                        uid, "100 balchi", "100 bal to'plandi", "⭐"
                    )
                    await bot.send_message(uid, "🎉 *Yangi yutuq!*\n\n⭐ *100 balchi*\n100 bal to'pladingiz!", parse_mode="Markdown")

                # 1000 bal
                if user["total_points"] >= 1000 and "Ming balchi" not in earned_titles:
                    await conn2.execute(
                        "INSERT INTO achievements (user_id, title, description, emoji) VALUES ($1,$2,$3,$4)",
                        uid, "Ming balchi", "1000 bal to'plandi", "🌟"
                    )
                    await bot.send_message(uid, "🎉 *Yangi yutuq!*\n\n🌟 *Ming balchi*\n1000 bal to'pladingiz!", parse_mode="Markdown")

                # 7 kunlik odat
                max_streak = await conn2.fetchval(
                    "SELECT MAX(streak) FROM habits WHERE user_id = $1", uid
                )
                if (max_streak or 0) >= 7 and "7 kunlik chempion" not in earned_titles:
                    await conn2.execute(
                        "INSERT INTO achievements (user_id, title, description, emoji) VALUES ($1,$2,$3,$4)",
                        uid, "7 kunlik chempion", "7 kun ketma-ket odat", "🔥"
                    )
                    await bot.send_message(uid, "🎉 *Yangi yutuq!*\n\n🔥 *7 kunlik chempion*\n7 kun ketma-ket odat bajardingiz!", parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Achievement check error for {user['user_id']}: {e}")

async def scheduler_loop(bot: Bot):
    """Asosiy scheduler loop - har daqiqada ishga tushadi"""
    while True:
        try:
            now = datetime.now()
            minute = now.minute
            hour = now.hour

            # Har daqiqa
            await send_reminders(bot)
            await send_reminder_followup(bot)
            await send_plan_reminders(bot)
            await send_prayer_reminders(bot)
            await send_prayer_followup(bot)
            await send_morning_routine(bot)
            await send_evening_routine(bot)

            # Har soat
            if minute == 0:
                await check_achievements(bot)

            # Har payshanba 20:00 da
            if hour == 20 and minute == 0:
                await send_weekly_leaderboard(bot)

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        await asyncio.sleep(60)  # Har 60 soniyada

async def start_scheduler(bot: Bot):
    """Schedulerni ishga tushirish"""
    logger.info("✅ Scheduler ishga tushdi!")
    await scheduler_loop(bot)
