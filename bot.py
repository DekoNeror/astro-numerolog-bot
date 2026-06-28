import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

groq_client = Groq(api_key=GROQ_API_KEY)

# ---------- База данных пользователей (в памяти) ----------
users_db = {}

def save_user(user_id: int, data: dict):
    users_db[user_id] = data

def get_user(user_id: int) -> dict:
    return users_db.get(user_id, {})

# ---------- Нумерология ----------

def calculate_numerology(date_str: str, name: str) -> dict:
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        return None

    digits = [int(d) for d in date_str if d.isdigit()]
    total = sum(digits)
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(d) for d in str(total))
    life_path = total

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

    month, day = date.month, date.day
    zodiac_list = [
        (1,20,"Козерог"),(2,19,"Водолей"),(3,20,"Рыбы"),(4,20,"Овен"),
        (5,21,"Телец"),(6,21,"Близнецы"),(7,23,"Рак"),(8,23,"Лев"),
        (9,23,"Дева"),(10,23,"Весы"),(11,22,"Скорпион"),(12,22,"Стрелец"),(12,31,"Козерог")
    ]
    zodiac = "Козерог"
    for z_month, z_day, z_name in zodiac_list:
        if month < z_month or (month == z_month and day <= z_day):
            zodiac = z_name
            break

    return {"life_path": life_path, "destiny": destiny, "zodiac": zodiac,
            "birth_day": date.day, "birth_month": date.month, "birth_year": date.year, "name": name}

def ai_request(prompt: str, max_tokens: int = 1000) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.8
    )
    return response.choices[0].message.content

def get_ai_reading(nums: dict) -> str:
    return ai_request(f"""Ты опытный нумеролог и астролог. Дай персональный разбор.
Имя: {nums['name']}, Знак: {nums['zodiac']}, Число жизни: {nums['life_path']}, Число судьбы: {nums['destiny']}
Дата: {nums['birth_day']}.{nums['birth_month']}.{nums['birth_year']}

Напиши:
1. 🌟 Характеристика личности
2. 💫 Число жизненного пути {nums['life_path']}
3. 🔮 Число судьбы {nums['destiny']}
4. ♈ {nums['zodiac']} — ключевые черты
5. 💰 Прогноз на месяц (финансы, отношения, здоровье)
6. ✨ Совет нумеролога

По-русски, тепло, на "ты", с эмодзи, 300-400 слов.""")

def get_daily_horoscope(zodiac: str) -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Астролог. Гороскоп на {today} для {zodiac}.
🌅 Энергия дня
❤️ Любовь
💼 Карьера и деньги
🌿 Здоровье
🎯 Совет дня
По-русски, 150-200 слов, позитивно.""", 500)

def get_tarot(name: str) -> str:
    cards = ["Маг","Жрица","Императрица","Император","Иерофант","Влюблённые",
             "Колесница","Сила","Отшельник","Колесо Фортуны","Справедливость",
             "Повешенный","Смерть","Умеренность","Дьявол","Башня","Звезда",
             "Луна","Солнце","Суд","Мир","Шут"]
    import random
    drawn = random.sample(cards, 3)
    return ai_request(f"""Таролог. Расклад для {name}: прошлое={drawn[0]}, настоящее={drawn[1]}, будущее={drawn[2]}.
Дай мистический персональный расклад. По-русски, 200-250 слов, с эмодзи 🔮.""", 600)

def get_moon_calendar() -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Астролог. Лунный календарь на {today}.
🌙 Фаза луны и её влияние
✅ Что хорошо делать сегодня
❌ Чего избегать
💼 Для бизнеса и финансов
❤️ Для отношений
🌿 Для здоровья
По-русски, 200 слов, с эмодзи.""", 500)

def get_dream(name: str, dream: str) -> str:
    return ai_request(f"""Толкователь снов. {name} видел сон: "{dream}"
Дай мистическое толкование: символы, послание, что ждёт в будущем.
По-русски, 200-250 слов, загадочно, с эмодзи 😴🌙.""", 600)

