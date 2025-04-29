#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IslamQuiz - телеграм-бот ислам туралы білімді тексеруге арналған.
Бот күнделікті сұрақтар жібереді, жауаптарды қабылдайды және ұпайларды есептейді.
"""

import json
import logging
import random
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import pytz
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Poll,
    ChatMemberUpdated,
    ChatMember,
    Message,
    User,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    JobQueue,
    MessageHandler,
    filters,
)

# Логгер баптау
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константалар
TOKEN = "7956214041:AAG8U68UhPLWUAKoNiB7t11GFWJ0OrioEFc"  # Ботыңыздың токенін осында орнатыңыз
# Астана уақыт белдеуі
TIMEZONE = pytz.timezone("Asia/Almaty")

# Глобальдық айнымалылар
active_polls = {}
user_scores = {}
daily_participants = set()

# Тақырыптар тізімі
TOPICS = {
    "aqida": "Ақида",
    "fiqh": "Фиқһ",
    "sira": "Сира",
    "quran": "Құран",
    "hadis": "Хадис",
    "adab": "Әдеп",
    # Жаңа ілім категориялары
    "ilim_aqida": "Ақида - Исламның негізгі сенім жүйесі",
    "ilim_fiqh": "Фиқһ - Ислам құқығы",
    "ilim_akhlaq": "Ахлақ - Исламдағы мінез-құлық нормалары",
    "ilim_sira": "Сира - Пайғамбарымыздың (ﷺ) өмірбаяны",
    "ilim_quran": "Құран және тәпсір - Құран Кәрім және оның түсіндірмесі"
}

# Батырмалар
def get_main_keyboard():
    """Негізгі батырмалар тақтасын жасау"""
    keyboard = [
        [KeyboardButton("Викторина")],
        [KeyboardButton("Менің нәтижем"), KeyboardButton("Жетістіктер")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_topic_keyboard():
    keyboard = []
    for topic_id, topic_name in TOPICS.items():
        keyboard.append([InlineKeyboardButton(topic_name, callback_data=f"topic_{topic_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Артқа", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

# Сұрақтар базасын жүктеу
def load_questions() -> List[Dict]:
    """Сұрақтар базасын JSON файлынан жүктеу"""
    try:
        with open("questions.json", "r", encoding="utf-8") as file:
            questions = json.load(file)
        return questions
    except FileNotFoundError:
        logging.error("questions.json файлы табылмады")
        return []

# Ұпайлар базасын жүктеу және сақтау
def load_scores() -> Dict:
    """Ұпайлар базасын JSON файлынан жүктеу"""
    try:
        with open("scores.json", "r", encoding="utf-8") as file:
            scores = json.load(file)
        return scores
    except FileNotFoundError:
        return {}

def save_scores(scores: Dict) -> None:
    """Ұпайлар базасын JSON файлына сақтау"""
    with open("scores.json", "w", encoding="utf-8") as file:
        json.dump(scores, file, ensure_ascii=False, indent=4)

# Телеграм каналдарының тізімі (міндетті тіркелу үшін)
REQUIRED_CHANNELS = [
    {"username": "kuanyshbekzhigit", "name": "Қуаныш Бекжігіт"},
    {"username": "davidsuragan", "name": "Дәуіт Сұраған"}
]

# Арналарға тіркелуді қатаң тексеру функциясы
async def check_user_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Пайдаланушының міндетті каналдарға тіркелгенін қатаң тексеру"""
    
    # Тексеру журналын жазу
    logging.info("Пайдаланушы арналарға тіркелуін тексеру")
    
    # Пайдаланушы идентификаторын алу
    user_id = update.effective_user.id
    
    # Тіркелмеген арналар тізімі
    not_subscribed = []
    
    # Тіркелу мәртебесі (әдепкі: False)
    subscribed_to_all = True
    
    for channel in REQUIRED_CHANNELS:
        try:
            # Арна идентификаторы
            chat_username = channel['username']
            
            # Арнаны алу
            try:
                chat = await context.bot.get_chat(f"@{chat_username}")
                chat_id = chat.id
                
                # Пайдаланушы мүшелігін тексеру
                try:
                    # getChat_member API әдісін шақыру
                    member = await context.bot.get_chat_member(chat_id, user_id)
                    
                    # Пайдаланушы мәртебесін тексеру
                    # 'creator', 'administrator', 'member' - тіркелген
                    # 'left', 'kicked', 'restricted' - тіркелмеген
                    status = member.status
                    
                    logging.info(f"Арна: {chat_username}, Пайдаланушы: {user_id}, Мәртебе: {status}")
                    
                    # Тіркелмеген мәртебелерді тексеру
                    if status not in ['creator', 'administrator', 'member']:
                        not_subscribed.append(channel)
                        subscribed_to_all = False
                        logging.warning(f"Пайдаланушы {user_id} арнаға тіркелмеген: {chat_username}")
                
                except Exception as e:
                    # Пайдаланушы мүшелігін тексеру қатесі
                    logging.error(f"Пайдаланушы мүшелігін тексеру қатесі: {e}")
                    not_subscribed.append(channel)
                    subscribed_to_all = False
                    
            except Exception as e:
                # Арнаны алу қатесі
                logging.error(f"Арнаны алу қатесі: {e}")
                not_subscribed.append(channel)
                subscribed_to_all = False
        
        except Exception as e:
            # Жалпы қате
            logging.error(f"Арна тексеру кезінде жалпы қате: {e}")
            not_subscribed.append(channel)
            subscribed_to_all = False
    
    # Егер барлық арналарға тіркелген болса
    if subscribed_to_all:
        logging.info(f"Пайдаланушы {user_id} барлық қажетті арналарға тіркелген")
        return True
    
    # Барлық тіркелмеген арналар тізімін көрсету
    channel_links = []
    for channel in not_subscribed:
        # HTML форматында сілтеме жасау
        link = f"<a href='https://t.me/{channel['username']}'>{channel['name']}</a>"
        channel_links.append(link)
    
    # Хабарлама мәтіні
    channels_text = "\n".join(channel_links)
    message_text = (
        "📢 <b>Назар аударыңыз!</b>\n\n"
        "Бұл ботты пайдалану үшін <b>міндетті түрде</b> келесі арналарға тіркелу қажет:\n\n"
        f"{channels_text}\n\n"
        "Тіркелгеннен кейін «<b>✅ Тексеру</b>» батырмасын басыңыз."
    )
    
    # Тіркелу батырмаларын жасау
    keyboard = []
    
    # Әр арна үшін тіркелу батырмасы
    for channel in not_subscribed:
        button = [InlineKeyboardButton(
            f"📢 {channel['name']} арнасына тіркелу", 
            url=f"https://t.me/{channel['username']}"
        )]
        keyboard.append(button)
    
    # Тексеру батырмасы
    keyboard.append([InlineKeyboardButton("Тексеру", callback_data="check_subscription")])
    
    # Батырмалар тақтасын жасау
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Хабарлама жіберу (callback немесе хабарлама түріне байланысты)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.edit_text(
                message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"Callback хабарламасын жаңарту қатесі: {e}")
            # Бұрынғы хабарламаны жою және жаңа хабарлама жіберу
            try:
                await update.callback_query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
    else:
        try:
            await update.message.reply_text(
                message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"Хабарлама жіберу қатесі: {e}")
            # Тікелей чатқа хабарлама жіберу
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
    
    return False

