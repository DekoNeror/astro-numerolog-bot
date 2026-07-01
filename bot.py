import os
import json
import logging
import random
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

# ========== КОНФИГ ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CHANNEL_ID = "@astro_numerolog_ru"
ADMIN_ID = 1473856140
BOT_USERNAME = "astro_numerolog_bot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
groq_client = Groq(api_key=GROQ_API_KEY)

# ========== БАЗА ДАННЫХ ==========
DB_FILE = "bot_data.json"
users_db = {}
all_users = {}
user_states = {}
contests = {}
sent_posts = {}

def load_db():
    global users_db, all_users, contests, sent_posts
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            users_db = {int(k): v for k, v in data.get("users_db", {}).items()}
            all_users = {int(k): v for k, v in data.get("all_users", {}).items()}
            contests = data.get("contests", {})
            sent_posts = data.get("sent_posts", {})
            logger.info(f"База загружена: {len(all_users)} пользователей")
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")

def save_db():
    try:
        data = {
            "users_db": {str(k): v for k, v in users_db.items()},
            "all_users": {str(k): v for k, v in all_users.items()},
            "contests": contests,
            "sent_posts": sent_posts
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def can_send_post(key):
    today = datetime.now().strftime("%d.%m.%Y")
    lock_key = f"{key}_{today}"
    lock_file = f"lock_{key}.txt"
    if sent_posts.get(lock_key):
        return False
    try:
        if os.path.exists(lock_file):
            with open(lock_file, "r") as f:
                if f.read().strip() == today:
                    sent_posts[lock_key] = True
                    return False
        with open(lock_file, "w") as f:
            f.write(today)
    except Exception as e:
        logger.error(f"Lock error: {e}")
    sent_posts[lock_key] = True
    save_db()
    return True

# ========== ПОЛЬЗОВАТЕЛИ ==========
def save_user(uid, data):
    users_db[uid] = data
    save_db()

def get_user(uid):
    return users_db.get(uid, {})

def has_profile(uid):
    return bool(users_db.get(uid, {}).get("name"))

def track_user(uid, tg_user):
    changed = False
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
        changed = True
    else:
        if all_users[uid].get("tg_name") != tg_user.full_name:
            all_users[uid]["tg_name"] = tg_user.full_name
            changed = True
        if tg_user.username and all_users[uid].get("username") != tg_user.username:
            all_users[uid]["username"] = tg_user.username
            changed = True
    if changed:
        save_db()

def is_blocked(uid):
    return all_users.get(uid, {}).get("blocked", False)

def is_premium(uid):
    p = all_users.get(uid, {}).get("premium_until")
    if p:
        try:
            return datetime.now() < datetime.strptime(p, "%d.%m.%Y")
        except:
            pass
    return False

def get_premium_days_left(uid):
    p = all_users.get(uid, {}).get("premium_until")
    if p:
        try:
            return max(0, (datetime.strptime(p, "%d.%m.%Y") - datetime.now()).days)
        except:
            pass
    return 0

def add_premium(uid, days):
    if uid not in all_users:
        all_users[uid] = {"tg_name": "—", "username": "—", "joined": "—",
                          "blocked": False, "premium_until": None, "referrals": 0,
                          "daily_bonus_date": None, "ref_by": None}
    p = all_users[uid].get("premium_until")
    base = datetime.now()
    if p:
        try:
            d = datetime.strptime(p, "%d.%m.%Y")
            if d > base:
                base = d
        except:
            pass
    all_users[uid]["premium_until"] = (base + timedelta(days=days)).strftime("%d.%m.%Y")
    save_db()

def can_daily_bonus(uid):
    last = all_users.get(uid, {}).get("daily_bonus_date")
    return last != datetime.now().strftime("%d.%m.%Y")

def claim_daily_bonus(uid):
    if uid in all_users:
        all_users[uid]["daily_bonus_date"] = datetime.now().strftime("%d.%m.%Y")
        save_db()

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
    ru_map = {'а':1,'б':2,'в':6,'г':3,'д':4,'е':5,'ё':5,'ж':2,'з':7,'и':1,'й':1,
              'к':2,'л':3,'м':4,'н':5,'о':7,'п':8,'р':9,'с':1,'т':2,'у':6,'ф':8,
              'х':5,'ц':4,'ч':6,'ш':2,'щ':3,'ъ':4,'ы':2,'ь':2,'э':5,'ю':6,'я':1}
    destiny = sum(ru_map.get(c.lower(), 0) for c in name if c.isalpha())
    while destiny > 9 and destiny not in (11, 22, 33):
        destiny = sum(int(d) for d in str(destiny))
    zodiac_list = [(1,20,"Козерог"),(2,19,"Водолей"),(3,20,"Рыбы"),(4,20,"Овен"),
                   (5,21,"Телец"),(6,21,"Близнецы"),(7,23,"Рак"),(8,23,"Лев"),
                   (9,23,"Дева"),(10,23,"Весы"),(11,22,"Скорпион"),(12,22,"Стрелец"),(12,31,"Козерог")]
    zodiac = "Козерог"
    for z_month, z_day, z_name in zodiac_list:
        if date.month < z_month or (date.month == z_month and date.day <= z_day):
            zodiac = z_name
            break
    return {"life_path": life_path, "destiny": destiny, "zodiac": zodiac,
            "birth_day": date.day, "birth_month": date.month, "birth_year": date.year, "name": name}

def lucky_number(uid):
    today = datetime.now().strftime("%d%m%Y")
    random.seed(int(str(abs(uid)) + today))
    return random.randint(1, 9)

# ========== AI ==========
def ai_request(prompt, max_tokens=1000):
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=0.8
        )
        return r.choices[0].message.content
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "Звёзды молчат... Попробуй ещё раз 🔮"