def get_celebrity_compatibility(name: str, zodiac: str, life_path: int, celeb: str) -> str:
    return ai_request(f"""Нумеролог. Совместимость {name} ({zodiac}, число {life_path}) с {celeb}.
💑 Совместимость в % и описание
❤️ В любви
🤝 В дружбе
⚡ Сложности
✨ Итог
По-русски, 200 слов, весело и с юмором, эмодзи.""", 500)

def get_compatibility(name1, date1, name2, date2) -> str:
    nums1 = calculate_numerology(date1, name1)
    nums2 = calculate_numerology(date2, name2)
    if not nums1 or not nums2:
        return "Ошибка в данных. Проверь формат дат (ДД.ММ.ГГГГ)"
    return ai_request(f"""Нумеролог. Совместимость:
{name1}: {nums1['zodiac']}, число жизни {nums1['life_path']}, судьбы {nums1['destiny']}
{name2}: {nums2['zodiac']}, число жизни {nums2['life_path']}, судьбы {nums2['destiny']}
💑 Общая совместимость (%)
❤️ В любви
🤝 В дружбе
💼 В работе
⚡ Сложности
✨ Совет
По-русски, 250 слов, эмодзи.""", 700)

# ---------- Клавиатуры ----------

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Нумерологический разбор", callback_data="numerology")],
        [InlineKeyboardButton("⭐ Гороскоп на сегодня", callback_data="horoscope")],
        [InlineKeyboardButton("🃏 Расклад Таро", callback_data="tarot")],
        [InlineKeyboardButton("🌙 Лунный календарь", callback_data="moon")],
        [InlineKeyboardButton("😴 Толкование сна", callback_data="dream")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compatibility")],
        [InlineKeyboardButton("👑 Совместимость со знаменитостью", callback_data="celeb")],
        [InlineKeyboardButton("⚙️ Мои данные", callback_data="my_data")],
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]])

CELEBRITIES = ["Илон Маск", "Тейлор Свифт", "Дрейк", "Ариана Гранде",
               "Криштиану Роналду", "Билл Гейтс", "Леди Гага", "Джонни Депп"]

def celeb_keyboard():
    buttons = [[InlineKeyboardButton(c, callback_data=f"celeb_{c}")] for c in CELEBRITIES]
    buttons.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)

# ---------- Состояния ----------
user_states = {}

