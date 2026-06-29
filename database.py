import asyncpg
import asyncio
from config import DATABASE_URL
from datetime import datetime, date

pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                city TEXT DEFAULT 'Tashkent',
                region TEXT DEFAULT 'Toshkent shahri',
                latitude FLOAT,
                longitude FLOAT,
                reminder_repeat INTEGER DEFAULT 2,
                reminder_interval INTEGER DEFAULT 10,
                prayer_reminders BOOLEAN DEFAULT TRUE,
                task_reminders BOOLEAN DEFAULT TRUE,
                morning_time TEXT DEFAULT '07:00',
                evening_time TEXT DEFAULT '21:00',
                language TEXT DEFAULT 'uz',
                total_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS goals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                description TEXT,
                goal_type TEXT DEFAULT 'daily',
                deadline DATE,
                is_completed BOOLEAN DEFAULT FALSE,
                points_reward INTEGER DEFAULT 15,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS daily_plans (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                plan_date DATE DEFAULT CURRENT_DATE,
                scheduled_time TEXT,
                is_completed BOOLEAN DEFAULT FALSE,
                reminder_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                remind_at TIMESTAMP NOT NULL,
                is_sent BOOLEAN DEFAULT FALSE,
                is_done BOOLEAN DEFAULT FALSE,
                reminder_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS habits (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                emoji TEXT DEFAULT '✅',
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS habit_logs (
                id SERIAL PRIMARY KEY,
                habit_id INTEGER REFERENCES habits(id),
                user_id BIGINT REFERENCES users(user_id),
                log_date DATE DEFAULT CURRENT_DATE,
                is_done BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS prayers (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                prayer_name TEXT NOT NULL,
                prayer_date DATE DEFAULT CURRENT_DATE,
                is_done BOOLEAN DEFAULT FALSE,
                reminder_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tasbeh (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                text TEXT NOT NULL,
                target_count INTEGER DEFAULT 33,
                current_count INTEGER DEFAULT 0,
                log_date DATE DEFAULT CURRENT_DATE
            );

            CREATE TABLE IF NOT EXISTS gratitude (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS debts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                person_name TEXT NOT NULL,
                amount FLOAT NOT NULL,
                currency TEXT DEFAULT 'UZS',
                debt_type TEXT DEFAULT 'gave',
                description TEXT,
                due_date DATE,
                is_paid BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS journal (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                content TEXT NOT NULL,
                mood TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS ideas (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                content TEXT,
                category TEXT DEFAULT 'Umumiy',
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                task_name TEXT,
                duration_minutes INTEGER DEFAULT 25,
                is_completed BOOLEAN DEFAULT FALSE,
                started_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                title TEXT NOT NULL,
                description TEXT,
                emoji TEXT DEFAULT '🏆',
                earned_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS points_log (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                points INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS groups (
                id SERIAL PRIMARY KEY,
                group_id BIGINT UNIQUE NOT NULL,
                group_name TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS group_members (
                id SERIAL PRIMARY KEY,
                group_id BIGINT REFERENCES groups(group_id),
                user_id BIGINT REFERENCES users(user_id),
                joined_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS brain_exercises (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                exercise_type TEXT NOT NULL,
                question TEXT,
                answer TEXT,
                user_answer TEXT,
                is_correct BOOLEAN,
                points_earned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
    print("✅ Database initialized!")

async def add_user(user_id: int, username: str, full_name: str):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE
            SET username = $2, full_name = $3
        """, user_id, username, full_name)

async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def update_user(user_id: int, **kwargs):
    p = await get_pool()
    async with p.acquire() as conn:
        set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(kwargs.keys())])
        values = list(kwargs.values())
        await conn.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = $1",
            user_id, *values
        )

async def add_points(user_id: int, points: int, reason: str):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET total_points = total_points + $2 WHERE user_id = $1",
            user_id, points
        )
        await conn.execute(
            "INSERT INTO points_log (user_id, points, reason) VALUES ($1, $2, $3)",
            user_id, points, reason
        )

async def get_points_stats(user_id: int, period: str = "week"):
    p = await get_pool()
    async with p.acquire() as conn:
        if period == "week":
            interval = "7 days"
        elif period == "month":
            interval = "30 days"
        else:
            interval = "365 days"
        return await conn.fetchval(
            f"SELECT COALESCE(SUM(points), 0) FROM points_log WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '{interval}'",
            user_id
        )
