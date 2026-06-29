import os
import logging
import random
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CHANNEL_ID = "@astro_numerolog_ru"
ADMIN_ID = 1473856140

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
groq_client = Groq(api_key=GROQ_API_KEY)

# ========== БАЗА ДАННЫХ ==========
users_db = {}        # {user_id: {name, date, zodiac, life_path, destiny}}
all_users = {}       # {user_id: {tg_name, username, joined, blocked, premium_until, referrals, daily_bonus_date, ref_by}}
user_states = {}     # состояния диалогов
contests = {}        # {contest_id: {title, description, end_date, winner_id, active}}
referral_bonuses = {}  # {user_id: days_added}

def save_user(uid, data):
    users_db[uid] = data

def get_user(uid):
    return users_db.get(uid, {})

def track_user(uid, tg_user):
    if uid not in all_users:
        all_users[uid] = {
            "tg_name": tg_user.full_name,
            "username": tg_user.username or "—",
            "joined": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "blocked": False,
            "premium_until": None,
            "referrals": 0,
            "daily_bonus_date": None,
            "ref_by": None
        }
    else:
        all_users[uid]["tg_name"] = tg_user.full_name
        if tg_user.username:
            all_users[uid]["username"] = tg_user.username

def is_blocked(uid):
    return all_users.get(uid, {}).get("blocked", False)

def is_premium(uid):
    u = all_users.get(uid, {})
    if u.get("premium_until"):
        return datetime.now() < datetime.strptime(u["premium_until"], "%d.%m.%Y")
    return False

def get_premium_days_left(uid):
    u = all_users.get(uid, {})
    if u.get("premium_until"):
        d = datetime.strptime(u["premium_until"], "%d.%m.%Y")
        days = (d - datetime.now()).days
        return max(0, days)
    return 0

def add_premium(uid, days):
    if uid not in all_users:
        all_users[uid] = {"tg_name": "—", "username": "—", "joined": "—", "blocked": False, "premium_until": None, "referrals": 0, "daily_bonus_date": None, "ref_by": None}
    current = all_users[uid].get("premium_until")
    if current:
        try:
            base = datetime.strptime(current, "%d.%m.%Y")
            if base < datetime.now():
                base = datetime.now()
        except:
            base = datetime.now()
    else:
        base = datetime.now()
    new_date = base + timedelta(days=days)
    all_users[uid]["premium_until"] = new_date.strftime("%d.%m.%Y")

def can_daily_bonus(uid):
    u = all_users.get(uid, {})
    last = u.get("daily_bonus_date")
    if not last:
        return True
    return last != datetime.now().strftime("%d.%m.%Y")

def claim_daily_bonus(uid):
    if uid in all_users:
        all_users[uid]["daily_bonus_date"] = datetime.now().strftime("%d.%m.%Y")

# ========== НУМЕРОЛОГИЯ ==========
def calculate_numerology(date_str, name):
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
    except:
        return None
    digits = [int(d) for d in date_str if d.isdigit()]
    total = sum(digits)
    while total > 9 and total not in (11, 22, 33):
        total = sum(int(d) for d in str(total))
    life_path = total
    ru_map = {'а':1,'б':2,'в':6,'г':3,'д':4,'е':5,'ё':5,'ж':2,'з':7,'и':1,'й':1,'к':2,'л':3,'м':4,'н':5,'о':7,'п':8,'р':9,'с':1,'т':2,'у':6,'ф':8,'х':5,'ц':4,'ч':6,'ш':2,'щ':3,'ъ':4,'ы':2,'ь':2,'э':5,'ю':6,'я':1}
    destiny = sum(ru_map.get(c.lower(), 0) for c in name if c.isalpha())
    while destiny > 9 and destiny not in (11, 22, 33):
        destiny = sum(int(d) for d in str(destiny))
    zodiac_list = [(1,20,"Козерог"),(2,19,"Водолей"),(3,20,"Рыбы"),(4,20,"Овен"),(5,21,"Телец"),(6,21,"Близнецы"),(7,23,"Рак"),(8,23,"Лев"),(9,23,"Дева"),(10,23,"Весы"),(11,22,"Скорпион"),(12,22,"Стрелец"),(12,31,"Козерог")]
    zodiac = "Козерог"
    month, day = date.month, date.day
    for z_month, z_day, z_name in zodiac_list:
        if month < z_month or (month == z_month and day <= z_day):
            zodiac = z_name
            break
    return {"life_path": life_path, "destiny": destiny, "zodiac": zodiac, "birth_day": date.day, "birth_month": date.month, "birth_year": date.year, "name": name}

def lucky_number(uid):
    today = datetime.now().strftime("%d%m%Y")
    seed = int(str(uid) + today)
    random.seed(seed)
    return random.randint(1, 9)

def ai_request(prompt, max_tokens=1000):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.8
    )
    return response.choices[0].message.content