# Бот командалары
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бот бастау командасы"""
    try:
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Пайдаланушы /start командасын жіберді: {update.effective_user.id}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей /start командасын жіберді")
            return
        
        # Қарсы алу хабарламасы
        welcome_text = (
            "Ассаламу алейкум! 🌙\n\n"
            "*IslamQuiz* ботына қош келдіңіз!\n\n"
            "Бұл бот арқылы ислам дінінің әр түрлі салалары бойынша білімінізді тексере аласыз.\n\n"
            "Төмендегі батырмаларды пайдаланып ботпен жұмыс істей аласыз:"
        )
        
        # Хабарлама жіберу
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logging.error(f"/start командасын өңдеу кезінде қате: {e}")
        await update.message.reply_text(f"Қате туындады: {str(e)}")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Арнайы сұрақ сұрату командасы"""
    try:
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Пайдаланушы /quiz командасын жіберді: {update.effective_user.id}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей /quiz командасын жіберді")
            return
        
        questions = load_questions()
        question_data = random.choice(questions)
        
        await send_quiz(context, update.effective_chat.id, question_data)
        
        await update.message.reply_text(
            "Сізге арнайы сұрақ дайын! Алла ісіңізге береке берсін! 🎯",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"/quiz командасын өңдеу кезінде қате: {e}")
        await update.message.reply_text(f"Қате туындады: {str(e)}")

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нәтижені көрсету командасы"""
    try:
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Пайдаланушы /score командасын жіберді: {update.effective_user.id}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей /score командасын жіберді")
            return
        
        scores = load_scores()
        user_id = str(update.effective_user.id)
        
        if user_id in scores:
            if isinstance(scores[user_id], dict):
                score_value = scores[user_id]["total"]
            else:
                score_value = scores[user_id]
            message = f"*Сіздің нәтижеңіз:*\n\nДұрыс жауаптар: {score_value}"
        else:
            message = "Сіз әлі викторинаға қатыспадыңыз"
            
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"/score командасын өңдеу кезінде қате: {e}")
        await update.message.reply_text(f"Қате туындады: {str(e)}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Жетістіктер тізімін көрсету командасы"""
    try:
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Пайдаланушы /leaderboard командасын жіберді: {update.effective_user.id}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей /leaderboard командасын жіберді")
            return
        
        scores = load_scores()
        
        if not scores:
            await update.message.reply_text("Әзірше ешкім викторинаға қатыспаған")
            return
        
        # Жаңа формат пен ескі форматты өңдеу
        processed_scores = {}
        for user_id, score in scores.items():
            if isinstance(score, dict):
                processed_scores[user_id] = score["total"]
            else:
                processed_scores[user_id] = score
        
        sorted_scores = sorted(processed_scores.items(), key=lambda x: x[1], reverse=True)
        
        message = "*🏆 Үздік нәтижелер:*\n\n"
        for i, (user_id, score) in enumerate(sorted_scores[:10], 1):
            try:
                user = await context.bot.get_chat(int(user_id))
                name = user.first_name
            except:
                name = "Белгісіз қатысушы"
            message += f"{i}. {name}: {score} ұпай\n"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"/leaderboard командасын өңдеу кезінде қате: {e}")
        await update.message.reply_text(f"Қате туындады: {str(e)}")