def get_ai_reading(nums):
    return ai_request(f"""Ты опытный нумеролог и астролог. Сделай персональный разбор.
Имя: {nums['name']}, Знак: {nums['zodiac']}, Число жизни: {nums['life_path']}, Число судьбы: {nums['destiny']}
Дата: {nums['birth_day']}.{nums['birth_month']}.{nums['birth_year']}
Структура ответа:
🌟 Характеристика личности (3-4 предложения)
💫 Число жизненного пути {nums['life_path']} — что означает
🔮 Число судьбы {nums['destiny']} — твоя миссия
♈ {nums['zodiac']} — ключевые черты
💰 Прогноз на ближайший месяц
✨ Главный совет от нумеролога
Пиши по-русски, тепло, на "ты", 300-400 слов, используй эмодзи.""")

def get_daily_horoscope(zodiac):
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Составь детальный гороскоп на {today} для знака {zodiac}.
🌅 Общая энергия дня
❤️ Любовь и отношения
💼 Карьера и финансы
🌿 Здоровье и энергия
🎯 Главный совет дня
Пиши по-русски, позитивно, 150-200 слов, эмодзи.""", 500)

def get_tarot(name):
    cards = ["Маг","Жрица","Императрица","Император","Иерофант","Влюблённые",
             "Колесница","Сила","Отшельник","Колесо Фортуны","Справедливость",
             "Повешенный","Смерть","Умеренность","Дьявол","Башня","Звезда",
             "Луна","Солнце","Суд","Мир","Шут"]
    drawn = random.sample(cards, 3)
    return ai_request(f"""Ты опытный таролог. Расклад "Прошлое-Настоящее-Будущее" для {name}.
🃏 Прошлое — карта "{drawn[0]}"
🃏 Настоящее — карта "{drawn[1]}"
🃏 Будущее — карта "{drawn[2]}"
Для каждой карты: значение + как влияет на ситуацию.
Финальный вывод: общий посыл расклада.
Пиши мистично, по-русски, 200-250 слов, эмодзи 🔮.""", 600)

def get_moon_calendar():
    today = datetime.now().strftime("%d.%m.%Y")
    return ai_request(f"""Лунный календарь на {today}.
🌙 Фаза луны и её влияние
✅ Что благоприятно делать сегодня
❌ Чего лучше избегать
💼 Влияние на бизнес и финансы
❤️ Влияние на отношения
🌿 Влияние на здоровье
Пиши по-русски, конкретно, 180-200 слов, эмодзи.""", 500)

def get_dream(name, dream):
    return ai_request(f"""Ты мистический толкователь снов. {name} увидел сон: "{dream}"
Расшифруй символы и послание сна.
😴 Главный символ сна и его значение
🌙 Что подсознание пытается сказать
🔮 Предсказание — что этот сон означает для будущего
✨ Практический совет на основе сна
Пиши загадочно и мудро, по-русски, 200-250 слов, эмодзи.""", 600)

def get_compatibility(name1, date1, name2, date2):
    n1 = calculate_numerology(date1, name1)
    n2 = calculate_numerology(date2, name2)
    if not n1 or not n2:
        return None
    return ai_request(f"""Нумеролог. Анализ совместимости двух людей.
{name1}: {n1['zodiac']}, число жизни {n1['life_path']}, число судьбы {n1['destiny']}
{name2}: {n2['zodiac']}, число жизни {n2['life_path']}, число судьбы {n2['destiny']}
💑 Процент совместимости и общий вывод
❤️ Совместимость в любви и романтике
🤝 Совместимость в дружбе и общении
💼 Совместимость в работе и делах
⚡ Возможные сложности и как их преодолеть
✨ Главный совет для гармоничных отношений
Пиши по-русски, 250 слов, эмодзи.""", 700)

def get_celebrity_compatibility(name, zodiac, life_path, celeb):
    return ai_request(f"""Нумеролог. Совместимость {name} ({zodiac}, число жизни {life_path}) с {celeb}.
💑 Процент совместимости
❤️ Как сложились бы отношения
🤝 Что общего между вами
⚡ В чём различия
✨ Забавный вывод
Пиши весело и легко, по-русски, 200 слов, эмодзи.""", 500)

def get_yearly_forecast(nums):
    return ai_request(f"""Нумеролог. Прогноз на год для {nums['name']}.
Знак: {nums['zodiac']}, число жизни: {nums['life_path']}, судьбы: {nums['destiny']}
🌱 Январь-Март: главные события и возможности
☀️ Апрель-Июнь: пиковые моменты
🍂 Июль-Сентябрь: трансформации
❄️ Октябрь-Декабрь: итоги и подготовка
💰 Финансовый прогноз года
❤️ Личная жизнь — чего ждать
💼 Карьера и развитие
✨ Главное слово года
Пиши вдохновляюще, по-русски, 400-500 слов, эмодзи.""", 1000)

def get_name_numerology(name):
    return ai_request(f"""Нумеролог. Полный анализ имени "{name}".
🔢 Числовое значение и его расшифровка
✨ Что имя говорит о характере человека
💫 Сильные стороны носителей этого имени
⚡ Слабые стороны и зоны роста
🎯 Жизненное предназначение по имени
🌟 Как использовать силу своего имени
Пиши по-русски, 250-300 слов, эмодзи.""", 700)

def get_lucky_day_forecast(name, zodiac, life_path, uid):
    lnum = lucky_number(uid)
    return ai_request(f"""Нумеролог. Прогноз удачи на сегодня для {name}.
Знак: {zodiac}, число жизни: {life_path}, число удачи: {lnum}
🍀 Число удачи {lnum} — что оно означает именно сегодня
⭐ Лучшее время для важных решений и дел
💚 Что принесёт удачу сегодня
🔴 Чего стоит избегать
💫 Аффирмация дня специально для тебя
Пиши по-русски, позитивно, 200 слов, эмодзи.""", 500)

def get_oracle_answer(name, question):
    return ai_request(f"""Ты древний мистический Оракул. {name} задаёт вопрос: "{question}"