# ========== AI ФУНКЦИИ ==========
def get_ai_reading(nums):
    return ai_request(f"""Нумеролог и астролог. Персональный разбор.
Имя: {nums['name']}, Знак: {nums['zodiac']}, Число жизни: {nums['life_path']}, Судьбы: {nums['destiny']}
Дата: {nums['birth_day']}.{nums['birth_month']}.{nums['birth_year']}
1. 🌟 Характеристика личности
2. 💫 Число жизненного пути {nums['life_path']}
3. 🔮 Число судьбы {nums['destiny']}
4. ♈ {nums['zodiac']} — черты
5. 💰 Прогноз на месяц
6. ✨ Совет нумеролога
По-русски, тепло, на ты, эмодзи, 300-400 слов.""")

def get_daily_horoscope(zodiac):
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Гороскоп на {today} для {zodiac}.
🌅 Энергия дня / ❤️ Любовь / 💼 Карьера / 🌿 Здоровье / 🎯 Совет
По-русски, 150-200 слов, позитивно.""", 500)

def get_tarot(name):
    cards = ["Маг","Жрица","Императрица","Император","Иерофант","Влюблённые","Колесница","Сила","Отшельник","Колесо Фортуны","Справедливость","Повешенный","Смерть","Умеренность","Дьявол","Башня","Звезда","Луна","Солнце","Суд","Мир","Шут"]
    drawn = random.sample(cards, 3)
    return ai_request(f"""Таролог. Расклад для {name}: прошлое={drawn[0]}, настоящее={drawn[1]}, будущее={drawn[2]}.
Мистический расклад. По-русски, 200-250 слов, эмодзи 🔮.""", 600)

def get_moon_calendar():
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Лунный календарь на {today}.
🌙 Фаза / ✅ Что делать / ❌ Чего избегать / 💼 Бизнес / ❤️ Отношения / 🌿 Здоровье
По-русски, 200 слов, эмодзи.""", 500)

def get_dream(name, dream):
    return ai_request(f"""Толкователь снов. {name} видел сон: "{dream}"
Символы, послание, будущее. По-русски, 200-250 слов, загадочно, эмодзи 😴🌙.""", 600)

def get_celebrity_compatibility(name, zodiac, life_path, celeb):
    return ai_request(f"""Нумеролог. Совместимость {name} ({zodiac}, число {life_path}) с {celeb}.
💑 % / ❤️ Любовь / 🤝 Дружба / ⚡ Сложности / ✨ Итог
По-русски, 200 слов, весело, эмодзи.""", 500)

def get_compatibility(name1, date1, name2, date2):
    n1 = calculate_numerology(date1, name1)
    n2 = calculate_numerology(date2, name2)
    if not n1 or not n2:
        return "Ошибка в данных. Проверь формат дат (ДД.ММ.ГГГГ)"
    return ai_request(f"""Нумеролог. Совместимость:
{name1}: {n1['zodiac']}, жизнь {n1['life_path']}, судьба {n1['destiny']}
{name2}: {n2['zodiac']}, жизнь {n2['life_path']}, судьба {n2['destiny']}
💑 % / ❤️ Любовь / 🤝 Дружба / 💼 Работа / ⚡ Сложности / ✨ Совет
По-русски, 250 слов, эмодзи.""", 700)

def get_yearly_forecast(nums):
    return ai_request(f"""Нумеролог. Прогноз на год для {nums['name']}.
Знак: {nums['zodiac']}, число жизни: {nums['life_path']}, судьбы: {nums['destiny']}
По кварталам:
🌱 Январь-Март: ...
☀️ Апрель-Июнь: ...
🍂 Июль-Сентябрь: ...
❄️ Октябрь-Декабрь: ...
💰 Финансы года / ❤️ Любовь года / 💼 Карьера года / ✨ Главный совет года
По-русски, 400-500 слов, вдохновляюще, эмодзи.""", 1000)

def get_name_numerology(name):
    return ai_request(f"""Нумеролог. Анализ имени "{name}".
🔢 Числовое значение имени
✨ Что имя говорит о характере
💫 Сильные стороны носителя имени
⚡ Слабые стороны
🎯 Жизненное предназначение по имени
🌟 Совет как использовать силу своего имени
По-русски, 250-300 слов, эмодзи.""", 700)

def get_lucky_day_forecast(name, zodiac, life_path):
    lnum = lucky_number(hash(name))
    return ai_request(f"""Нумеролог. Прогноз на сегодня для {name}.
Знак: {zodiac}, число жизни: {life_path}, число удачи сегодня: {lnum}
🎯 Число удачи: {lnum} — что оно означает сегодня
⭐ Лучшее время для важных дел
💚 Благоприятные действия
🔴 Чего избегать
💫 Аффирмация дня
По-русски, 200 слов, позитивно, эмодзи.""", 500)