# Сұрақтар жіберу логикасы
async def send_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int, question_data: Dict) -> None:
    """Викторина жіберу"""
    try:
        # Сұрақ деректерін көшіруін жасаймыз, түпнұсқасын өзгертпеу үшін
        data = question_data.copy()
        
        # correct_option_id кілті жоқ болса, correct_answer индексін пайдаланамыз
        if "correct_option_id" not in data:
            # 1-тәсіл: options тізіміндегі correct_answer индексін пайдалану
            if "correct_answer" in data and "options" in data:
                correct_option = data.get("correct_answer")
                if isinstance(correct_option, str) and correct_option in data["options"]:
                    data["correct_option_id"] = data["options"].index(correct_option)
                elif isinstance(correct_option, int) and 0 <= correct_option < len(data["options"]):
                    data["correct_option_id"] = correct_option
                else:
                    data["correct_option_id"] = 0
            # 2-тәсіл: егер жоғарыдағы тәсіл қолданылмаса, әдепкі 0 мәнін тағайындаймыз
            else:
                data["correct_option_id"] = 0

        # Қажетті деректерді алу
        question_text = data["question"]
        options = data["options"]
        correct_option_id = int(data["correct_option_id"])
        explanation = data.get("explanation", "Түсіндірме жоқ")
        
        # Мотивация хабарламасы (егер болса)
        motivation = data.get("motivation", "Білім - ең үлкен байлық!")
        
        # Тақырып идентификаторы (егер болса)
        topic_id = data.get("topic", "")
        
        # Жауап уақыты (30 секунд)
        open_period = 30
        
        # Викторина жіберу
        message = await context.bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_option_id,
            open_period=open_period,
            explanation=explanation,
            is_anonymous=False
        )
        
        # Сауалнама идентификаторы мен чат идентификаторын сақтау
        poll_id = message.poll.id
        
        # Чатқа байланысты викторина деректерін сақтау
        context.bot_data.setdefault("quiz_data", {})[poll_id] = {
            "chat_id": chat_id,
            "message_id": message.message_id,
            "correct_option_id": correct_option_id,
            "options": options,
            "question": question_text,
            "explanation": explanation,
            "motivation": motivation,
            "topic_id": topic_id
        }
        
        # Викторина аяқталғаннан кейін түсіндірмені жіберу
        job_name = f"poll_{poll_id}"
        context.job_queue.run_once(
            send_explanation,
            when=open_period + 2,
            data=poll_id,
            name=job_name
        )
    except Exception as e:
        logging.error(f"Викторина жіберу кезінде қате: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Викторина жіберу кезінде қате туындады: {str(e)}"
        )