# ---------- Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = get_user(user_id)
    if user.get("name"):
        text = (f"С возвращением, *{user['name']}*! 🌟\n\n"
                f"Твой знак: *{user.get('zodiac', '?')}* | Число жизни: *{user.get('life_path', '?')}*\n\n"
                f"Выбери что тебя интересует 👇")
    else:
        text = ("🌟 *Добро пожаловать в Астро Нумеролог!*\n\n"
                "Я помогу тебе узнать:\n"
                "✨ Число судьбы и жизненного пути\n"
                "🔮 Персональный нумерологический разбор\n"
                "⭐ Гороскоп на каждый день\n"
                "🃏 Расклад Таро\n"
                "🌙 Лунный календарь\n"
                "😴 Толкование снов\n"
                "💑 Совместимость с партнёром\n\n"
                "Выбери что тебя интересует 👇")
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    data = query.data

    if data == "menu":
        await query.message.reply_text("Выбери что тебя интересует 👇", reply_markup=main_menu())

    elif data == "my_data":
        if user.get("name"):
            text = (f"⚙️ *Твои данные:*\n\n"
                    f"👤 Имя: *{user['name']}*\n"
                    f"📅 Дата рождения: *{user['date']}*\n"
                    f"♈ Знак зодиака: *{user['zodiac']}*\n"
                    f"🔢 Число жизни: *{user['life_path']}*\n"
                    f"🔮 Число судьбы: *{user['destiny']}*")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_data")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
        else:
            text = "У тебя пока нет сохранённых данных. Сделай нумерологический разбор!"
            keyboard = back_menu()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif data == "edit_data":
        user_states[user_id] = {"action": "numerology", "step": "name"}
        await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "numerology":
        if user.get("name"):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Использовать мои данные", callback_data="use_saved")],
                [InlineKeyboardButton("📝 Ввести новые данные", callback_data="new_data_num")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
            await query.message.reply_text(
                f"У меня есть твои данные, *{user['name']}*! Использовать их?",
                parse_mode="Markdown", reply_markup=keyboard)
        else:
            user_states[user_id] = {"action": "numerology", "step": "name"}
            await query.message.reply_text("🔮 Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "use_saved":
        await query.message.reply_text(f"🔮 Считаю разбор для *{user['name']}*... ✨", parse_mode="Markdown")
        nums = calculate_numerology(user['date'], user['name'])
        reading = get_ai_reading(nums)
        await query.message.reply_text(
            f"*Разбор для {user['name']}*\n\n{reading}\n\n"
            f"📊 Число жизни: *{nums['life_path']}* | Число судьбы: *{nums['destiny']}* | *{nums['zodiac']}*\n\n"
            f"Поделись ботом с другом! 👫",
            parse_mode="Markdown", reply_markup=back_menu())

    elif data == "new_data_num":
        user_states[user_id] = {"action": "numerology", "step": "name"}
        await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "horoscope":
        if user.get("zodiac"):
            await query.message.reply_text(f"⭐ Составляю гороскоп для *{user['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(user['zodiac'])
            await query.message.reply_text(
                f"*Гороскоп для {user['name']} ({user['zodiac']})*\n\n{horoscope}\n\nПоделись ботом! 🌟",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[user_id] = {"action": "horoscope", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "tarot":
        name = user.get("name")
        if name:
            await query.message.reply_text(f"🃏 Тяну карты для *{name}*... ✨", parse_mode="Markdown")
            result = get_tarot(name)
            await query.message.reply_text(f"*Расклад Таро для {name}*\n\n{result}\n\nПоделись ботом! 🔮",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[user_id] = {"action": "tarot", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "moon":
        await query.message.reply_text("🌙 Составляю лунный календарь на сегодня... ✨")
        result = get_moon_calendar()
        await query.message.reply_text(f"*Лунный календарь*\n\n{result}\n\nПоделись ботом! 🌙",
            parse_mode="Markdown", reply_markup=back_menu())

    elif data == "dream":
        user_states[user_id] = {"action": "dream", "step": "name" if not user.get("name") else "dream"}
        if user.get("name"):
            await query.message.reply_text("😴 Опиши свой сон подробно:", parse_mode="Markdown")
        else:
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "compatibility":
        user_states[user_id] = {"action": "compatibility", "step": "name1"}
        await query.message.reply_text("💑 Напиши *своё имя*:", parse_mode="Markdown")

    elif data == "celeb":
        name = user.get("name", "")
        if name:
            await query.message.reply_text(
                f"👑 *{name}*, выбери знаменитость для проверки совместимости:",
                parse_mode="Markdown", reply_markup=celeb_keyboard())
        else:
            user_states[user_id] = {"action": "celeb_name", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data.startswith("celeb_"):
        celeb = data[6:]
        name = user.get("name", "Пользователь")
        zodiac = user.get("zodiac", "Овен")
        life_path = user.get("life_path", 1)
        await query.message.reply_text(f"👑 Считаю совместимость *{name}* с *{celeb}*... ✨", parse_mode="Markdown")
        result = get_celebrity_compatibility(name, zodiac, life_path, celeb)
        await query.message.reply_text(
            f"*{name} + {celeb}*\n\n{result}\n\nПоделись с друзьями! 👑",
            parse_mode="Markdown", reply_markup=back_menu())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})
    user = get_user(user_id)

    if not state:
        await update.message.reply_text("Напиши /start чтобы начать 🌟")
        return

    action = state.get("action")
    step = state.get("step")

    # НУМЕРОЛОГИЯ
    if action == "numerology":
        if step == "name":
            user_states[user_id]["name"] = text
            user_states[user_id]["step"] = "date"
            await update.message.reply_text(f"Привет, *{text}*! 👋\n\nДата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ (например 15.03.1990)")
                return
            save_user(user_id, {"name": name, "date": text, "zodiac": nums["zodiac"],
                                "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text("🔮 Считаю разбор... ✨")
            reading = get_ai_reading(nums)
            await update.message.reply_text(
                f"*Разбор для {name}*\n\n{reading}\n\n"
                f"📊 Число жизни: *{nums['life_path']}* | Судьбы: *{nums['destiny']}* | *{nums['zodiac']}*\n\n"
                f"Поделись ботом с другом! 👫",
                parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(user_id, None)

    # ГОРОСКОП
    elif action == "horoscope":
        if step == "name":
            user_states[user_id]["name"] = text
            user_states[user_id]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ")
                return
            save_user(user_id, {"name": name, "date": text, "zodiac": nums["zodiac"],
                                "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text(f"⭐ Гороскоп для *{nums['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(nums["zodiac"])
            await update.message.reply_text(
                f"*Гороскоп для {name} ({nums['zodiac']})*\n\n{horoscope}\n\nПоделись! 🌟",
                parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(user_id, None)

    # ТАРО
    elif action == "tarot":
        if step == "name":
            user_states[user_id]["name"] = text
            save_user(user_id, {**user, "name": text})
            await update.message.reply_text(f"🃏 Тяну карты для *{text}*... ✨", parse_mode="Markdown")
            result = get_tarot(text)
            await update.message.reply_text(f"*Расклад Таро для {text}*\n\n{result}\n\nПоделись! 🔮",
                parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(user_id, None)

    # СОН
    elif action == "dream":
        if step == "name":
            user_states[user_id]["dreamer"] = text
            user_states[user_id]["step"] = "dream"
            save_user(user_id, {**user, "name": text})
            await update.message.reply_text("😴 Опиши свой сон подробно:")
        elif step == "dream":
            name = state.get("dreamer") or user.get("name", "Друг")
            await update.message.reply_text("🌙 Толкую сон... ✨")
            result = get_dream(name, text)
            await update.message.reply_text(f"*Толкование сна для {name}*\n\n{result}\n\nПоделись! 😴",
                parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(user_id, None)

    # СОВМЕСТИМОСТЬ
    elif action == "compatibility":
        if step == "name1":
            user_states[user_id]["name1"] = text
            user_states[user_id]["step"] = "date1"
            await update.message.reply_text(f"*{text}* 👋\n\nТвоя дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date1":
            user_states[user_id]["date1"] = text
            user_states[user_id]["step"] = "name2"
            await update.message.reply_text("Имя *партнёра*:", parse_mode="Markdown")
        elif step == "name2":
            user_states[user_id]["name2"] = text
            user_states[user_id]["step"] = "date2"
            await update.message.reply_text(f"Дата рождения *{text}* (ДД.ММ.ГГГГ):", parse_mode="Markdown")
        elif step == "date2":
            name1, date1, name2 = state["name1"], state["date1"], state["name2"]
            await update.message.reply_text("💑 Считаю совместимость... ✨")
            result = get_compatibility(name1, date1, name2, text)
            await update.message.reply_text(
                f"*Совместимость {name1} и {name2}*\n\n{result}\n\nПоделись! 💫",
                parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(user_id, None)

    # ИМЯ ДЛЯ ЗНАМЕНИТОСТИ
    elif action == "celeb_name":
        if step == "name":
            save_user(user_id, {**user, "name": text})
            user_states.pop(user_id, None)
            await update.message.reply_text(
                f"👑 *{text}*, выбери знаменитость:",
                parse_mode="Markdown", reply_markup=celeb_keyboard())

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
