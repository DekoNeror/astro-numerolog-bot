import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

# ============================
# ВСТАВЬ СВОИ КЛЮЧИ СЮДА:
TELEGRAM_TOKEN = "ВСТАВЬ_ТОКЕН_БОТА"
GROQ_API_KEY = "ВСТАВЬ_GROQ_КЛЮЧ"
# ============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

groq_client = Groq(api_key=GROQ_API_KEY)

# ---------- Нумерология ----------

def calculate_numerology(date_str: str, name: str) -> dict:
    """Считаем нумерологические числа по дате и имени."""
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        return None

    # Число жизненного пути
    digits = [int(d) for d in date_str if d.isdigit()]
    total = sum(digits)
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(d) for d in str(total))
    life_path = total

    # Число судьбы (по имени, русский алфавит)
    ru_map = {
        'а':1,'б':2,'в':6,'г':3,'д':4,'е':5,'ё':5,'ж':2,'з':7,'и':1,
        'й':1,'к':2,'л':3,'м':4,'н':5,'о':7,'п':8,'р':9,'с':1,'т':2,
        'у':6,'ф':8,'х':5,'ц':4,'ч':6,'ш':2,'щ':3,'ъ':4,'ы':2,'ь':2,
        'э':5,'ю':6,'я':1
    }
    name_digits = [ru_map.get(c.lower(), 0) for c in name if c.isalpha()]
    destiny = sum(name_digits)
    while destiny > 9 and destiny not in (11, 22, 33):
        destiny = sum(int(d) for d in str(destiny))

    # Знак зодиака
    month, day = date.month, date.day
    zodiac_signs = [
        (1, 20, "Козерог"), (2, 19, "Водолей"), (3, 20, "Рыбы"),
        (4, 20, "Овен"), (5, 21, "Телец"), (6, 21, "Близнецы"),
        (7, 23, "Рак"), (8, 23, "Лев"), (9, 23, "Дева"),
        (10, 23, "Весы"), (11, 22, "Скорпион"), (12, 22, "Стрелец"),
        (12, 31, "Козерог")
    ]
    zodiac = "Козерог"
    for z_month, z_day, z_name in zodiac_signs:
        if month < z_month or (month == z_month and day <= z_day):
            zodiac = z_name
            break

    return {
        "life_path": life_path,
        "destiny": destiny,
        "zodiac": zodiac,
        "birth_day": date.day,
        "birth_month": date.month,
        "birth_year": date.year,
        "name": name
    }


def get_ai_reading(nums: dict) -> str:
    """Получаем персональный прогноз от ИИ."""
    prompt = f"""Ты опытный нумеролог и астролог. Дай персональный, вдохновляющий и точный разбор для человека.

Данные:
- Имя: {nums['name']}
- Знак зодиака: {nums['zodiac']}
- Число жизненного пути: {nums['life_path']}
- Число судьбы: {nums['destiny']}
- Дата рождения: {nums['birth_day']}.{nums['birth_month']}.{nums['birth_year']}

Напиши разбор в таком формате:
1. 🌟 Краткая характеристика личности (2-3 предложения)
2. 💫 Число жизненного пути {nums['life_path']} — что оно означает для этого человека
3. 🔮 Число судьбы {nums['destiny']} — его влияние на жизнь
4. ♈ {nums['zodiac']} — ключевые черты и особенности
5. 💰 Прогноз на ближайший месяц (финансы, отношения, здоровье)
6. ✨ Совет от нумеролога

Пиши по-русски, тепло и лично, обращайся к человеку на "ты". Используй эмодзи. Текст около 300-400 слов."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.8
    )
    return response.choices[0].message.content


def get_daily_horoscope(zodiac: str) -> str:
    """Ежедневный гороскоп для знака зодиака."""
    today = datetime.now().strftime("%d.%m.%Y")
    prompt = f"""Ты астролог. Напиши вдохновляющий гороскоп на сегодня ({today}) для знака {zodiac}.

Формат:
🌅 Общая энергия дня
❤️ Любовь и отношения  
💼 Карьера и деньги
🌿 Здоровье и энергия
🎯 Совет дня

Пиши по-русски, около 150-200 слов. Используй эмодзи. Тон позитивный и мотивирующий."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.9
    )
    return response.choices[0].message.content


def get_compatibility(name1: str, date1: str, name2: str, date2: str) -> str:
    """Совместимость двух людей."""
    nums1 = calculate_numerology(date1, name1)
    nums2 = calculate_numerology(date2, name2)
    if not nums1 or not nums2:
        return "Ошибка в данных. Проверь формат дат (ДД.ММ.ГГГГ)"

    prompt = f"""Ты нумеролог и астролог. Рассчитай совместимость двух людей.

Человек 1: {name1}, {nums1['zodiac']}, число жизни: {nums1['life_path']}, число судьбы: {nums1['destiny']}
Человек 2: {name2}, {nums2['zodiac']}, число жизни: {nums2['life_path']}, число судьбы: {nums2['destiny']}

Напиши:
💑 Общая совместимость (в % и описание)
❤️ В отношениях и любви
🤝 В дружбе и общении
💼 В работе и бизнесе
⚡ Возможные сложности
✨ Главный совет паре

Пиши по-русски, около 250 слов. Используй эмодзи."""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.8
    )
    return response.choices[0].message.content


# ---------- Хранилище состояний пользователей ----------
user_states = {}