async def send_explanation(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Дұрыс жауап пен түсіндірмені жіберу"""
    try:
        job = context.job
        poll_id = job.data
        
        # quiz_data деректеріне қол жеткізу
        quiz_data = context.bot_data.get("quiz_data", {}).get(poll_id)
        
        if not quiz_data:
            logging.error(f"Poll ID {poll_id} үшін quiz_data табылмады")
            return
        
        chat_id = quiz_data["chat_id"]
        correct_option_id = quiz_data["correct_option_id"]
        options = quiz_data["options"]
        explanation = quiz_data.get("explanation", "Түсіндірме жоқ")
        motivation = quiz_data.get("motivation", "Білім - ең үлкен байлық!")
        
        # Дұрыс жауап
        correct_option = options[correct_option_id]
        
        # Хабарлама құру
        text = (
            f"*Дұрыс жауап:* {correct_option}\n\n"
            f"*Түсіндірме:*\n{explanation}\n\n"
            f"{motivation}"
        )
        
        # Жауапты жіберу
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Келесі сұрақ батырмасы (егер topic_id сақталған болса)
        if "topic_id" in quiz_data:
            topic_id = quiz_data["topic_id"]
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Келесі сұрақ", callback_data=f"next_topic_{topic_id}")
            ]])
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="Келесі сұраққа көшуге дайынсыз ба?",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Түсіндірме жіберу кезінде қате: {e}")

# Жаңа мүшелерді қарсы алу
async def greet_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Чатқа жаңадан қосылған мүшелерді қарсы алу"""
    result = extract_status_change(update.chat_member)
    if result is None:
        return
    
    was_member, is_member = result
    
    if not was_member and is_member:
        # Жаңа мүше чатқа қосылды
        new_member = update.chat_member.new_chat_member.user
        await update.effective_chat.send_message(
            f"Ассаламу алейкум, {new_member.first_name}! 🌙\n\n"
            f"*IslamQuiz* чатына қош келдіңіз!\n"
            f"Бүгінгі сұраққа жауап беруге дайынсыз ба?",
            parse_mode=ParseMode.MARKDOWN
        )

def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
    """Мүшенің статусының өзгеруін анықтау көмекші функциясы"""
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))
    
    if status_change is None:
        return None
    
    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)
    
    return was_member, is_member