# ========== АВТОПОСТИНГ ==========
async def post_morning_horoscope(context):
    today = datetime.now().strftime("%d.%m.%Y")
    text = ai_request(f"""Гороскоп на {today} для всех 12 знаков.
Для каждого 2-3 предложения:
♈ Овен — ... ♉ Телец — ... ♊ Близнецы — ... ♋ Рак — ... ♌ Лев — ... ♍ Дева — ...
♎ Весы — ... ♏ Скорпион — ... ♐ Стрелец — ... ♑ Козерог — ... ♒ Водолей — ... ♓ Рыбы — ...
По-русски, позитивно, эмодзи.""", 1000)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🌅 *Гороскоп на {today}*\n\n{text}\n\n🔮 Персональный разбор — в боте @astro_numerolog_bot", parse_mode="Markdown")

async def post_affirmation(context):
    text = ai_request("Вдохновляющая аффирмация дня. Одна мощная фраза + 3-4 предложения почему работает. По-русски, эмодзи ✨💫", 300)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"💫 *Аффирмация дня*\n\n{text}\n\n🔮 Твоё число судьбы — в боте!", parse_mode="Markdown")

async def post_moon(context):
    text = get_moon_calendar()
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🌙 *Лунный календарь*\n\n{text}\n\n🔮 Персональный прогноз — в боте!", parse_mode="Markdown")

async def post_evening_wish(context):
    text = ai_request("Тёплое вечернее послание от Вселенной. 4-5 предложений. Мистично, душевно, на ты. Эмодзи 🌟✨🔮", 300)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🌟 *Послание Вселенной*\n\n{text}\n\n🔮 Узнай что звёзды говорят лично тебе — в боте!", parse_mode="Markdown")

async def post_sleep_advice(context):
    text = ai_request("Мистический совет перед сном. Как зарядиться ночью, что загадать звёздам. 4-5 предложений. Спокойно, тепло, эмодзи 😴🌙✨", 300)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"😴 *Совет перед сном*\n\n{text}\n\n🔮 Толкование снов — в боте!", parse_mode="Markdown")

async def post_weekly_tarot(context):
    card = random.choice(["Маг","Жрица","Императрица","Сила","Звезда","Луна","Солнце","Мир","Колесо Фортуны"])
    text = ai_request(f"Карта недели для всех — {card}. Что означает в любви, работе, финансах, здоровье. По-русски, 200-250 слов, эмодзи 🃏🔮", 500)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🃏 *Карта Таро недели — {card}*\n\n{text}\n\n🔮 Личный расклад — в боте!", parse_mode="Markdown")

async def post_weekly_numerology(context):
    week = datetime.now().strftime("%d.%m.%Y")
    text = ai_request(f"Нумерологический прогноз на неделю с {week}. Для чисел 1-9, 11, 22. Формат: Число 1 — ..., Число 2 — ... По-русски, эмодзи 🔢✨", 800)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=f"🔢 *Нумерологический прогноз недели*\n\n{text}\n\n🔮 Узнай своё число — в боте!", parse_mode="Markdown")

