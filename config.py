import os

# Bot Token - @BotFather dan oling
BOT_TOKEN = os.getenv("BOT_TOKEN", "8162519981:AAFznA3-OTIce4P3GcoOK_jQR3DKnoJOaQM")

# Gemini API Key - aistudio.google.com dan oling
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAgZw4zUnUCdXm44KnTsZ19KnaSTHqrRYk")

# PostgreSQL Database URL - Railway avtomatik beradi
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:IAfUPZIODlSbMCnPBngAIjFWMJsTENWz@reseau.proxy.rlwy.net:21781/railway")

# Namoz vaqtlari API
PRAYER_API_URL = "https://api.aladhan.com/v1/timingsByCity"

# Bal tizimi
POINTS = {
    "prayer": 10,
    "daily_plan": 5,
    "goal": 15,
    "debt_paid": 10,
    "pomodoro": 5,
    "habit": 3,
    "journal": 3,
    "idea": 2,
    "brain_exercise": 5,
    "morning_routine": 8,
    "evening_routine": 8,
}

PENALTY_POINTS = {
    "missed_prayer": -2,
    "missed_plan": -1,
    "missed_habit": -1,
}

# Uzbekiston viloyatlari
UZBEKISTAN_REGIONS = {
    "Toshkent shahri": "Tashkent",
    "Toshkent viloyati": "Tashkent",
    "Samarqand": "Samarkand",
    "Buxoro": "Bukhara",
    "Andijon": "Andijan",
    "Farg'ona": "Fergana",
    "Namangan": "Namangan",
    "Qashqadaryo": "Kashkadarya",
    "Surxondaryo": "Surkhandarya",
    "Xorazm": "Khorezm",
    "Navoiy": "Navoi",
    "Jizzax": "Jizzakh",
    "Sirdaryo": "Syrdarya",
    "Qoraqalpog'iston": "Karakalpakstan",
}