# Апта сайынғы рейтинг жариялау
async def weekly_results(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Апта сайынғы нәтижелерді жариялау"""
    # Барлық чаттарға жібереміз (чаттар тізімін жүйеде сақтау керек)
    # Бұл жерде мысал үшін тек бір чатқа жіберілуде
    chat_ids = context.bot_data.get("active_chats", [])
    
    if not chat_ids:
        return
    
    scores = load_scores()
    
    # Апталық ұпайлар бойынша сұрыптау
    leaderboard_data = sorted(
        [(user_id, data["weekly"]) for user_id, data in scores.items()],
        key=lambda x: x[1],
        reverse=True
    )[:5]  # Тек 5 үздік
    
    if not leaderboard_data:
        for chat_id in chat_ids:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Бұл аптада ешкім ұпай жинаған жоқ 😔",
                parse_mode=ParseMode.MARKDOWN
            )
        return
    
    text = (
        "*Апталық нәтижелер!* 🏆\n\n"
        "Ең көп дұрыс жауап берген қатысушылар:\n\n"
    )
    
    for i, (user_id, points) in enumerate(leaderboard_data, start=1):
        user_info = await context.bot.get_chat(int(user_id))
        username = user_info.first_name
        
        if i == 1:
            text += f"🥇 {username}: {points} ұпай\n"
        elif i == 2:
            text += f"🥈 {username}: {points} ұпай\n"
        elif i == 3:
            text += f"🥉 {username}: {points} ұпай\n"
        else:
            text += f"{i}. {username}: {points} ұпай\n"
    
    text += "\nБарлық қатысушыларға рахмет! Жаңа аптада жаңа білім мен жаңа сұрақтар күтіңіздер! 📚"
    
    # Апталық нәтижелерді барлық чатқа жіберу
    for chat_id in chat_ids:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Апталық ұпайларды нөлдеу
    for user_id in scores:
        scores[user_id]["weekly"] = 0
    
    save_scores(scores)

# Күнделікті сұрақ жіберу
async def daily_quiz(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Күнделікті сұрақ жіберу"""
    chat_ids = context.bot_data.get("active_chats", [])
    
    if not chat_ids:
        return
    
    questions = load_questions()
    question_data = random.choice(questions)
    
    intro_text = (
        "*Бүгінгі IslamQuiz сұрағы!* 🌙\n\n"
        "Құрметті қатысушылар, жаңа сұраққа дайын болыңыздар!\n"
        "Дұрыс жауап берсеңіз, ұпай аласыз. Жауап беру уақыты: 24 сағат."
    )
    
    for chat_id in chat_ids:
        await context.bot.send_message(
            chat_id=chat_id,
            text=intro_text,
            parse_mode=ParseMode.MARKDOWN
        )
        await send_quiz(context, chat_id, question_data)

# Күнделікті ескерту жіберу
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Күнделікті ескерту жіберу"""
    chat_ids = context.bot_data.get("active_chats", [])
    
    if not chat_ids:
        return
    
    reminder_text = (
        "🌙 *IslamQuiz ескертуі*\n\n"
        "Құрметті қатысушылар, бүгінгі сұраққа жауап беруді ұмытпаңыз!\n"
        "Білім - ең үлкен байлық! 📚"
    )
    
    for chat_id in chat_ids:
        await context.bot.send_message(
            chat_id=chat_id,
            text=reminder_text,
            parse_mode=ParseMode.MARKDOWN
        )

# Чатты тіркеу
async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Чатты белсенді чаттар тізіміне қосу"""
    chat_id = update.effective_chat.id
    active_chats = context.bot_data.setdefault("active_chats", [])
    
    if chat_id not in active_chats:
        active_chats.append(chat_id)
        await update.message.reply_text(
            "Чат сәтті тіркелді! Енді күнделікті сұрақтар осы чатқа жіберіледі.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "Бұл чат бұрыннан тіркелген!",
            parse_mode=ParseMode.MARKDOWN
        )

async def group_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Топта викторина бастау"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("😕 Бұл команда тек топтарда жұмыс істейді!")
        return

    try:
        # Сұрақтарды жүктеу
        questions = load_questions()
        if not questions:
            await update.message.reply_text("❌ Сұрақтар жүктелмеді!")
            return

        # Кездейсоқ сұрақ таңдау
        question_data = random.choice(questions)
        
        # Сұрақты форматтау
        question_text = f"📚 Сұрақ:\n\n{question_data['question']}\n\n"
        options = question_data['options']
        
        # Сауалнама жіберу
        poll = await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question_text,
            options=options,
            is_anonymous=False,
            type='quiz',
            correct_option_id=question_data['correct_option'],
            explanation=question_data['explanation'],
            open_period=60  # 60 секунд
        )
        
        # Сауалнама ID-сын сақтау
        poll_id = poll.poll.id
        context.bot_data[poll_id] = {
            'question': question_data,
            'chat_id': update.effective_chat.id
        }
        
        # Бастау хабарламасы
        await update.message.reply_text(
            "🎯 Викторина басталды!\n\n"
            "📝 Сұраққа жауап беру үшін 60 секунд уақытыңыз бар.\n"
            "✅ Дұрыс жауап +1 ұпай\n"
            "❌ Қате жауап 0 ұпай\n\n"
            "Қатысушылардың нәтижелері автоматты түрде есептеледі!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Қате пайда болды: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Бот командаларын көрсету"""
    help_text = (
        "*IslamQuiz ботының командалары:*\n\n"
        "👤 *Жеке командалар:*\n"
        "/start - ботты бастау\n"
        "/quiz - жаңа сұрақ алу\n"
        "/score - өз ұпайыңызды көру\n"
        "/leaderboard - көшбасшылар тізімін көру\n\n"
        "👥 *Топ командалары:*\n"
        "/creategroup - жаңа жарыс тобын ашу\n"
        "/groupquiz - топта жарыс бастау\n"
        "/register - топты тіркеу (күнделікті сұрақтар үшін)\n\n"
        "ℹ️ *Қосымша ақпарат:*\n"
        "• Жауап беру уақыты: 30 секунд\n"
        "• Дұрыс жауап: +1 ұпай\n"
        "• Апталық нәтижелер: жексенбі күні\n"
        "• Күнделікті сұрақ: таңғы 9:00\n"
        "• Ескерту: кешкі 18:00\n\n"
        "📚 *Білім - ең үлкен байлық!*"
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Жауаптарды өңдеу функциясы
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сауалнамаға берілген жауаптарды өңдеу"""
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user_id = str(poll_answer.user.id)
    
    poll_data = context.bot_data.get("quiz_data", {}).get(poll_id)
    if not poll_data:
        return
    
    selected_option = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    correct_option = poll_data["correct_option_id"]
    
    # Ұпайларды жаңарту
    scores = load_scores()
    if isinstance(scores.get(user_id), int):
        # Ескі формат
        scores[user_id] = {"total": scores[user_id], "weekly": 0}
    elif user_id not in scores:
        scores[user_id] = {"total": 0, "weekly": 0}
    
    # Дұрыс жауап бергені үшін ұпай беру
    if selected_option == correct_option:
        scores[user_id]["total"] += 1
        scores[user_id]["weekly"] += 1
        save_scores(scores)
        
        # Пайдаланушыға хабарлама жіберу
        try:
            chat_id = poll_data.get("chat_id")
            if chat_id:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎉 Дұрыс жауап! Жарайсың!\n{poll_data.get('motivation', 'Білім - ең үлкен байлық!')}"
                )
        except Exception as e:
            logging.error(f"Жауап хабарламасын жіберу кезінде қате: {e}")

# Тақырып таңдауды өңдеу
async def handle_topic_selection(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тақырып бойынша сұрақтар көрсету"""
    topic_id = query.data.split("_")[1]
    questions = load_questions()
    
    # Тақырып бойынша сұрақтарды сүзгілеу
    topic_questions = [q for q in questions if q.get("topic") == topic_id]
    
    if not topic_questions:
        await query.message.edit_text(
            f"Бұл тақырып бойынша әзірше сұрақтар жоқ.",
            reply_markup=get_topic_keyboard()
        )
        return
    
    # Кездейсоқ сұрақ таңдау
    question_data = random.choice(topic_questions)
    
    # correct_option_id кілті жоқ болса, бұны да тексереміз
    if "correct_option_id" not in question_data:
        correct_option = question_data.get("correct_answer", 0)
        if isinstance(correct_option, str) and correct_option in question_data.get("options", []):
            question_data["correct_option_id"] = question_data["options"].index(correct_option)
        else:
            question_data["correct_option_id"] = 0
    
    # Сұрақ жіберу
    await send_quiz(context, query.message.chat_id, question_data)
    
    # Келесі сұрақ түймесін қосу
    await query.message.reply_text(
        f"Тақырып бойынша сұрақ дайын! Жақсы бағың келсін! 🎯",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Келесі сұрақ", callback_data=f"next_topic_{topic_id}")
        ]])
    )