# ---------- Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔮 Мой нумерологический разбор", callback_data="numerology")],
        [InlineKeyboardButton("⭐ Гороскоп на сегодня", callback_data="horoscope")],
        [InlineKeyboardButton("💑 Совместимость с партнёром", callback_data="compatibility")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌟 *Добро пожаловать в Астро Нумеролог!*\n\n"
        "Я помогу тебе узнать:\n"
        "✨ Твоё число судьбы и жизненного пути\n"
        "🔮 Персональный нумерологический разбор\n"
        "⭐ Гороскоп на каждый день\n"
        "💑 Совместимость с любимым человеком\n\n"
        "Выбери что тебя интересует 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "numerology":
        user_states[user_id] = {"action": "numerology", "step": "name"}
        await query.message.reply_text(
            "🔮 *Нумерологический разбор*\n\n"
            "Напиши своё *имя* (как тебя зовут):",
            parse_mode="Markdown"
        )

    elif query.data == "horoscope":
        user_states[user_id] = {"action": "horoscope", "step": "name"}
        await query.message.reply_text(
            "⭐ *Гороскоп на сегодня*\n\n"
            "Напиши своё *имя*:",
            parse_mode="Markdown"
        )

    elif query.data == "compatibility":
        user_states[user_id] = {"action": "compatibility", "step": "name1"}
        await query.message.reply_text(
            "💑 *Совместимость с партнёром*\n\n"
            "Напиши *своё имя*:",
            parse_mode="Markdown"
        )

    elif query.data == "menu":
        keyboard = [
            [InlineKeyboardButton("🔮 Мой нумерологический разбор", callback_data="numerology")],
            [InlineKeyboardButton("⭐ Гороскоп на сегодня", callback_data="horoscope")],
            [InlineKeyboardButton("💑 Совместимость с партнёром", callback_data="compatibility")],
        ]
        await query.message.reply_text(
            "Выбери что тебя интересует 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})

    if not state:
        await update.message.reply_text(
            "Напиши /start чтобы начать 🌟"
        )
        return

    action = state.get("action")
    step = state.get("step")

    # --- НУМЕРОЛОГИЯ ---
    if action == "numerology":
        if step == "name":
            user_states[user_id]["name"] = text
            user_states[user_id]["step"] = "date"
            await update.message.reply_text(
                f"Привет, *{text}*! 👋\n\nТеперь напиши дату рождения в формате *ДД.ММ.ГГГГ*\nНапример: 15.03.1990",
                parse_mode="Markdown"
            )
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат даты. Напиши в формате ДД.ММ.ГГГГ\nНапример: 15.03.1990")
                return
            await update.message.reply_text("🔮 Считаю твой нумерологический разбор... Подожди немного ✨")
            reading = get_ai_reading(nums)
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
            await update.message.reply_text(
                f"*Персональный разбор для {name}*\n\n{reading}\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📊 Твои числа:\n"
                f"• Число жизненного пути: *{nums['life_path']}*\n"
                f"• Число судьбы: *{nums['destiny']}*\n"
                f"• Знак зодиака: *{nums['zodiac']}*\n\n"
                f"Поделись ботом с другом — узнайте совместимость! 👫",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            user_states.pop(user_id, None)

    # --- ГОРОСКОП ---
    elif action == "horoscope":
        if step == "name":
            user_states[user_id]["name"] = text
            user_states[user_id]["step"] = "date"
            await update.message.reply_text(
                f"Привет, *{text}*! 👋\n\nНапиши дату рождения в формате *ДД.ММ.ГГГГ*:",
                parse_mode="Markdown"
            )
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат даты. Напиши в формате ДД.ММ.ГГГГ")
                return
            await update.message.reply_text(f"⭐ Составляю гороскоп для {nums['zodiac']}... ✨")
            horoscope = get_daily_horoscope(nums['zodiac'])
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
            await update.message.reply_text(
                f"*Гороскоп для {name} ({nums['zodiac']})*\n\n{horoscope}\n\n"
                f"Поделись ботом с друзьями! 🌟",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            user_states.pop(user_id, None)

    # --- СОВМЕСТИМОСТЬ ---
    elif action == "compatibility":
        if step == "name1":
            user_states[user_id]["name1"] = text
            user_states[user_id]["step"] = "date1"
            await update.message.reply_text(
                f"*{text}* — запомнил! 👋\n\nНапиши свою дату рождения *ДД.ММ.ГГГГ*:",
                parse_mode="Markdown"
            )
        elif step == "date1":
            user_states[user_id]["date1"] = text
            user_states[user_id]["step"] = "name2"
            await update.message.reply_text("Теперь напиши *имя партнёра*:", parse_mode="Markdown")
        elif step == "name2":
            user_states[user_id]["name2"] = text
            user_states[user_id]["step"] = "date2"
            await update.message.reply_text(
                f"И дату рождения *{text}* в формате *ДД.ММ.ГГГГ*:",
                parse_mode="Markdown"
            )
        elif step == "date2":
            name1 = state.get("name1")
            date1 = state.get("date1")
            name2 = state.get("name2")
            await update.message.reply_text("💑 Считаю вашу совместимость... ✨")
            result = get_compatibility(name1, date1, name2, text)
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
            await update.message.reply_text(
                f"*Совместимость {name1} и {name2}*\n\n{result}\n\n"
                f"Поделись ботом с друзьями! 💫",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            user_states.pop(user_id, None)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