# ========== КЛАВИАТУРЫ ==========
def main_menu(uid=None):
    premium = is_premium(uid) if uid else False
    rows = [
        [InlineKeyboardButton("🔮 Нумерологический разбор", callback_data="numerology")],
        [InlineKeyboardButton("⭐ Гороскоп на сегодня", callback_data="horoscope")],
        [InlineKeyboardButton("🃏 Расклад Таро", callback_data="tarot")],
        [InlineKeyboardButton("🌙 Лунный календарь", callback_data="moon")],
        [InlineKeyboardButton("😴 Толкование сна", callback_data="dream")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compatibility")],
        [InlineKeyboardButton("👑 Совместимость со звездой", callback_data="celeb")],
        [InlineKeyboardButton("🌟 Прогноз на год", callback_data="yearly")],
        [InlineKeyboardButton("✍️ Нумерология имени", callback_data="name_num")],
        [InlineKeyboardButton("🍀 Число удачи сегодня", callback_data="lucky")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral")],
        [InlineKeyboardButton("⚙️ Мои данные", callback_data="my_data")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/astro_numerolog_ru")],
    ]
    if premium:
        rows.insert(0, [InlineKeyboardButton("✨ PREMIUM активен", callback_data="premium_info")])
    return InlineKeyboardMarkup(rows)

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/astro_numerolog_ru")]
    ])

def channel_promo():
    return "\n\n✨ *Подпишись на наш канал* — ежедневные гороскопы, лунный календарь и аффирмации: [Астро Нумеролог](https://t.me/astro_numerolog_ru)" 

CELEBRITIES = ["Илон Маск","Тейлор Свифт","Дрейк","Ариана Гранде","Криштиану Роналду","Билл Гейтс","Леди Гага","Джонни Депп"]

def celeb_keyboard():
    buttons = [[InlineKeyboardButton(c, callback_data=f"celeb_{c}")] for c in CELEBRITIES]
    buttons.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    track_user(uid, update.message.from_user)
    if is_blocked(uid):
        await update.message.reply_text("⛔ Вы заблокированы.")
        return
    # Реферальная ссылка
    args = context.args
    if args and args[0].startswith("ref"):
        try:
            ref_id = int(args[0][3:])
            if ref_id != uid and uid in all_users and not all_users[uid].get("ref_by"):
                all_users[uid]["ref_by"] = ref_id
                if ref_id in all_users:
                    all_users[ref_id]["referrals"] = all_users[ref_id].get("referrals", 0) + 1
                    add_premium(ref_id, 3)
                    try:
                        await context.bot.send_message(ref_id, "🎉 По твоей ссылке пришёл новый пользователь! +3 дня Premium в подарок!")
                    except:
                        pass
        except:
            pass
    user = get_user(uid)
    premium = is_premium(uid)
    if user.get("name"):
        days = get_premium_days_left(uid)
        prem_text = f"\n✨ Premium активен ещё {days} дн." if premium else ""
        text = (f"С возвращением, *{user['name']}*! 🌟{prem_text}\n\n"
                f"Знак: *{user.get('zodiac','?')}* | Число жизни: *{user.get('life_path','?')}*\n\n"
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
                "🌟 Прогноз на целый год\n"
                "🍀 Число удачи на сегодня\n\n"
                "Выбери что тебя интересует 👇\n\n"
                "📢 Подпишись на канал: [Астро Нумеролог](https://t.me/astro\_numerolog\_ru)")
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu(uid))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user = get_user(uid)
    data = query.data

    if data == "menu":
        await query.message.edit_text("Выбери что тебя интересует 👇", reply_markup=main_menu(uid))

    elif data == "premium_info":
        days = get_premium_days_left(uid)
        await query.message.reply_text(f"✨ *Твой Premium*\n\nОсталось: *{days} дней*\n\nВсе функции бота доступны!", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "daily_bonus":
        if can_daily_bonus(uid):
            claim_daily_bonus(uid)
            zodiac = user.get("zodiac", "Овен")
            bonus_text = ai_request(f"Мини-прогноз на сегодня для {zodiac}. 3-4 предложения. Позитивно, эмодзи.", 200)
            await query.message.reply_text(
                f"🎁 *Ежедневный бонус получен!*\n\n{bonus_text}\n\n"
                f"Приходи завтра за новым прогнозом! ✨",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            await query.message.reply_text("⏰ Ты уже получал бонус сегодня!\n\nПриходи завтра — каждый день новый прогноз 🌟", reply_markup=back_menu())

    elif data == "referral":
        refs = all_users.get(uid, {}).get("referrals", 0)
        ref_link = f"https://t.me/astro_numerolog_bot?start=ref{uid}"
        await query.message.reply_text(
            f"👥 *Пригласи друга — получи подарок!*\n\n"
            f"За каждого приглашённого друга ты получаешь *+3 дня Premium* бесплатно!\n\n"
            f"Твоя ссылка:\n`{ref_link}`\n\n"
            f"Приглашено друзей: *{refs}*\n"
            f"Заработано Premium дней: *{refs * 3}*\n\n"
            f"Отправь ссылку другу и оба получите бонус! 🎁",
            parse_mode="Markdown", reply_markup=back_menu())

    elif data == "my_data":
        if user.get("name"):
            days = get_premium_days_left(uid)
            prem = f"✨ Premium до {all_users.get(uid,{}).get('premium_until','—')}" if is_premium(uid) else "Нет Premium"
            text = (f"⚙️ *Твои данные:*\n\n"
                    f"👤 Имя: *{user['name']}*\n"
                    f"📅 Дата: *{user['date']}*\n"
                    f"♈ Знак: *{user['zodiac']}*\n"
                    f"🔢 Число жизни: *{user['life_path']}*\n"
                    f"🔮 Число судьбы: *{user['destiny']}*\n"
                    f"💎 Статус: {prem}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Изменить данные", callback_data="edit_data")],[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]])
        else:
            text = "У тебя пока нет сохранённых данных. Сделай нумерологический разбор!"
            keyboard = back_menu()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    elif data == "edit_data":
        user_states[uid] = {"action": "numerology", "step": "name"}
        await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "numerology":
        if user.get("name"):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Мои данные", callback_data="use_saved")],
                [InlineKeyboardButton("📝 Новые данные", callback_data="new_data_num")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
            await query.message.reply_text(f"У меня есть твои данные, *{user['name']}*! Использовать?", parse_mode="Markdown", reply_markup=keyboard)
        else:
            user_states[uid] = {"action": "numerology", "step": "name"}
            await query.message.reply_text("🔮 Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "use_saved":
        await query.message.reply_text(f"🔮 Считаю разбор для *{user['name']}*... ✨", parse_mode="Markdown")
        nums = calculate_numerology(user['date'], user['name'])
        reading = get_ai_reading(nums)
        await query.message.reply_text(f"*Разбор для {user['name']}*\n\n{reading}\n\n📊 Число жизни: *{nums['life_path']}* | Судьбы: *{nums['destiny']}* | *{nums['zodiac']}*\n\nПоделись ботом с другом! 👫", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "new_data_num":
        user_states[uid] = {"action": "numerology", "step": "name"}
        await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "horoscope":
        if user.get("zodiac"):
            await query.message.reply_text(f"⭐ Гороскоп для *{user['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(user["zodiac"])
            await query.message.reply_text(f"*Гороскоп для {user['name']} ({user['zodiac']})*\n\n{horoscope}\n\nПоделись! 🌟", parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[uid] = {"action": "horoscope", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "tarot":
        name = user.get("name")
        if name:
            await query.message.reply_text(f"🃏 Тяну карты для *{name}*... ✨", parse_mode="Markdown")
            result = get_tarot(name)
            await query.message.reply_text(f"*Расклад Таро для {name}*\n\n{result}\n\nПоделись! 🔮", parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[uid] = {"action": "tarot", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "moon":
        await query.message.reply_text("🌙 Составляю лунный календарь... ✨")
        result = get_moon_calendar()
        await query.message.reply_text(f"*Лунный календарь*\n\n{result}\n\nПоделись! 🌙", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "dream":
        if user.get("name"):
            user_states[uid] = {"action": "dream", "step": "dream", "dreamer": user["name"]}
            await query.message.reply_text("😴 Опиши свой сон подробно:")
        else:
            user_states[uid] = {"action": "dream", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "compatibility":
        user_states[uid] = {"action": "compatibility", "step": "name1"}
        await query.message.reply_text("💑 Напиши *своё имя*:", parse_mode="Markdown")

    elif data == "yearly":
        if user.get("name"):
            await query.message.reply_text(f"🌟 Составляю прогноз на год для *{user['name']}*... ✨\n\n_Это займёт немного дольше..._", parse_mode="Markdown")
            nums = calculate_numerology(user['date'], user['name'])
            result = get_yearly_forecast(nums)
            await query.message.reply_text(f"*Прогноз на год для {user['name']}*\n\n{result}\n\nПоделись! 🌟", parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[uid] = {"action": "yearly", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "name_num":
        user_states[uid] = {"action": "name_num", "step": "name"}
        await query.message.reply_text("✍️ Введи имя для анализа:", parse_mode="Markdown")

    elif data == "lucky":
        if user.get("name"):
            lnum = lucky_number(uid)
            result = get_lucky_day_forecast(user['name'], user.get('zodiac','Овен'), user.get('life_path', 1))
            await query.message.reply_text(f"🍀 *Число удачи сегодня: {lnum}*\n\n{result}\n\nПоделись! ✨", parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[uid] = {"action": "lucky", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "celeb":
        if user.get("name"):
            await query.message.reply_text(f"👑 *{user['name']}*, выбери знаменитость:", parse_mode="Markdown", reply_markup=celeb_keyboard())
        else:
            user_states[uid] = {"action": "celeb_name", "step": "name"}
            await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data.startswith("celeb_"):
        celeb = data[6:]
        name = user.get("name", "Пользователь")
        zodiac = user.get("zodiac", "Овен")
        life_path = user.get("life_path", 1)
        await query.message.reply_text(f"👑 Считаю совместимость *{name}* с *{celeb}*... ✨", parse_mode="Markdown")
        result = get_celebrity_compatibility(name, zodiac, life_path, celeb)
        await query.message.reply_text(f"*{name} + {celeb}*\n\n{result}\n\nПоделись! 👑", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "admin_test":
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text="Тестовый пост — бот работает! Канал подключён успешно ✅")
            await query.message.reply_text("✅ Пост отправлен в канал!")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")

    elif data == "admin_refresh":
        await show_admin_panel(query.message)

    elif data == "admin_new_contest":
        if query.from_user.id != ADMIN_ID:
            return
        user_states[query.from_user.id] = {"action": "admin_contest", "step": "days"}
        await query.message.reply_text(
            "🎉 *Создание конкурса*\n\n"
            "Шаг 1: Напиши количество дней Premium для победителя\n"
            "Например: *30*",
            parse_mode="Markdown"
        )

    elif data == "admin_give_premium":
        if query.from_user.id != ADMIN_ID:
            return
        user_states[query.from_user.id] = {"action": "admin_premium", "step": "uid"}
        users_list = "\n".join([f"ID: `{uid}` — {u['tg_name']}" for uid, u in list(all_users.items())[:15]])
        await query.message.reply_text(
            f"🎁 *Выдать Premium*\n\n"
            f"Список пользователей:\n{users_list}\n\n"
            f"Напиши ID пользователя:",
            parse_mode="Markdown"
        )

    elif data == "admin_broadcast":
        if query.from_user.id != ADMIN_ID:
            return
        user_states[query.from_user.id] = {"action": "admin_broadcast", "step": "text"}
        await query.message.reply_text(
            "📢 *Рассылка*\n\n"
            f"Получат сообщение: *{len(all_users)}* пользователей\n\n"
            "Напиши текст сообщения:",
            parse_mode="Markdown"
        )

    elif data.startswith("contest_win_"):
        parts = data.split("_")
        cid = parts[2]
        winner_id = int(parts[3])
        days = int(parts[4])
        if cid in contests:
            contests[cid]["winner_id"] = winner_id
            contests[cid]["active"] = False
            add_premium(winner_id, days)
            winner_name = all_users.get(winner_id, {}).get("tg_name", "—")
            try:
                await context.bot.send_message(winner_id, f"🎉 *Поздравляем!*\n\nТы выиграл в конкурсе *{contests[cid]['title']}*!\n\n🎁 Тебе начислено *{days} дней Premium* бесплатно!\n\nПриятного пользования ✨", parse_mode="Markdown")
            except:
                pass
            await query.message.reply_text(f"✅ Победитель выбран!\n\n👤 {winner_name}\n🎁 Начислено {days} дней Premium")

# ========== ADMIN PANEL ==========
async def show_admin_panel(message):
    total = len(all_users)
    with_data = len(users_db)
    blocked = sum(1 for u in all_users.values() if u.get("blocked"))
    premium_count = sum(1 for uid in all_users if is_premium(uid))
    active_contests = sum(1 for c in contests.values() if c.get("active"))
    text = (
        "*ПАНЕЛЬ АДМИНИСТРАТОРА*\n\n"
        "*Статистика:*\n"
        f"👥 Всего пользователей: *{total}*\n"
        f"📝 Заполнили профиль: *{with_data}*\n"
        f"✨ Premium пользователей: *{premium_count}*\n"
        f"⛔ Заблокировано: *{blocked}*\n"
        f"🎉 Активных конкурсов: *{active_contests}*\n\n"
        "*Пользователи:*\n"
    )
    if not all_users:
        text += "_Пока никто не писал боту_"
    else:
        for uid, u in list(all_users.items())[:20]:
            status = "⛔" if u.get("blocked") else ("✨" if is_premium(uid) else "✅")
            name = users_db.get(uid, {}).get("name", "—")
            text += f"{status} {u['tg_name']} | @{u.get('username','—')} | {name} | ID:{uid}\n"
        if len(all_users) > 20:
            text += f"\n...и ещё {len(all_users)-20} пользователей"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎉 Создать конкурс", callback_data="admin_new_contest")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin_give_premium")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🧪 Тест поста в канал", callback_data="admin_test")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")]
    ])
    await message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Нет доступа.")
        return
    await show_admin_panel(update.message)

async def test_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text="Тестовый пост — бот работает! ✅")
        await update.message.reply_text("✅ Пост отправлен!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def give_premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /premium 123456789 30\n(ID пользователя и количество дней)")
        return
    uid = int(context.args[0])
    days = int(context.args[1])
    add_premium(uid, days)
    winner_name = all_users.get(uid, {}).get("tg_name", "—")
    try:
        await context.bot.send_message(uid, f"🎁 *Подарок от Астро Нумеролога!*\n\nТебе начислено *{days} дней Premium* бесплатно!\n\nВсе функции бота теперь доступны ✨", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ Выдано {days} дней Premium пользователю {winner_name} (ID: {uid})")

async def block_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /block 123456789")
        return
    uid = int(context.args[0])
    if uid in all_users:
        all_users[uid]["blocked"] = True
        await update.message.reply_text(f"⛔ Пользователь {uid} заблокирован.")
    else:
        await update.message.reply_text("Пользователь не найден.")

async def unblock_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /unblock 123456789")
        return
    uid = int(context.args[0])
    if uid in all_users:
        all_users[uid]["blocked"] = False
        await update.message.reply_text(f"✅ Пользователь {uid} разблокирован.")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /broadcast Текст сообщения")
        return
    text = " ".join(context.args)
    sent = 0
    failed = 0
    for uid in all_users:
        if not all_users[uid].get("blocked"):
            try:
                await context.bot.send_message(uid, f"📢 *Сообщение от Астро Нумеролога:*\n\n{text}", parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
    await update.message.reply_text(f"📢 Рассылка завершена!\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")

async def contest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /contest 30 Название конкурса\n(дни Premium и название)")
        return
    days = int(context.args[0])
    title = " ".join(context.args[1:])
    cid = str(len(contests) + 1)
    contests[cid] = {"title": title, "days": days, "active": True, "winner_id": None}
    contest_text = (
        f"🎉 *КОНКУРС!*\n\n"
        f"*{title}*\n\n"
        f"🏆 Приз: *{days} дней Premium* бесплатно!\n\n"
        f"Для участия:\n"
        f"1. Подпишись на канал https://t.me/astro_numerolog_ru\n"
        f"2. Напиши боту /start\n"
        f"3. Поделись ботом с другом\n\n"
        f"Победитель выбирается случайно! Удачи! 🍀"
    )
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=contest_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Не удалось отправить в канал: {e}")
        return
    buttons = []
    for uid, u in list(all_users.items())[:10]:
        if not u.get("blocked"):
            name = u.get("tg_name", "—")
            buttons.append([InlineKeyboardButton(f"🏆 {name}", callback_data=f"contest_win_{cid}_{uid}_{days}")])
    buttons.append([InlineKeyboardButton("🎲 Случайный победитель", callback_data=f"contest_win_{cid}_{list(all_users.keys())[0] if all_users else 0}_{days}")])
    await update.message.reply_text(
        f"✅ Конкурс создан и опубликован в канале!\n\nВыбери победителя когда конкурс закончится:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ========== MESSAGE HANDLER ==========
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(uid, {})
    user = get_user(uid)
    if is_blocked(uid):
        return
    if not state:
        await update.message.reply_text("Выбери что тебя интересует 👇", reply_markup=main_menu(uid))
        return
    action = state.get("action")
    step = state.get("step")

    if action == "numerology":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"Привет, *{text}*! 👋\n\nДата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ (например 15.03.1990)")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"], "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text("🔮 Считаю разбор... ✨")
            reading = get_ai_reading(nums)
            await update.message.reply_text(f"*Разбор для {name}*\n\n{reading}\n\n📊 Число жизни: *{nums['life_path']}* | Судьбы: *{nums['destiny']}* | *{nums['zodiac']}*\n\nПоделись ботом с другом! 👫{channel_promo()}", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "horoscope":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"], "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text(f"⭐ Гороскоп для *{nums['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(nums["zodiac"])
            await update.message.reply_text(f"*Гороскоп для {name} ({nums['zodiac']})*\n\n{horoscope}\n\nПоделись! 🌟", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "tarot":
        if step == "name":
            save_user(uid, {**user, "name": text})
            await update.message.reply_text(f"🃏 Тяну карты для *{text}*... ✨", parse_mode="Markdown")
            result = get_tarot(text)
            await update.message.reply_text(f"*Расклад Таро для {text}*\n\n{result}\n\nПоделись! 🔮", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "dream":
        if step == "name":
            user_states[uid]["dreamer"] = text
            user_states[uid]["step"] = "dream"
            save_user(uid, {**user, "name": text})
            await update.message.reply_text("😴 Опиши свой сон подробно:")
        elif step == "dream":
            name = state.get("dreamer") or user.get("name", "Друг")
            await update.message.reply_text("🌙 Толкую сон... ✨")
            result = get_dream(name, text)
            await update.message.reply_text(f"*Толкование сна для {name}*\n\n{result}\n\nПоделись! 😴", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "compatibility":
        if step == "name1":
            user_states[uid]["name1"] = text
            user_states[uid]["step"] = "date1"
            await update.message.reply_text(f"*{text}* 👋\n\nТвоя дата *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date1":
            user_states[uid]["date1"] = text
            user_states[uid]["step"] = "name2"
            await update.message.reply_text("Имя *партнёра*:", parse_mode="Markdown")
        elif step == "name2":
            user_states[uid]["name2"] = text
            user_states[uid]["step"] = "date2"
            await update.message.reply_text(f"Дата *{text}* (ДД.ММ.ГГГГ):", parse_mode="Markdown")
        elif step == "date2":
            name1, date1, name2 = state["name1"], state["date1"], state["name2"]
            await update.message.reply_text("💑 Считаю совместимость... ✨")
            result = get_compatibility(name1, date1, name2, text)
            await update.message.reply_text(f"*Совместимость {name1} и {name2}*\n\n{result}\n\nПоделись! 💫", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "yearly":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"], "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text(f"🌟 Составляю прогноз на год для *{name}*... ✨\n_Это займёт немного дольше..._", parse_mode="Markdown")
            result = get_yearly_forecast(nums)
            await update.message.reply_text(f"*Прогноз на год для {name}*\n\n{result}\n\nПоделись! 🌟{channel_promo()}", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "name_num":
        if step == "name":
            await update.message.reply_text(f"✍️ Анализирую имя *{text}*... ✨", parse_mode="Markdown")
            result = get_name_numerology(text)
            await update.message.reply_text(f"*Нумерология имени {text}*\n\n{result}\n\nПоделись! ✨", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "lucky":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши ДД.ММ.ГГГГ")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"], "life_path": nums["life_path"], "destiny": nums["destiny"]})
            lnum = lucky_number(uid)
            result = get_lucky_day_forecast(name, nums["zodiac"], nums["life_path"])
            await update.message.reply_text(f"🍀 *Число удачи сегодня: {lnum}*\n\n{result}\n\nПоделись! ✨", parse_mode="Markdown", reply_markup=back_menu())
            user_states.pop(uid, None)

    elif action == "admin_contest":
        if uid != ADMIN_ID:
            return
        if step == "days":
            try:
                days = int(text)
                user_states[uid]["days"] = days
                user_states[uid]["step"] = "title"
                await update.message.reply_text(f"✅ Приз: {days} дней Premium\n\nТеперь напиши *название конкурса*:", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Напиши число, например: 30")
        elif step == "title":
            days = user_states[uid]["days"]
            title = text
            cid = str(len(contests) + 1)
            contests[cid] = {"title": title, "days": days, "active": True, "winner_id": None}
            contest_text = (
                f"🎉 *КОНКУРС!*\n\n"
                f"*{title}*\n\n"
                f"🏆 Приз: *{days} дней Premium* бесплатно!\n\n"
                f"Для участия:\n"
                f"1. Подпишись на канал https://t.me/astro_numerolog_ru\n"
                f"2. Напиши боту /start\n"
                f"3. Поделись ботом с другом\n\n"
                f"Победитель выбирается случайно! Удачи! 🍀"
            )
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=contest_text, parse_mode="Markdown")
                await update.message.reply_text("✅ Конкурс опубликован в канале!")
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка публикации: {e}")
            buttons = []
            for u_id, u_data in list(all_users.items())[:10]:
                if not u_data.get("blocked"):
                    buttons.append([InlineKeyboardButton(f"🏆 {u_data.get('tg_name','—')}", callback_data=f"contest_win_{cid}_{u_id}_{days}")])
            if all_users:
                rand_uid = random.choice(list(all_users.keys()))
                buttons.append([InlineKeyboardButton("🎲 Случайный победитель", callback_data=f"contest_win_{cid}_{rand_uid}_{days}")])
            if buttons:
                await update.message.reply_text("Выбери победителя когда конкурс закончится:", reply_markup=InlineKeyboardMarkup(buttons))
            user_states.pop(uid, None)

    elif action == "admin_premium":
        if uid != ADMIN_ID:
            return
        if step == "uid":
            try:
                target_uid = int(text)
                user_states[uid]["target_uid"] = target_uid
                user_states[uid]["step"] = "days"
                target_name = all_users.get(target_uid, {}).get("tg_name", "—")
                await update.message.reply_text(f"👤 Пользователь: *{target_name}*\n\nСколько дней Premium выдать?", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Напиши числовой ID пользователя")
        elif step == "days":
            try:
                days = int(text)
                target_uid = user_states[uid]["target_uid"]
                add_premium(target_uid, days)
                target_name = all_users.get(target_uid, {}).get("tg_name", "—")
                try:
                    await context.bot.send_message(target_uid, f"🎁 *Подарок!*\n\nТебе начислено *{days} дней Premium* бесплатно! ✨", parse_mode="Markdown")
                except:
                    pass
                await update.message.reply_text(f"✅ Выдано {days} дней Premium пользователю {target_name}!")
                user_states.pop(uid, None)
            except:
                await update.message.reply_text("❌ Напиши число дней, например: 30")

    elif action == "admin_broadcast":
        if uid != ADMIN_ID:
            return
        if step == "text":
            msg_text = text
            await update.message.reply_text("📢 Начинаю рассылку...")
            sent, failed = 0, 0
            for u_id in all_users:
                if not all_users[u_id].get("blocked"):
                    try:
                        await context.bot.send_message(u_id, f"📢 *Сообщение от Астро Нумеролога:*\n\n{msg_text}", parse_mode="Markdown")
                        sent += 1
                    except:
                        failed += 1
            await update.message.reply_text(f"✅ Рассылка завершена!\n\nОтправлено: {sent}\nОшибок: {failed}")
            user_states.pop(uid, None)

    elif action == "celeb_name":
        if step == "name":
            save_user(uid, {**user, "name": text})
            user_states.pop(uid, None)
            await update.message.reply_text(f"👑 *{text}*, выбери знаменитость:", parse_mode="Markdown", reply_markup=celeb_keyboard())

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue
    jq.run_daily(post_morning_horoscope, time=time(5, 0))
    jq.run_daily(post_affirmation, time=time(9, 0))
    jq.run_daily(post_moon, time=time(12, 0))
    jq.run_daily(post_evening_wish, time=time(16, 0))
    jq.run_daily(post_sleep_advice, time=time(18, 0))
    jq.run_daily(post_weekly_tarot, time=time(15, 0), days=(4,))
    jq.run_daily(post_weekly_numerology, time=time(7, 0), days=(6,))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("test_post", test_post))
    app.add_handler(CommandHandler("premium", give_premium_cmd))
    app.add_handler(CommandHandler("block", block_user_cmd))
    app.add_handler(CommandHandler("unblock", unblock_user_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("contest", contest_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