# Хабарламаларды өңдеу
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Хабарламаларды өңдеу"""
    try:
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Пайдаланушыдан хабарлама: {update.effective_user.id}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей хабарлама жіберуге тырысты")
            return
        
        # Хабарлама мәтінін алу
        text = update.message.text
        
        # Хабарламаны өңдеу
        if text == "Викторина":
            await quiz(update, context)
        elif text == "Менің нәтижем":
            await score(update, context)
        elif text == "Жетістіктер":
            await leaderboard(update, context)
        else:
            await update.message.reply_text(
                "Өкінішке орай, мен сіздің хабарламаңызды түсінбеймін. Төмендегі кнопкаларды пайдаланыңыз:",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logging.error(f"Хабарламаны өңдеу кезінде қате: {e}")
        try:
            await update.message.reply_text(f"Қате туындады: {str(e)}")
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Қате туындады: {str(e)}"
            )

# Кнопкаларды өңдеу
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопкаларды өңдеу"""
    try:
        query = update.callback_query
        await query.answer()
        
        # "Тексеру" батырмасын өңдеу
        if query.data == "check_subscription":
            logging.info("Тексеру батырмасы басылды")
            if await check_user_subscription(update, context):
                try:
                    await query.message.edit_text(
                        "🎉 <b>Керемет, сіз барлық қажетті арналарға тіркелдіңіз!</b>\n\n"
                        "Енді ботты толықтай қолдана аласыз. Төмендегі батырмаларды пайдаланыңыз:",
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_main_keyboard()
                    )
                except Exception as e:
                    logging.error(f"Тексеру сәтті аяқталған соң хабарламаны жаңарту қатесі: {e}")
                    try:
                        await query.message.delete()
                    except:
                        pass
                    
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="🎉 <b>Керемет, сіз барлық қажетті арналарға тіркелдіңіз!</b>\n\n"
                             "Енді ботты толықтай қолдана аласыз. Төмендегі батырмаларды пайдаланыңыз:",
                        parse_mode=ParseMode.HTML,
                        reply_markup=get_main_keyboard()
                    )
            return
        
        # ⚠️ БҰДАН КЕЙІНГІ КЕЗ-КЕЛГЕН ӘРЕКЕТ ҮШІН АРНАЛАРҒА ТІРКЕЛУДІ ҚАТАҢ ТЕКСЕРУ
        logging.info(f"Батырма басылды: {query.data}")
        if not await check_user_subscription(update, context):
            logging.warning(f"Пайдаланушы {update.effective_user.id} арналарға тіркелмей батырманы басуға тырысты: {query.data}")
            return
        
        # Негізгі батырмаларды өңдеу
        try:
            if query.data == "quiz":
                # Викторина жіберу
                await send_random_quiz(update, context)
            elif query.data == "score":
                # Нәтижелерді көрсету
                await show_user_score(update, context)
            elif query.data == "leaderboard":
                # Жетістіктер тізімін көрсету
                await show_leaderboard_list(update, context)
            elif query.data == "back_to_main":
                await query.message.edit_text(
                    "Не істегіңіз келеді?",
                    reply_markup=get_main_keyboard()
                )
            elif query.data.startswith("topic_"):
                await handle_topic_selection(query, context)
            elif query.data.startswith("next_topic_"):
                # Келесі тақырып бойынша сұрақ
                topic_id = query.data.split("_")[2]
                logging.info(f"Келесі тақырып сұрағы сұралды: {topic_id}")
                
                # Пайдаланушының ботпен қарым-қатынас жасай алатындығын тексеру
                try:
                    await send_topic_quiz(update, context, topic_id)
                except Exception as e:
                    logging.error(f"Келесі тақырып сұрағын жіберуде қате: {e}")
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Сұрақ жіберу кезінде қате туындады: {str(e)}"
                    )
            else:
                logging.warning(f"Белгісіз батырма: {query.data}")
        except Exception as e:
            logging.error(f"Батырманы өңдеу кезінде қате: {e}")
            try:
                await query.message.reply_text(f"Қате туындады: {str(e)}")
            except:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Қате туындады: {str(e)}"
                )
    except Exception as e:
        logging.error(f"Жалпы батырма өңдеу қатесі: {e}")