Дай мудрый и вдохновляющий ответ.
🔮 Видение Оракула — прямой ответ на вопрос
⚡ Что нужно сделать прямо сейчас
🌟 На какой знак или совпадение обратить внимание
✨ Послание-напутствие в одной фразе
Пиши загадочно и мудро, по-русски, на "ты", 200-250 слов, эмодзи.""", 600)

# ========== АВТОПОСТИНГ ==========
ZODIACS = ["♈ Овен","♉ Телец","♊ Близнецы","♋ Рак","♌ Лев","♍ Дева",
           "♎ Весы","♏ Скорпион","♐ Стрелец","♑ Козерог","♒ Водолей","♓ Рыбы"]

async def post_morning_horoscope(context):
    if not can_send_post('morning_horoscope'): return
    today = datetime.now().strftime("%d.%m.%Y")
    try:
        text = ai_request(f"""Гороскоп на {today} для всех 12 знаков зодиака.
Для каждого знака напиши 2-3 предложения о главном событии дня.
Формат:
♈ Овен — ...
♉ Телец — ...
♊ Близнецы — ...
♋ Рак — ...
♌ Лев — ...
♍ Дева — ...
♎ Весы — ...
♏ Скорпион — ...
♐ Стрелец — ...
♑ Козерог — ...
♒ Водолей — ...
♓ Рыбы — ...
Пиши ТОЛЬКО по-русски, позитивно, без вступлений.""", 1200)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🌅 *Гороскоп на {today}*\n\n{text}\n\n🔮 Персональный разбор — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_affirmation(context):
    if not can_send_post('affirmation'): return
    try:
        text = ai_request("Напиши вдохновляющую аффирмацию дня. Одна мощная фраза на ты + 3-4 предложения объяснения. Только по-русски, эмодзи ✨💫. Без вступлений.", 300)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"💫 *Аффирмация дня*\n\n{text}\n\n🔮 Узнай своё число судьбы — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_moon(context):
    if not can_send_post('moon'): return
    try:
        text = get_moon_calendar()
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🌙 *Лунный календарь*\n\n{text}\n\n🔮 Персональный прогноз — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_evening_wish(context):
    if not can_send_post('evening_wish'): return
    try:
        text = ai_request("Напиши тёплое вечернее послание от Вселенной. 4-5 предложений. Мистично, душевно, на ты. Только по-русски. Эмодзи 🌟✨🔮. Без вступлений.", 300)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🌟 *Послание Вселенной*\n\n{text}\n\n🔮 Что звёзды говорят лично тебе — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_sleep_advice(context):
    if not can_send_post('sleep_advice'): return
    try:
        text = ai_request("Напиши мистический совет перед сном. Как зарядиться ночью, что загадать звёздам. 4-5 предложений. Спокойно, тепло, на ты. Только по-русски. Эмодзи 😴🌙✨. Без вступлений.", 300)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"😴 *Совет перед сном*\n\n{text}\n\n🔮 Толкование снов — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_weekly_tarot(context):
    if not can_send_post('weekly_tarot'): return
    try:
        card = random.choice(["Маг","Жрица","Императрица","Сила","Звезда","Луна","Солнце","Мир","Колесо Фортуны"])
        text = ai_request(f"Карта Таро недели для всех — {card}. Что означает в любви, работе, финансах, здоровье. Только по-русски, 200-250 слов, эмодзи 🃏🔮. Без вступлений.", 500)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🃏 *Карта Таро недели — {card}*\n\n{text}\n\n🔮 Личный расклад — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

async def post_weekly_numerology(context):
    if not can_send_post('weekly_numerology'): return
    try:
        week = datetime.now().strftime("%d.%m.%Y")
        text = ai_request(f"Нумерологический прогноз на неделю с {week}. Для чисел 1, 2, 3, 4, 5, 6, 7, 8, 9. Для каждого числа 2-3 предложения. Только по-русски, эмодзи 🔢✨. Без вступлений.", 800)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"🔢 *Нумерологический прогноз недели*\n\n{text}\n\n🔮 Узнай своё число — @{BOT_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Post error: {e}")

# ========== PREMIUM GATE ==========
def premium_required(uid):
    """Возвращает True если нужен Premium (пользователь не premium)"""
    return not is_premium(uid)

def premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Получить Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("👥 Пригласить друга (+3 дня)", callback_data="referral")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
    ])

# ========== КЛАВИАТУРЫ ==========
def main_menu(uid=None):
    premium = is_premium(uid) if uid else False
    rows = [
        [InlineKeyboardButton("🔮 Нумерологический разбор", callback_data="numerology")],
        [InlineKeyboardButton("⭐ Гороскоп на сегодня", callback_data="horoscope")],
        [InlineKeyboardButton("🌙 Лунный календарь" + (" 🔒" if not premium else ""), callback_data="moon")],
        [InlineKeyboardButton("😴 Толкование сна", callback_data="dream")],
        [InlineKeyboardButton("💑 Совместимость с партнёром", callback_data="compatibility")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("— — — PREMIUM — — —", callback_data="premium_info")],
        [InlineKeyboardButton("🃏 Расклад Таро" + (" 🔒" if not premium else ""), callback_data="tarot")],
        [InlineKeyboardButton("👑 Совместимость со звездой" + (" 🔒" if not premium else ""), callback_data="celeb")],
        [InlineKeyboardButton("🌟 Прогноз на год" + (" 🔒" if not premium else ""), callback_data="yearly")],
        [InlineKeyboardButton("✍️ Нумерология имени" + (" 🔒" if not premium else ""), callback_data="name_num")],
        [InlineKeyboardButton("🍀 Число удачи" + (" 🔒" if not premium else ""), callback_data="lucky")],
        [InlineKeyboardButton("🔮 Вопрос Оракулу" + (" 🔒" if not premium else ""), callback_data="oracle")],
        [InlineKeyboardButton("— — — — — — — — —", callback_data="noop")],
        [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral"),
         InlineKeyboardButton("⚙️ Мои данные", callback_data="my_data")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/astro_numerolog_ru")]
    ]
    return InlineKeyboardMarkup(rows)

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")],
        [InlineKeyboardButton("📢 Наш канал", url="https://t.me/astro_numerolog_ru")]
    ])

CELEBRITIES = ["Илон Маск","Тейлор Свифт","Дрейк","Ариана Гранде",
               "Криштиану Роналду","Билл Гейтс","Леди Гага","Джонни Депп"]

def celeb_keyboard():
    buttons = [[InlineKeyboardButton(c, callback_data=f"celeb_{c}")] for c in CELEBRITIES]
    buttons.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)

# ========== START ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    track_user(uid, update.message.from_user)
    if is_blocked(uid):
        await update.message.reply_text("⛔ Вы заблокированы.")
        return
    # Реферал
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
                        await context.bot.send_message(ref_id,
                            "🎉 По твоей ссылке пришёл новый пользователь!\n\n✨ *+3 дня Premium* начислено автоматически!",
                            parse_mode="Markdown")
                    except:
                        pass
                save_db()
        except:
            pass
    user = get_user(uid)
    premium = is_premium(uid)
    if user.get("name"):
        days = get_premium_days_left(uid)
        prem_text = f"\n✨ *Premium* активен ещё {days} дн." if premium else ""
        text = (f"С возвращением, *{user['name']}*! 🌟{prem_text}\n\n"
                f"♈ Знак: *{user.get('zodiac','?')}* | 🔢 Число жизни: *{user.get('life_path','?')}*\n\n"
                f"Выбери что тебя интересует 👇")
    else:
        text = ("🌟 *Добро пожаловать в Астро Нумеролог!*\n\n"
                "Узнай тайны своей судьбы:\n"
                "✨ Число судьбы и жизненного пути\n"
                "🔮 Персональный нумерологический разбор\n"
                "⭐ Гороскоп на каждый день\n"
                "💑 Совместимость с партнёром\n"
                "😴 Толкование снов\n"
                "🌟 Прогноз на целый год и многое другое\n\n"
                "Выбери что тебя интересует 👇")
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu(uid))

# ========== КНОПКИ ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user = get_user(uid)
    data = query.data

    # Заглушка для разделителей
    if data == "noop":
        return

    if data == "menu":
        text = f"Выбери что тебя интересует 👇"
        if user.get("name"):
            premium = is_premium(uid)
            days = get_premium_days_left(uid)
            prem_text = f"\n✨ Premium активен ещё {days} дн." if premium else ""
            text = f"С возвращением, *{user['name']}*! 🌟{prem_text}\n\n{text}"
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu(uid))

    # ===== БЕСПЛАТНЫЕ ФУНКЦИИ =====

    elif data == "numerology":
        if user.get("name"):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ Использовать данные {user['name']}", callback_data="use_saved")],
                [InlineKeyboardButton("📝 Ввести другие данные", callback_data="new_data_num")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
            await query.message.edit_text(
                f"🔮 У меня уже есть твои данные!\n\n"
                f"👤 *{user['name']}*\n"
                f"📅 {user['date']}\n"
                f"♈ {user['zodiac']} | 🔢 Число жизни: {user['life_path']}",
                parse_mode="Markdown", reply_markup=kb)
        else:
            user_states[uid] = {"action": "numerology", "step": "name"}
            await query.message.reply_text("🔮 Давай начнём!\n\nНапиши своё *имя*:", parse_mode="Markdown")

    elif data == "use_saved":
        await query.message.reply_text(f"🔮 Считаю разбор для *{user['name']}*... ✨", parse_mode="Markdown")
        nums = calculate_numerology(user['date'], user['name'])
        reading = get_ai_reading(nums)
        await query.message.reply_text(
            f"*Нумерологический разбор для {user['name']}*\n\n{reading}\n\n"
            f"📊 Число жизни: *{nums['life_path']}* | Судьбы: *{nums['destiny']}* | *{nums['zodiac']}*",
            parse_mode="Markdown", reply_markup=back_menu())

    elif data == "new_data_num":
        user_states[uid] = {"action": "numerology", "step": "name"}
        await query.message.reply_text("Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "horoscope":
        if user.get("zodiac"):
            await query.message.reply_text(f"⭐ Гороскоп для *{user['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(user["zodiac"])
            await query.message.reply_text(
                f"*Гороскоп для {user['name']} ({user['zodiac']})*\n\n{horoscope}",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            user_states[uid] = {"action": "horoscope", "step": "name"}
            await query.message.reply_text("⭐ Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "dream":
        # Бесплатно — безлимит
        if user.get("name"):
            user_states[uid] = {"action": "dream", "step": "dream", "name": user["name"]}
            await query.message.reply_text(
                f"😴 *{user['name']}*, опиши свой сон как можно подробнее.\n\nЧто происходило? Кто был? Какие ощущения? 👇",
                parse_mode="Markdown")
        else:
            user_states[uid] = {"action": "dream", "step": "name"}
            await query.message.reply_text("😴 Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "compatibility":
        # Бесплатно
        if user.get("name"):
            user_states[uid] = {"action": "compatibility", "step": "name2",
                                 "name1": user["name"], "date1": user["date"]}
            await query.message.reply_text(
                f"💑 Считаю совместимость для *{user['name']}*\n\nНапиши *имя партнёра*:",
                parse_mode="Markdown")
        else:
            user_states[uid] = {"action": "compatibility", "step": "name1"}
            await query.message.reply_text("💑 Напиши *своё имя*:", parse_mode="Markdown")

    elif data == "daily_bonus":
        if can_daily_bonus(uid):
            claim_daily_bonus(uid)
            zodiac = user.get("zodiac", "Овен")
            bonus_text = ai_request(
                f"Мини-прогноз на сегодня для {zodiac}. 3-4 предложения. Позитивно, вдохновляюще. По-русски, эмодзи.", 200)
            await query.message.reply_text(
                f"🎁 *Ежедневный бонус получен!*\n\n{bonus_text}\n\n"
                f"Приходи завтра за новым прогнозом! ✨",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            await query.message.reply_text(
                "⏰ *Бонус уже получен!*\n\nПриходи завтра — каждый день новый прогноз 🌟",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== PREMIUM ФУНКЦИИ =====

    elif data == "moon":
        if premium_required(uid):
            await query.message.reply_text(
                "🌙 *Лунный календарь* — функция Premium\n\n"
                "Получи доступ к лунному календарю, раскладам Таро, прогнозу на год и многому другому!\n\n"
                "✨ Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            await query.message.reply_text("🌙 Составляю лунный календарь... ✨")
            result = get_moon_calendar()
            await query.message.reply_text(f"*Лунный календарь*\n\n{result}", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "tarot":
        if premium_required(uid):
            await query.message.reply_text(
                "🃏 *Расклад Таро* — функция Premium\n\n"
                "Открой доступ к раскладам Таро, прогнозу на год, числу удачи и Оракулу!\n\n"
                "✨ Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            name = user.get("name", "Друг")
            await query.message.reply_text(f"🃏 Тяну карты для *{name}*... ✨", parse_mode="Markdown")
            result = get_tarot(name)
            await query.message.reply_text(f"*Расклад Таро для {name}*\n\n{result}", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "celeb":
        if premium_required(uid):
            await query.message.reply_text(
                "👑 *Совместимость со звёздами* — функция Premium\n\n"
                "Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            name = user.get("name", "Друг")
            await query.message.reply_text(f"👑 *{name}*, выбери знаменитость:", parse_mode="Markdown", reply_markup=celeb_keyboard())

    elif data.startswith("celeb_"):
        celeb = data[6:]
        name = user.get("name", "Пользователь")
        zodiac = user.get("zodiac", "Овен")
        life_path = user.get("life_path", 1)
        await query.message.reply_text(f"👑 Считаю совместимость *{name}* с *{celeb}*... ✨", parse_mode="Markdown")
        result = get_celebrity_compatibility(name, zodiac, life_path, celeb)
        await query.message.reply_text(f"*{name} + {celeb}*\n\n{result}", parse_mode="Markdown", reply_markup=back_menu())

    elif data == "yearly":
        if premium_required(uid):
            await query.message.reply_text(
                "🌟 *Прогноз на год* — функция Premium\n\n"
                "Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            if user.get("name"):
                await query.message.reply_text(f"🌟 Составляю прогноз на год для *{user['name']}*... ✨\n\n_Это займёт немного дольше..._", parse_mode="Markdown")
                nums = calculate_numerology(user['date'], user['name'])
                result = get_yearly_forecast(nums)
                await query.message.reply_text(f"*Прогноз на год для {user['name']}*\n\n{result}", parse_mode="Markdown", reply_markup=back_menu())
            else:
                user_states[uid] = {"action": "yearly", "step": "name"}
                await query.message.reply_text("🌟 Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "name_num":
        if premium_required(uid):
            await query.message.reply_text(
                "✍️ *Нумерология имени* — функция Premium\n\n"
                "Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            user_states[uid] = {"action": "name_num", "step": "name"}
            await query.message.reply_text("✍️ Введи *имя* для анализа:", parse_mode="Markdown")

    elif data == "lucky":
        if premium_required(uid):
            await query.message.reply_text(
                "🍀 *Число удачи* — функция Premium\n\n"
                "Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            if user.get("name"):
                lnum = lucky_number(uid)
                result = get_lucky_day_forecast(user['name'], user.get('zodiac','Овен'), user.get('life_path', 1), uid)
                await query.message.reply_text(f"🍀 *Число удачи сегодня: {lnum}*\n\n{result}", parse_mode="Markdown", reply_markup=back_menu())
            else:
                user_states[uid] = {"action": "lucky", "step": "name"}
                await query.message.reply_text("🍀 Напиши своё *имя*:", parse_mode="Markdown")

    elif data == "oracle":
        if premium_required(uid):
            await query.message.reply_text(
                "🔮 *Вопрос Оракулу* — функция Premium\n\n"
                "Пригласи друга и получи *3 дня Premium бесплатно*!",
                parse_mode="Markdown", reply_markup=premium_keyboard())
        else:
            name = user.get("name", "Друг")
            user_states[uid] = {"action": "oracle", "step": "question", "name": name}
            await query.message.reply_text(
                "🔮 *Оракул слушает тебя...*\n\nЗадай любой вопрос — о любви, карьере, будущем или выборе.\n\nНапиши свой вопрос 👇",
                parse_mode="Markdown")

    # ===== ОБЩЕЕ =====

    elif data == "premium_info":
        if is_premium(uid):
            days = get_premium_days_left(uid)
            await query.message.reply_text(
                f"✨ *Твой Premium*\n\nОсталось: *{days} дней*\n\n"
                f"Доступны все функции бота!\n\n"
                f"👥 Пригласи друга — получи ещё +3 дня",
                parse_mode="Markdown", reply_markup=back_menu())
        else:
            await query.message.reply_text(
                "✨ *Premium — открой все возможности!*\n\n"
                "🃏 Расклад Таро\n"
                "🌙 Лунный календарь\n"
                "🌟 Прогноз на год\n"
                "✍️ Нумерология имени\n"
                "🍀 Число удачи каждый день\n"
                "👑 Совместимость со звёздами\n"
                "🔮 Вопрос Оракулу\n\n"
                "💡 *Как получить бесплатно:*\n"
                "👥 Пригласи друга → +3 дня Premium\n"
                "10 друзей = 1 месяц бесплатно!",
                parse_mode="Markdown", reply_markup=premium_keyboard())

    elif data == "buy_premium":
        await query.message.reply_text(
            "💎 *Получить Premium*\n\n"
            "🆓 *Бесплатно:*\n"
            "👥 Пригласи друга → +3 дня\n\n"
            "💳 *Скоро:* оплата через Telegram Stars\n\n"
            "Пока используй реферальную ссылку — это совершенно бесплатно! 🎁",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Пригласить друга", callback_data="referral")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ]))

    elif data == "referral":
        refs = all_users.get(uid, {}).get("referrals", 0)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{uid}"
        await query.message.reply_text(
            f"👥 *Пригласи друга — получи Premium!*\n\n"
            f"За каждого приглашённого: *+3 дня Premium* 🎁\n\n"
            f"Твоя ссылка:\n`{ref_link}`\n\n"
            f"👫 Приглашено друзей: *{refs}*\n"
            f"✨ Заработано дней: *{refs * 3}*",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ]))

    elif data == "my_data":
        if user.get("name"):
            prem = f"✨ Premium до {all_users.get(uid,{}).get('premium_until','—')}" if is_premium(uid) else "❌ Нет Premium"
            text = (f"⚙️ *Твои данные:*\n\n"
                    f"👤 Имя: *{user['name']}*\n"
                    f"📅 Дата рождения: *{user['date']}*\n"
                    f"♈ Знак зодиака: *{user['zodiac']}*\n"
                    f"🔢 Число жизни: *{user['life_path']}*\n"
                    f"🔮 Число судьбы: *{user['destiny']}*\n"
                    f"💎 Статус: {prem}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Изменить данные", callback_data="new_data_num")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
        else:
            text = "⚙️ У тебя пока нет сохранённых данных.\n\nСначала сделай нумерологический разбор!"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔮 Нумерологический разбор", callback_data="numerology")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
            ])
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

    # ===== ADMIN =====
    elif data == "admin_test":
        if query.from_user.id != ADMIN_ID: return
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text="🧪 Тестовый пост — бот работает! ✅")
            await query.message.reply_text("✅ Пост отправлен!")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")

    elif data == "admin_refresh":
        await show_admin_panel(query.message)

    elif data == "admin_new_contest":
        if query.from_user.id != ADMIN_ID: return
        user_states[uid] = {"action": "admin_contest", "step": "days"}
        await query.message.reply_text("🎉 Сколько дней Premium для победителя?\nНапример: *30*", parse_mode="Markdown")

    elif data == "admin_give_premium":
        if query.from_user.id != ADMIN_ID: return
        user_states[uid] = {"action": "admin_premium", "step": "uid"}
        users_list = "\n".join([f"ID: `{u_id}` — {u['tg_name']}" for u_id, u in list(all_users.items())[:15]])
        await query.message.reply_text(f"🎁 *Выдать Premium*\n\n{users_list}\n\nНапиши ID:", parse_mode="Markdown")

    elif data == "admin_broadcast":
        if query.from_user.id != ADMIN_ID: return
        user_states[uid] = {"action": "admin_broadcast", "step": "text"}
        await query.message.reply_text(f"📢 Рассылка для *{len(all_users)}* пользователей.\n\nНапиши текст:", parse_mode="Markdown")

    elif data.startswith("contest_win_"):
        if query.from_user.id != ADMIN_ID: return
        parts = data.split("_")
        cid, winner_id, days = parts[2], int(parts[3]), int(parts[4])
        if cid in contests:
            contests[cid]["winner_id"] = winner_id
            contests[cid]["active"] = False
            add_premium(winner_id, days)
            winner_name = all_users.get(winner_id, {}).get("tg_name", "—")
            try:
                await context.bot.send_message(winner_id,
                    f"🎉 *Поздравляем!* Ты выиграл в конкурсе!\n\n🎁 Начислено *{days} дней Premium*! ✨",
                    parse_mode="Markdown")
            except: pass
            await query.message.reply_text(f"✅ Победитель: {winner_name}\n🎁 {days} дней Premium")

# ========== ADMIN PANEL ==========
async def show_admin_panel(message):
    total = len(all_users)
    with_data = len(users_db)
    blocked = sum(1 for u in all_users.values() if u.get("blocked"))
    premium_count = sum(1 for u_id in all_users if is_premium(u_id))
    active_contests = sum(1 for c in contests.values() if c.get("active"))
    text = (
        "*ПАНЕЛЬ АДМИНИСТРАТОРА*\n\n"
        f"👥 Всего пользователей: *{total}*\n"
        f"📝 Заполнили профиль: *{with_data}*\n"
        f"✨ Premium: *{premium_count}*\n"
        f"⛔ Заблокировано: *{blocked}*\n"
        f"🎉 Конкурсов: *{active_contests}*\n\n"
        "*Пользователи:*\n"
    )
    if not all_users:
        text += "_Пока никто не писал_"
    else:
        for u_id, u in list(all_users.items())[:25]:
            status = "⛔" if u.get("blocked") else ("✨" if is_premium(u_id) else "✅")
            name = users_db.get(u_id, {}).get("name", "—")
            text += f"{status} {u['tg_name']} | @{u.get('username','—')} | {name} | ID:{u_id}\n"
        if len(all_users) > 25:
            text += f"\n_...и ещё {len(all_users)-25}_"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎉 Создать конкурс", callback_data="admin_new_contest")],
        [InlineKeyboardButton("🎁 Выдать Premium", callback_data="admin_give_premium")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🧪 Тест поста", callback_data="admin_test")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")]
    ])
    await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Нет доступа.")
        return
    await show_admin_panel(update.message)

async def test_post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text="🧪 Тест — бот работает! ✅")
        await update.message.reply_text("✅ Пост отправлен!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def give_premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /premium ID дни")
        return
    uid_target, days = int(context.args[0]), int(context.args[1])
    add_premium(uid_target, days)
    name = all_users.get(uid_target, {}).get("tg_name", "—")
    try:
        await context.bot.send_message(uid_target,
            f"🎁 *Тебе начислено {days} дней Premium!*\n\nВсе функции бота доступны ✨",
            parse_mode="Markdown")
    except: pass
    await update.message.reply_text(f"✅ {name} — выдано {days} дней")

async def block_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    uid_target = int(context.args[0])
    if uid_target in all_users:
        all_users[uid_target]["blocked"] = True
        save_db()
        await update.message.reply_text(f"⛔ {uid_target} заблокирован")

async def unblock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    uid_target = int(context.args[0])
    if uid_target in all_users:
        all_users[uid_target]["blocked"] = False
        save_db()
        await update.message.reply_text(f"✅ {uid_target} разблокирован")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    text = " ".join(context.args)
    sent = failed = 0
    for u_id in all_users:
        if not all_users[u_id].get("blocked"):
            try:
                await context.bot.send_message(u_id, f"📢 *Сообщение:*\n\n{text}", parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
    await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Ошибок: {failed}")

async def contest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if len(context.args) < 2: return
    days = int(context.args[0])
    title = " ".join(context.args[1:])
    cid = str(len(contests) + 1)
    contests[cid] = {"title": title, "days": days, "active": True, "winner_id": None}
    save_db()
    text = (f"🎉 *КОНКУРС!*\n\n*{title}*\n\n"
            f"🏆 Приз: *{days} дней Premium* бесплатно!\n\n"
            f"Для участия:\n"
            f"1. Подпишись на канал\n"
            f"2. Напиши боту /start\n"
            f"3. Поделись ботом с другом\n\n"
            f"Победитель выбирается случайно! Удачи! 🍀")
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
        await update.message.reply_text("✅ Конкурс опубликован!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    if all_users:
        buttons = [[InlineKeyboardButton(f"🏆 {u['tg_name']}", callback_data=f"contest_win_{cid}_{u_id}_{days}")]
                   for u_id, u in list(all_users.items())[:10] if not u.get("blocked")]
        rand_uid = random.choice(list(all_users.keys()))
        buttons.append([InlineKeyboardButton("🎲 Случайный победитель", callback_data=f"contest_win_{cid}_{rand_uid}_{days}")])
        await update.message.reply_text("Выбери победителя:", reply_markup=InlineKeyboardMarkup(buttons))

# ========== СООБЩЕНИЯ ==========
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(uid, {})
    user = get_user(uid)
    if is_blocked(uid): return
    if not state:
        await update.message.reply_text(
            "Выбери действие из меню 👇",
            reply_markup=main_menu(uid))
        return
    action = state.get("action")
    step = state.get("step")

    # ===== НУМЕРОЛОГИЯ =====
    if action == "numerology":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(
                f"Привет, *{text}*! 👋\n\nТеперь напиши дату рождения в формате *ДД.ММ.ГГГГ*\n\nНапример: 15.03.1990",
                parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*\nНапример: *15.03.1990*", parse_mode="Markdown")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"],
                            "life_path": nums["life_path"], "destiny": nums["destiny"]})
            user_states.pop(uid, None)
            await update.message.reply_text("🔮 Считаю твой разбор... ✨")
            reading = get_ai_reading(nums)
            await update.message.reply_text(
                f"*Нумерологический разбор для {name}*\n\n{reading}\n\n"
                f"📊 Число жизни: *{nums['life_path']}* | Судьбы: *{nums['destiny']}* | *{nums['zodiac']}*",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== ГОРОСКОП =====
    elif action == "horoscope":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, напиши дату рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*", parse_mode="Markdown")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"],
                            "life_path": nums["life_path"], "destiny": nums["destiny"]})
            user_states.pop(uid, None)
            await update.message.reply_text(f"⭐ Гороскоп для *{nums['zodiac']}*... ✨", parse_mode="Markdown")
            horoscope = get_daily_horoscope(nums["zodiac"])
            await update.message.reply_text(
                f"*Гороскоп для {name} ({nums['zodiac']})*\n\n{horoscope}",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== СОН =====
    elif action == "dream":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "dream"
            await update.message.reply_text(f"😴 *{text}*, опиши свой сон подробно:", parse_mode="Markdown")
        elif step == "dream":
            name = state.get("name") or user.get("name", "Друг")
            user_states.pop(uid, None)
            await update.message.reply_text("🌙 Толкую сон... ✨")
            result = get_dream(name, text)
            await update.message.reply_text(
                f"*Толкование сна для {name}*\n\n{result}",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== СОВМЕСТИМОСТЬ =====
    elif action == "compatibility":
        if step == "name1":
            user_states[uid]["name1"] = text
            user_states[uid]["step"] = "date1"
            await update.message.reply_text(f"*{text}* 👋\n\nТвоя дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date1":
            if not calculate_numerology(text, "test"):
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*", parse_mode="Markdown")
                return
            user_states[uid]["date1"] = text
            user_states[uid]["step"] = "name2"
            await update.message.reply_text("Напиши *имя партнёра*:", parse_mode="Markdown")
        elif step == "name2":
            user_states[uid]["name2"] = text
            user_states[uid]["step"] = "date2"
            await update.message.reply_text(f"Дата рождения *{text}* (*ДД.ММ.ГГГГ*):", parse_mode="Markdown")
        elif step == "date2":
            if not calculate_numerology(text, "test"):
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*", parse_mode="Markdown")
                return
            name1, date1, name2 = state["name1"], state["date1"], state["name2"]
            user_states.pop(uid, None)
            # Сохраняем данные пользователя если ещё нет
            if not user.get("name"):
                nums = calculate_numerology(date1, name1)
                if nums:
                    save_user(uid, {"name": name1, "date": date1, "zodiac": nums["zodiac"],
                                    "life_path": nums["life_path"], "destiny": nums["destiny"]})
            await update.message.reply_text(f"💑 Считаю совместимость *{name1}* и *{name2}*... ✨", parse_mode="Markdown")
            result = get_compatibility(name1, date1, name2, text)
            if result:
                await update.message.reply_text(
                    f"*Совместимость {name1} и {name2}*\n\n{result}",
                    parse_mode="Markdown", reply_markup=back_menu())
            else:
                await update.message.reply_text("❌ Ошибка в данных. Проверь даты.", reply_markup=back_menu())
        # Если уже есть данные пользователя — только спрашиваем о партнёре
        elif step == "name2":
            user_states[uid]["name2"] = text
            user_states[uid]["step"] = "date2"
            await update.message.reply_text(f"Дата рождения *{text}* (*ДД.ММ.ГГГГ*):", parse_mode="Markdown")

    # ===== ГОД =====
    elif action == "yearly":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*", parse_mode="Markdown")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"],
                            "life_path": nums["life_path"], "destiny": nums["destiny"]})
            user_states.pop(uid, None)
            await update.message.reply_text(f"🌟 Составляю прогноз на год для *{name}*... ✨\n\n_Это займёт немного дольше..._", parse_mode="Markdown")
            result = get_yearly_forecast(nums)
            await update.message.reply_text(
                f"*Прогноз на год для {name}*\n\n{result}",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== ИМЯ =====
    elif action == "name_num":
        if step == "name":
            user_states.pop(uid, None)
            await update.message.reply_text(f"✍️ Анализирую имя *{text}*... ✨", parse_mode="Markdown")
            result = get_name_numerology(text)
            await update.message.reply_text(
                f"*Нумерология имени {text}*\n\n{result}",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== УДАЧА =====
    elif action == "lucky":
        if step == "name":
            user_states[uid]["name"] = text
            user_states[uid]["step"] = "date"
            await update.message.reply_text(f"*{text}*, дата рождения *ДД.ММ.ГГГГ*:", parse_mode="Markdown")
        elif step == "date":
            name = state.get("name")
            nums = calculate_numerology(text, name)
            if not nums:
                await update.message.reply_text("❌ Неверный формат. Напиши *ДД.ММ.ГГГГ*", parse_mode="Markdown")
                return
            save_user(uid, {"name": name, "date": text, "zodiac": nums["zodiac"],
                            "life_path": nums["life_path"], "destiny": nums["destiny"]})
            user_states.pop(uid, None)
            lnum = lucky_number(uid)
            result = get_lucky_day_forecast(name, nums["zodiac"], nums["life_path"], uid)
            await update.message.reply_text(
                f"🍀 *Число удачи сегодня: {lnum}*\n\n{result}",
                parse_mode="Markdown", reply_markup=back_menu())

    # ===== ОРАКУЛ =====
    elif action == "oracle":
        if step == "question":
            name = state.get("name") or user.get("name", "Друг")
            user_states.pop(uid, None)
            await update.message.reply_text("🔮 Оракул размышляет... ✨")
            result = get_oracle_answer(name, text)
            await update.message.reply_text(
                f"🔮 *Ответ Оракула*\n\n{result}",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔮 Задать ещё вопрос", callback_data="oracle")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]
                ]))

    # ===== ADMIN =====
    elif action == "admin_contest":
        if uid != ADMIN_ID: return
        if step == "days":
            try:
                days = int(text)
                user_states[uid]["days"] = days
                user_states[uid]["step"] = "title"
                await update.message.reply_text(f"✅ Приз: {days} дней\n\nНапиши *название конкурса*:", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Напиши число, например: 30")
        elif step == "title":
            days = user_states[uid]["days"]
            cid = str(len(contests) + 1)
            contests[cid] = {"title": text, "days": days, "active": True, "winner_id": None}
            save_db()
            contest_text = (f"🎉 *КОНКУРС!*\n\n*{text}*\n\n🏆 Приз: *{days} дней Premium*!\n\n"
                           f"Для участия:\n1. Подпишись на канал\n2. Напиши /start боту\n3. Поделись с другом\n\nУдачи! 🍀")
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=contest_text, parse_mode="Markdown")
                await update.message.reply_text("✅ Конкурс опубликован!")
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {e}")
            user_states.pop(uid, None)

    elif action == "admin_premium":
        if uid != ADMIN_ID: return
        if step == "uid":
            try:
                user_states[uid]["target_uid"] = int(text)
                user_states[uid]["step"] = "days"
                name = all_users.get(int(text), {}).get("tg_name", "—")
                await update.message.reply_text(f"👤 *{name}*\n\nСколько дней Premium?", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ Введи числовой ID")
        elif step == "days":
            try:
                days = int(text)
                target = user_states[uid]["target_uid"]
                add_premium(target, days)
                name = all_users.get(target, {}).get("tg_name", "—")
                try:
                    await context.bot.send_message(target, f"🎁 *Тебе начислено {days} дней Premium!* ✨", parse_mode="Markdown")
                except: pass
                await update.message.reply_text(f"✅ {name} — выдано {days} дней")
                user_states.pop(uid, None)
            except:
                await update.message.reply_text("❌ Напиши число дней")

    elif action == "admin_broadcast":
        if uid != ADMIN_ID: return
        sent = failed = 0
        for u_id in all_users:
            if not all_users[u_id].get("blocked"):
                try:
                    await context.bot.send_message(u_id, f"📢 *Сообщение:*\n\n{text}", parse_mode="Markdown")
                    sent += 1
                except:
                    failed += 1
        await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Ошибок: {failed}")
        user_states.pop(uid, None)

def main():
    load_db()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    jq = app.job_queue
    # Расписание UTC (МСК = UTC+3)
    jq.run_daily(post_morning_horoscope, time=time(5, 0))    # 8:00 МСК
    jq.run_daily(post_affirmation, time=time(9, 0))          # 12:00 МСК
    jq.run_daily(post_moon, time=time(12, 0))                # 15:00 МСК
    jq.run_daily(post_evening_wish, time=time(16, 0))        # 19:00 МСК
    jq.run_daily(post_sleep_advice, time=time(18, 0))        # 21:00 МСК
    jq.run_daily(post_weekly_tarot, time=time(15, 0), days=(4,))    # Пятница 18:00 МСК
    jq.run_daily(post_weekly_numerology, time=time(7, 0), days=(6,)) # Воскресенье 10:00 МСК
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("test_post", test_post_cmd))
    app.add_handler(CommandHandler("premium", give_premium_cmd))
    app.add_handler(CommandHandler("block", block_cmd))
    app.add_handler(CommandHandler("unblock", unblock_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("contest", contest_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
