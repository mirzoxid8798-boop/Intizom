# 🤖 Intizom Bot

O'zini o'zi boshqarish va intizom shakllantirish uchun Telegram bot.

---

## 📋 Bo'limlar

- 🎯 Maqsadlar (kunlik/haftalik/oylik/yillik)
- 📅 Kunlik Reja
- 🔔 Aqlli Eslatmalar
- ✅ Odatlar + Streak
- 🕌 Ibodat (Namoz, Tasbeh, Shukronalik)
- 📊 Statistika + Tahlil
- 👤 Profil
- 💰 Qarz Daftari
- 🌅 Ertalabki Routin
- 🌙 Kechki Tahlil
- 🏆 Yutuqlar + Bal Tizimi
- 📝 Kundalik
- ⏱ Pomodoro Timer
- 💡 G'oyalar Daftarchasi
- 🧠 Aql Charxlash (Gemini AI)
- 👨‍👩‍👧 Guruh/Oila Rejimi
- ⚙️ Sozlamalar

---

## 🚀 O'rnatish

### 1. Kerakli narsalar
- Python 3.10+
- PostgreSQL database
- Telegram Bot Token (@BotFather)
- Gemini API Key (aistudio.google.com)

### 2. Fayllarni yuklab oling
```bash
# Fayllarni serverga yuklang
```

### 3. .env fayl yarating
```bash
cp .env.example .env
```
Keyin `.env` faylini oching va qiymatlarni to'ldiring:
```
BOT_TOKEN=your_token
GEMINI_API_KEY=your_key
DATABASE_URL=your_db_url
```

### 4. Kutubxonalarni o'rnating
```bash
pip install -r requirements.txt
```

### 5. Botni ishga tushiring
```bash
python main.py
```

---

## 🌐 Hostinglarda ishga tushirish

### Replit
1. Replit.com da yangi Python repl yarating
2. Barcha fayllarni yuklang
3. Replit Secrets ga o'zgaruvchilarni kiriting:
   - `BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `DATABASE_URL`
4. PostgreSQL uchun: Replit Database yoki ElephantSQL (bepul) ishlating
5. `main.py` ni ishga tushiring

### Railway
1. railway.app ga kiring
2. New Project → Deploy from GitHub
3. Variables ga kiriting:
   - `BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `DATABASE_URL` (Railway PostgreSQL qo'shing)
4. Deploy!

### VPS (Ubuntu)
```bash
# Python o'rnating
sudo apt update && sudo apt install python3 python3-pip postgresql -y

# PostgreSQL sozlang
sudo -u postgres psql -c "CREATE USER botuser WITH PASSWORD 'yourpassword';"
sudo -u postgres psql -c "CREATE DATABASE intizombot OWNER botuser;"

# .env faylni to'ldiring
DATABASE_URL=postgresql://botuser:yourpassword@localhost:5432/intizombot

# O'rnating va ishga tushiring
pip3 install -r requirements.txt
python3 main.py
```

### Bepul PostgreSQL (Barcha platformalar uchun)
ElephantSQL.com - bepul 20MB PostgreSQL:
1. elephantsql.com ga ro'yxatdan o'ting
2. Free plan yarating
3. URL ni `DATABASE_URL` ga kiriting

---

## 📁 Fayl tuzilmasi

```
bot/
├── main.py              # Asosiy ishga tushirish
├── database.py          # PostgreSQL baza
├── config.py            # Konfiguratsiya
├── scheduler.py         # Avtomatik eslatmalar
├── requirements.txt     # Kutubxonalar
├── .env.example         # .env namunasi
└── handlers/
    ├── goals.py         # Maqsadlar
    ├── daily_plan.py    # Kunlik reja
    ├── reminders.py     # Eslatmalar
    ├── habits.py        # Odatlar
    ├── prayer.py        # Namoz + Tasbeh
    ├── brain.py         # Aql charxlash
    └── other.py         # Qolgan barcha bo'limlar
```

---

## ⚙️ Muhim sozlamalar

**config.py** da sozlash mumkin:
- Ballar miqdori
- Viloyatlar ro'yxati
- Namoz API manzili

**.env** da sozlash kerak:
- BOT_TOKEN
- GEMINI_API_KEY  
- DATABASE_URL