# Викторина жіберу функциясы
async def send_random_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кездейсоқ викторина жіберу"""
    try:
        # Викторина үшін callback қолдану
        questions = load_questions()
        question_data = random.choice(questions)
        
        # correct_option_id кілтін тексеру және қажет болса қосу
        if "correct_option_id" not in question_data:
            correct_option = question_data.get("correct_answer", 0)
            if isinstance(correct_option, str) and correct_option in question_data.get("options", []):
                question_data["correct_option_id"] = question_data["options"].index(correct_option)
            else:
                question_data["correct_option_id"] = 0
        
        # Сұрақ жіберу
        if update.callback_query:
            await send_quiz(context, update.callback_query.message.chat_id, question_data)
            await update.callback_query.message.reply_text(
                "Сізге арнайы сұрақ дайын! Жақсы бағың келсін! 🎯",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await send_quiz(context, update.message.chat_id, question_data)
            await update.message.reply_text(
                "Сізге арнайы сұрақ дайын! Жақсы бағың келсін! 🎯",
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logging.error(f"Викторина жіберу кезінде қате: {e}")
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Викторина жіберу кезінде қате туындады: {str(e)}"
        )

# Тақырып бойынша викторина жіберу
async def send_topic_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, topic_id: str) -> None:
    """Белгілі тақырып бойынша викторина жіберу"""
    try:
        # Сұрақтарды жүктеу
        questions = load_questions()
        
        # Тақырып бойынша сүзгілеу
        topic_questions = [q for q in questions if q.get("topic") == topic_id]
        
        # Тексеру: сұрақтар бар ма?
        if not topic_questions:
            chat_id = update.effective_chat.id
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Бұл тақырып бойынша сұрақтар табылмады."
            )
            return
        
        # Кездейсоқ сұрақ таңдау
        question_data = random.choice(topic_questions)
        
        # correct_option_id кілтін тексеру және қажет болса қосу
        if "correct_option_id" not in question_data:
            correct_option = question_data.get("correct_answer", 0)
            if isinstance(correct_option, str) and correct_option in question_data.get("options", []):
                question_data["correct_option_id"] = question_data["options"].index(correct_option)
            else:
                question_data["correct_option_id"] = 0
        
        # Тақырып идентификаторын сұраққа қосу
        question_data["topic"] = topic_id
        
        # ChatID алу
        chat_id = update.effective_chat.id
        
        # Сұрақ жіберу
        await send_quiz(context, chat_id, question_data)
        
        # Келесі сұрақ батырмасы
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Келесі сұрақ", callback_data=f"next_topic_{topic_id}")
        ]])
        
        # Хабарлама жіберу
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Тақырып бойынша сұрақ дайын! Жақсы бағың келсін! 🎯",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Тақырып бойынша викторина жіберу кезінде қате: {e}")
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Сұрақ жіберу кезінде қате туындады: {str(e)}"
        )

# Пайдаланушы ұпайларын көрсету
async def show_user_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пайдаланушы ұпайларын көрсету"""
    try:
        # Деректерді алу
        scores = load_scores()
        user_id = str(update.effective_user.id)
        
        # Хабарлама дайындау
        if user_id in scores:
            # Формат тексеру (жаңа немесе ескі)
            if isinstance(scores[user_id], dict):
                score_value = scores[user_id]["total"]
            else:
                score_value = scores[user_id]
            
            message = f"*Сіздің нәтижеңіз:*\n\nДұрыс жауаптар: {score_value}"
        else:
            message = "Сіз әлі викторинаға қатыспадыңыз"
        
        # Хабарлама жіберу (callback query немесе message түріне байланысты)
        if update.callback_query:
            await update.callback_query.message.edit_text(
                message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Артқа", callback_data="back_to_main")
                ]])
            )
        else:
            await update.message.reply_text(
                message, 
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logging.error(f"Ұпайларды көрсету кезінде қате: {e}")
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Ұпайларды көрсету кезінде қате туындады: {str(e)}"
        )

