from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_pool, add_points
from config import GEMINI_API_KEY
import aiohttp
import json
import random

router = Router()

class BrainStates(StatesGroup):
    waiting_answer = State()
    word_chain = State()
    word_build = State()

EXERCISE_TYPES = {
    "math": "🔢 Matematik misol",
    "word_en": "🌍 Inglizcha so'z",
    "fact": "💡 Qiziqarli fakt",
    "quiz": "❓ Savol-javob",
    "word_chain": "🔤 Oxirgi harfga so'z",
    "word_build": "🧩 Harflardan so'z",
}

def brain_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Matematik misol", callback_data="brain_math")],
        [InlineKeyboardButton(text="🌍 Inglizcha so'z o'rgan", callback_data="brain_word_en")],
        [InlineKeyboardButton(text="💡 Bugungi fakt", callback_data="brain_fact")],
        [InlineKeyboardButton(text="❓ Savol-javob", callback_data="brain_quiz")],
        [InlineKeyboardButton(text="🔤 Oxirgi harfga so'z", callback_data="brain_word_chain")],
        [InlineKeyboardButton(text="🧩 Harflardan so'z yasat", callback_data="brain_word_build")],
        [InlineKeyboardButton(text="📊 Mening natijalarim", callback_data="brain_stats")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="main_menu")],
    ])

async def ask_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 300}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except:
                return None

@router.callback_query(F.data == "brain_menu")
async def brain_menu_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🧠 *Aql Charxlash*\n\nHar kuni miyangizni mashq qildiring! 💪",
        parse_mode="Markdown",
        reply_markup=brain_menu()
    )

@router.callback_query(F.data == "brain_math")
async def brain_math(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("⏳ Misol tayyorlanmoqda...")
    prompt = """O'zbek tilida bir matematika masalasini ber. 
    Qiyinlik: o'rta daraja (qo'shish, ayirish, ko'paytirish, bo'lish, ulushlar).
    Faqat quyidagi formatda yoz:
    SAVOL: [savol]
    JAVOB: [faqat raqam yoki qisqa javob]
    Boshqa hech narsa yozma."""
    
    result = await ask_gemini(prompt)
    if not result:
        await call.message.edit_text("❌ Xatolik yuz berdi. Qayta urinib ko'ring.", reply_markup=brain_menu())
        return

    lines = result.strip().split("\n")
    question = ""
    answer = ""
    for line in lines:
        if line.startswith("SAVOL:"):
            question = line.replace("SAVOL:", "").strip()
        elif line.startswith("JAVOB:"):
            answer = line.replace("JAVOB:", "").strip()

    p = await get_pool()
    async with p.acquire() as conn:
        record = await conn.fetchrow(
            "INSERT INTO brain_exercises (user_id, exercise_type, question, answer) VALUES ($1, 'math', $2, $3) RETURNING id",
            call.from_user.id, question, answer
        )

    await state.update_data(exercise_id=record["id"], answer=answer, exercise_type="math")
    await state.set_state(BrainStates.waiting_answer)
    await call.message.edit_text(
        f"🔢 *Matematik misol:*\n\n{question}\n\nJavobingizni yozing:",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "brain_word_en")
async def brain_word_en(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("⏳ So'z tayyorlanmoqda...")
    prompt = """O'rta qiyinlikdagi bitta inglizcha so'z ber va uning o'zbek tilidagi ma'nosini tushuntir.
    Format:
    SO'Z: [inglizcha so'z]
    TALAFFUZ: [fonetik talaffuz]
    MA'NO: [o'zbekcha ma'no]
    MISOL: [inglizcha misol jumla]
    TARJIMA: [misolning o'zbek tarjimasi]
    Boshqa hech narsa yozma."""

    result = await ask_gemini(prompt)
    if not result:
        await call.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=brain_menu())
        return

    await add_points(call.from_user.id, POINTS_BRAIN := 3, "Inglizcha so'z o'rgandi")
    await call.message.edit_text(
        f"🌍 *Bugungi inglizcha so'z:*\n\n{result}\n\n+3 bal oldiniz! 🌟",
        parse_mode="Markdown",
        reply_markup=brain_menu()
    )

POINTS_BRAIN = 3

@router.callback_query(F.data == "brain_fact")
async def brain_fact(call: CallbackQuery):
    await call.message.edit_text("⏳ Fakt izlanmoqda...")
    categories = ["ilm-fan", "tarix", "tabiat", "texnologiya", "inson tanasi", "kosmik", "hayvonlar"]
    category = random.choice(categories)
    prompt = f"""O'zbek tilida {category} haqida bitta qiziqarli, kam ma'lum fakt ayt.
    Faqat faktni yoz, 2-3 jumlada. Boshqa hech narsa qo'shma."""

    result = await ask_gemini(prompt)
    if not result:
        await call.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=brain_menu())
        return

    await add_points(call.from_user.id, 2, "Yangi fakt o'qildi")
    await call.message.edit_text(
        f"💡 *Bugungi qiziqarli fakt ({category}):*\n\n{result}\n\n+2 bal oldiniz! 🌟",
        parse_mode="Markdown",
        reply_markup=brain_menu()
    )