# Жетістіктер тізімін көрсету
async def show_leaderboard_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Жетістіктер тізімін көрсету"""
    try:
        scores = load_scores()
        
        if not scores:
            message = "Әзірше ешкім викторинаға қатыспаған"
            
            # Callback query немесе message түріне байланысты
            if update.callback_query:
                await update.callback_query.message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Артқа", callback_data="back_to_main")
                    ]])
                )
            else:
                await update.message.reply_text(message)
            return
        
        # Рейтингті жинау
        if any(isinstance(s, dict) for s in scores.values()):
            # Жаңа формат (dict)
            leaderboard_data = sorted(
                [(user_id, data["total"]) for user_id, data in scores.items() if isinstance(data, dict)],
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Тек 10 үздік
        else:
            # Ескі формат (int)
            leaderboard_data = sorted(
                [(user_id, score) for user_id, score in scores.items() if isinstance(score, int)],
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Тек 10 үздік
        
        if not leaderboard_data:
            message = "Рейтинг дайындауда қате орын алды"
            
            # Callback query немесе message түріне байланысты
            if update.callback_query:
                await update.callback_query.message.edit_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Артқа", callback_data="back_to_main")
                    ]])
                )
            else:
                await update.message.reply_text(message)
            return
        
        # Форматтау
        text = "*Жетістіктер тізімі* 🏆\n\n"
        
        for i, (user_id, points) in enumerate(leaderboard_data, start=1):
            try:
                user_info = await context.bot.get_chat(int(user_id))
                username = user_info.first_name
            except:
                username = f"User-{user_id[-4:]}"
            
            if i == 1:
                text += f"🥇 {username}: {points} ұпай\n"
            elif i == 2:
                text += f"🥈 {username}: {points} ұпай\n"
            elif i == 3:
                text += f"🥉 {username}: {points} ұпай\n"
            else:
                text += f"{i}. {username}: {points} ұпай\n"
        
        # Callback query немесе message түріне байланысты
        if update.callback_query:
            await update.callback_query.message.edit_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Артқа", callback_data="back_to_main")
                ]])
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logging.error(f"Жетістіктер тізімін көрсету кезінде қате: {e}")
        chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Жетістіктер тізімін көрсету кезінде қате туындады: {str(e)}"
        )

# Негізгі функция
def main() -> None:
    """Ботты іске қосу"""
    application = Application.builder().token(TOKEN).build()
    
    # Командаларды қосу
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("groupquiz", group_quiz))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register_chat))
    
    # Кнопкаларды өңдеу
    application.add_handler(CallbackQueryHandler(handle_button))
    
    # Сауалнама жауаптарын өңдеу
    application.add_handler(PollAnswerHandler(handle_poll_answer))
    
    # Хабарламаларды өңдеу
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Күнделікті сұрақтар
    job_queue = application.job_queue
    job_queue.run_daily(
        daily_quiz,
        time=datetime.time(hour=10, minute=0, tzinfo=TIMEZONE)
    )
    
    # Күнделікті еске салу
    job_queue.run_daily(
        daily_reminder,
        time=datetime.time(hour=20, minute=0, tzinfo=TIMEZONE)
    )
    
    # Апталық нәтижелер
    job_queue.run_daily(
        weekly_results,
        time=datetime.time(hour=10, minute=0, tzinfo=TIMEZONE),
        days=(6,)  # Сенбі күні
    )
    
    # Ботты іске қосу
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 