@router.callback_query(F.data == "brain_quiz")
async def brain_quiz(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("⏳ Savol tayyorlanmoqda...")
    topics = ["geografiya", "tarix", "fan", "sport", "madaniyat", "texnologiya"]
    topic = random.choice(topics)
    prompt = f"""O'zbek tilida {topic} bo'yicha bitta qiziqarli savol va javob ber.
    Format:
    SAVOL: [savol]
    JAVOB: [qisqa javob]
    IZOH: [qo'shimcha ma'lumot, 1 jumla]
    Boshqa hech narsa yozma."""

    result = await ask_gemini(prompt)
    if not result:
        await call.message.edit_text("❌ Xatolik. Qayta urinib ko'ring.", reply_markup=brain_menu())
        return

    lines = result.strip().split("\n")
    question, answer, explanation = "", "", ""
    for line in lines:
        if line.startswith("SAVOL:"):
            question = line.replace("SAVOL:", "").strip()
        elif line.startswith("JAVOB:"):
            answer = line.replace("JAVOB:", "").strip()
        elif line.startswith("IZOH:"):
            explanation = line.replace("IZOH:", "").strip()

    p = await get_pool()
    async with p.acquire() as conn:
        record = await conn.fetchrow(
            "INSERT INTO brain_exercises (user_id, exercise_type, question, answer) VALUES ($1, 'quiz', $2, $3) RETURNING id",
            call.from_user.id, question, answer
        )

    await state.update_data(exercise_id=record["id"], answer=answer, explanation=explanation, exercise_type="quiz")
    await state.set_state(BrainStates.waiting_answer)
    await call.message.edit_text(
        f"❓ *{topic.capitalize()} bo'yicha savol:*\n\n{question}\n\nJavobingizni yozing:",
        parse_mode="Markdown"
    )

@router.message(BrainStates.waiting_answer)
async def check_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    user_answer = message.text.strip().lower()
    correct_answer = data.get("answer", "").lower()
    exercise_id = data.get("exercise_id")
    explanation = data.get("explanation", "")

    is_correct = user_answer in correct_answer or correct_answer in user_answer

    p = await get_pool()
    async with p.acquire() as conn:
        points = 5 if is_correct else 1
        await conn.execute(
            "UPDATE brain_exercises SET user_answer = $1, is_correct = $2, points_earned = $3 WHERE id = $4",
            message.text, is_correct, points, exercise_id
        )

    await add_points(message.from_user.id, points, "Aql charxlash mashqi")
    await state.clear()

    if is_correct:
        text = f"🎉 *To'g'ri!* +{points} bal 🌟\n\n"
    else:
        text = f"❌ *Noto'g'ri.*\n\nTo'g'ri javob: *{data['answer']}*\n\n+{points} bal (qatnashganlik uchun) 🌟\n\n"

    if explanation:
        text += f"💡 {explanation}"

    await message.answer(text, parse_mode="Markdown", reply_markup=brain_menu())

@router.callback_query(F.data == "brain_word_chain")
async def brain_word_chain(call: CallbackQuery, state: FSMContext):
    starter_words = ["Olma", "Bahor", "Kitob", "Meva", "Inson", "Dastur", "Ilm", "Yulduz"]
    word = random.choice(starter_words)
    last_letter = word[-1].upper()

    await state.update_data(last_letter=last_letter, count=0, used_words=[word.lower()])
    await state.set_state(BrainStates.word_chain)
    await call.message.edit_text(
        f"🔤 *Oxirgi harfga so'z o'yini*\n\n"
        f"Men: *{word}*\n"
        f"Siz: *'{last_letter}'* harfidan boshlanadigan so'z yozing!\n\n"
        f"_(O'yindan chiqish uchun /stop)_",
        parse_mode="Markdown"
    )

@router.message(BrainStates.word_chain)
async def word_chain_answer(message: Message, state: FSMContext):
    if message.text == "/stop":
        data = await state.get_data()
        count = data.get("count", 0)
        await add_points(message.from_user.id, count, "So'z o'yini")
        await state.clear()
        await message.answer(
            f"🎮 O'yin tugadi!\n\n✅ {count} ta so'z aytdingiz!\n+{count} bal oldiniz! 🌟",
            reply_markup=brain_menu()
        )
        return

    data = await state.get_data()
    last_letter = data["last_letter"]
    used_words = data.get("used_words", [])
    user_word = message.text.strip()

    if not user_word[0].upper() == last_letter:
        await message.answer(f"❌ So'z *'{last_letter}'* harfidan boshlanishi kerak!", parse_mode="Markdown")
        return

    if user_word.lower() in used_words:
        await message.answer("❌ Bu so'z allaqachon ishlatilgan!")
        return

    used_words.append(user_word.lower())
    new_last = user_word[-1].upper()
    count = data["count"] + 1

    bot_words_pool = ["Anor", "Rahmat", "Tarvuz", "Zirak", "Kapalak", "Kema", "Avtobus", "Soyabon",
                      "Nok", "Kuz", "Zarafshon", "Non", "Nafas", "Sog'liq", "Quyosh", "Hayot"]

    bot_word = None
    for w in bot_words_pool:
        if w[0].upper() == new_last and w.lower() not in used_words:
            bot_word = w
            break

    if not bot_word:
        await add_points(message.from_user.id, count + 3, "So'z o'yinida g'alaba")
        await state.clear()
        await message.answer(
            f"🏆 *Siz yutdingiz!*\n\nMen so'z topa olmadim!\n\n"
            f"✅ {count} ta so'z | +{count + 3} bal 🌟",
            parse_mode="Markdown",
            reply_markup=brain_menu()
        )
        return

    used_words.append(bot_word.lower())
    bot_last = bot_word[-1].upper()
    await state.update_data(last_letter=bot_last, count=count, used_words=used_words)

    await message.answer(
        f"✅ *{user_word}* — to'g'ri!\n\n"
        f"Men: *{bot_word}*\n"
        f"Siz: *'{bot_last}'* harfidan so'z yozing!\n\n"
        f"_(Hisob: {count} | /stop — to'xtatish)_",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "brain_word_build")
async def brain_word_build(call: CallbackQuery, state: FSMContext):
    letter_sets = [
        "A, B, L, O, G'", "K, I, T, O, B", "M, E, V, A",
        "D, A, R, A, X, T", "B, O, G', C, H, A", "Y, U, L, D, U, Z",
        "I, N, S, O, N", "B, A, H, O, R"
    ]
    letters = random.choice(letter_sets)
    await state.update_data(letters=letters, count=0, words=[])
    await state.set_state(BrainStates.word_build)
    await call.message.edit_text(
        f"🧩 *Harflardan so'z yasang!*\n\n"
        f"Harflar: *{letters}*\n\n"
        f"Bu harflardan so'z yarating!\n"
        f"Bir so'z — bir xabar yuboring.\n\n"
        f"_(60 soniya | /done — tugating)_",
        parse_mode="Markdown"
    )

@router.message(BrainStates.word_build)
async def word_build_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    words = data.get("words", [])

    if message.text == "/done":
        count = len(words)
        await add_points(message.from_user.id, count * 2, "Harflardan so'z yasash")
        await state.clear()
        word_list = "\n".join([f"✅ {w}" for w in words])
        await message.answer(
            f"🎮 O'yin tugadi!\n\n{word_list}\n\n"
            f"✅ {count} ta so'z | +{count * 2} bal 🌟",
            parse_mode="Markdown",
            reply_markup=brain_menu()
        )
        return

    word = message.text.strip()
    letters_raw = data["letters"].replace("'", "").replace(",", "").replace(" ", "").upper()
    word_upper = word.upper().replace("'", "")

    valid = True
    letter_list = list(letters_raw)
    for char in word_upper:
        if char in letter_list:
            letter_list.remove(char)
        else:
            valid = False
            break

    if not valid:
        await message.answer(f"❌ *{word}* — berilgan harflardan yasab bo'lmaydi!", parse_mode="Markdown")
        return

    if word.lower() in [w.lower() for w in words]:
        await message.answer(f"⚠️ *{word}* allaqachon aytilgan!", parse_mode="Markdown")
        return

    words.append(word)
    await state.update_data(words=words)
    await message.answer(f"✅ *{word}* — to'g'ri! ({len(words)} ta) | /done — tugating", parse_mode="Markdown")

@router.callback_query(F.data == "brain_stats")
async def brain_stats(call: CallbackQuery):
    p = await get_pool()
    async with p.acquire() as conn:
        stats = await conn.fetch(
            """SELECT exercise_type, COUNT(*) as total,
               SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
               SUM(points_earned) as points
               FROM brain_exercises WHERE user_id = $1
               GROUP BY exercise_type""",
            call.from_user.id
        )

    if not stats:
        await call.message.edit_text("📊 Hali natija yo'q.", reply_markup=brain_menu())
        return

    text = "📊 *Aql charxlash natijalari:*\n\n"
    total_points = 0
    for s in stats:
        name = EXERCISE_TYPES.get(s["exercise_type"], s["exercise_type"])
        pct = int(s["correct"] / s["total"] * 100) if s["total"] > 0 else 0
        text += f"{name}\n✅ {s['correct']}/{s['total']} ({pct}%) | 🌟{s['points']} bal\n\n"
        total_points += (s["points"] or 0)

    text += f"🏆 Jami: *{total_points}* bal"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=brain_menu())
