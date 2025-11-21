import logging
import asyncio
import sqlite3
import os
import html
import re
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, CommandObject
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ContentType

#мур
# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
# ID администратора для тех.поддержки
ADMIN_ID = os.getenv("ADMIN_ID") or ""

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Настройки поведения
MAX_RANK_ENTRIES = 15
SWEAR_RANK_ENTRIES = 15
REQUIRED_CHANNEL = "@silentpower_V"
REQUIRED_CHANNEL_URL = "https://t.me/silentpower_V"
WELCOME_TEXT = (
    "👋 Добро пожаловать в SpringtrapSilent!\n\n"
    "Здесь вы можете настроить свой глобальный автоответчик "
    "(он будет использоваться, если вы не указали персональный) "
    "и связь с тех.поддержкой."
)
SWEAR_WORDS = {
    "бля", "блять", "блядь", "бляха", "блят", "бляха-муха", "бляцкий",
    "блядский", "блядство", "блядина", "блядище", "блядун", "бляшка",
    "поблядушка", "блядовать", "блядствовать", "заблядованный", "блядовоз",
    "блядогон",

    "хуй", "хер", "хуево", "хуёво", "хуйня", "хуя", "хуяк", "хуяр",
    "хуесос", "хуёв", "хуев", "хуич", "хуеглот", "хуевина", "хуила",
    "хуило", "хуйло", "хуеплет", "хуеплёт", "хуел", "хуепиздина",
    "охуеть", "охуенно", "охуевший", "нахуй", "нахер", "нах", "нахрен",
    "нахуя", "похуй", "похуизм", "хуета", "хуй моржовый", "хуепутало",
    "хуерыга", "хуеверт",

    "пизда", "пиздец", "пиздюк", "пиздёныш", "пиздабол", "пиздатый",
    "пиздоватый", "пиздобратия", "пиздопротивный", "распиздяй",
    "спиздить", "опизденеть", "пиздолиз", "пиздоглазый", "пиздострадалец",
    "пиздить", "впиздячить", "пиздюлина", "распиздяйство", "пиздолиз",
    "пизд", "пизжу", "пизжуешь", "пиздануть",

    "ебать", "ебал", "ебёт", "ебет", "ебись", "ебнули", "ебан", "ебнутый",
    "ебашить", "ебарь", "ебанутый", "еблан", "ебло", "ебанина", "выебать",
    "заебать", "наебать", "отъебись", "проебать", "съебаться", "уебать",
    "ебаться", "заебись", "ебалай", "ебанат", "ебаться-сраться", "долбоеб",
    "долбоёб", "ебака", "еблище", "ебошить", "еботэ",

    "сука", "сучка", "сучара", "сук", "сукаблять", "сучий", "сучонок",
    "сучье", "сучий потрох",
   
    "пидор", "пидорас", "пидр", "пидарас", "пидрила", "пидорок", "гомик",
    "гомосек", "голубой", "петух", "дырявый",

    "гандон", "гондон", "уебок", "уёбок", "уебан", "уебище", "уебанский",
    "мразь", "мразота", "сволочь", "скотина", "скотский", "чмо", "чмошник",
    "дурак", "даун", "идиот", "дебил", "кретин", "идиотина", "мудак",
    "мудило", "мудозвон", "шлюха", "проститутка", "курва", "шалава",
    "шмандовка", "паскуда", "погань", "тварь", "ублюдок", "мерзость",
    "подонок", "залупа", "залупился", "щенок",

    "дрочить", "дрочила", "дерьмо", "говно", "говнюк", "говнарь",
    "говнистый", "говнецо", "сраный", "ссанина", "мокрощелка",
    "мокрощёлка",
    
    "жопа", "жопошник", "жопный", "жопарь", "очко", "туз", "анус",
    "вагина", "манда", "мандовошка"
}

SUPPORT_MEDIA_TYPES = {
    ContentType.PHOTO,
    ContentType.VIDEO,
    ContentType.AUDIO,
    ContentType.VOICE,
    ContentType.VIDEO_NOTE,
    ContentType.ANIMATION,
    ContentType.DOCUMENT,
    ContentType.STICKER
}

WORD_PATTERN = re.compile(r"[\wёЁ]+", re.UNICODE)

# ==================== База данных ====================
class Database:
    def __init__(self, db_name="joyguard.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица блокировок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                blocker_id INTEGER NOT NULL,
                blocked_id INTEGER NOT NULL,
                personal_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, blocker_id, blocked_id)
            )
        ''')
        
        # Таблица глобальных автоответчиков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_autoresponders (
                user_id INTEGER PRIMARY KEY,
                message TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для тех.поддержки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_bans (
                user_id INTEGER PRIMARY KEY,
                block_media INTEGER NOT NULL DEFAULT 0,
                block_all INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица глобальных блокировок ("Спринг стоп все")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                blocker_id INTEGER NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, blocker_id)
            )
        ''')

        # Таблица исключений для глобальных блокировок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_block_exceptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                blocker_id INTEGER NOT NULL,
                allowed_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, blocker_id, allowed_id)
            )
        ''')

        # Таблица для антиспама (время последнего сообщения)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS last_support_time (
                user_id INTEGER PRIMARY KEY,
                last_message_time INTEGER NOT NULL
            )
        ''')

        # Таблица профилей пользователей (для поиска по username)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                username_lower TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица статистики по матам
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS swear_stats (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
        ''')

        conn.commit()
        conn.close()
    
    def toggle_block(self, chat_id: int, blocker_id: int, blocked_id: int, personal_message: str = None):
        """Переключение блокировки (блокировать/разблокировать)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли блокировка
        cursor.execute('''
            SELECT id FROM blocks 
            WHERE chat_id = ? AND blocker_id = ? AND blocked_id = ?
        ''', (chat_id, blocker_id, blocked_id))
        
        existing = cursor.fetchone()
        
        if existing:
            # Удаляем блокировку
            cursor.execute('''
                DELETE FROM blocks 
                WHERE chat_id = ? AND blocker_id = ? AND blocked_id = ?
            ''', (chat_id, blocker_id, blocked_id))
            conn.commit()
            conn.close()
            return False  # Разблокировано
        else:
            # Добавляем блокировку
            cursor.execute('''
                INSERT INTO blocks (chat_id, blocker_id, blocked_id, personal_message)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, blocker_id, blocked_id, personal_message))
            conn.commit()
            conn.close()
            return True  # Заблокировано
    
    def is_blocked(self, chat_id: int, blocker_id: int, blocked_id: int):
        """Проверка, заблокирован ли пользователь"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT personal_message FROM blocks 
            WHERE chat_id = ? AND blocker_id = ? AND blocked_id = ?
        ''', (chat_id, blocker_id, blocked_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return True, result[0]  # Заблокирован, персональное сообщение
        return False, None
    
    def get_chat_blocks(self, chat_id: int):
        """Получить все блокировки в чате"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT blocker_id, blocked_id FROM blocks 
            WHERE chat_id = ?
        ''', (chat_id,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_blocks_by_blocker(self, chat_id: int, blocker_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT blocked_id FROM blocks WHERE chat_id = ? AND blocker_id = ?''',
            (chat_id, blocker_id)
        )
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results
    
    def set_global_autoresponder(self, user_id: int, message: str):
        """Установить глобальный автоответчик"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO global_autoresponders (user_id, message, updated_at)
            VALUES (?, ?, ?)
        ''', (user_id, message, datetime.now()))
        
        conn.commit()
        conn.close()
    
    def get_global_autoresponder(self, user_id: int):
        """Получить глобальный автоответчик"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message FROM global_autoresponders 
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def save_support_message(self, user_id, message):
        """Сохранение сообщения в тех.поддержку"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO support_messages (user_id, message) VALUES (?, ?)",
            (user_id, message)
        )
        conn.commit()
        conn.close()

    def get_support_ban(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT block_media, block_all FROM support_bans WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {"block_media": bool(row[0]), "block_all": bool(row[1])}

    def _upsert_support_ban(self, user_id: int, block_media: int, block_all: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO support_bans (user_id, block_media, block_all)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                block_media = excluded.block_media,
                block_all = excluded.block_all,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, block_media, block_all)
        )
        conn.commit()
        conn.close()

    def set_support_ban(self, user_id: int, *, block_media: bool | None = None, block_all: bool | None = None):
        current = self.get_support_ban(user_id) or {"block_media": False, "block_all": False}
        new_media = block_media if block_media is not None else current["block_media"]
        new_all = block_all if block_all is not None else current["block_all"]
        self._upsert_support_ban(user_id, int(new_media), int(new_all))
        return {"block_media": new_media, "block_all": new_all}

    def toggle_support_media_ban(self, user_id: int):
        current = self.get_support_ban(user_id) or {"block_media": False, "block_all": False}
        new_state = not current["block_media"]
        self._upsert_support_ban(user_id, int(new_state), int(current["block_all"]))
        return new_state

    def toggle_support_full_ban(self, user_id: int):
        current = self.get_support_ban(user_id) or {"block_media": False, "block_all": False}
        new_state = not current["block_all"]
        self._upsert_support_ban(user_id, int(current["block_media"]), int(new_state))
        return new_state

    def increment_swear(self, chat_id: int, user_id: int, amount: int = 1):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO swear_stats (chat_id, user_id, count)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                count = count + excluded.count
            """,
            (chat_id, user_id, amount)
        )
        conn.commit()
        conn.close()

    def get_swear_ranking(self, chat_id: int, limit: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, count FROM swear_stats
            WHERE chat_id = ?
            ORDER BY count DESC, user_id ASC
            LIMIT ?
            """,
            (chat_id, limit)
        )
        results = cursor.fetchall()
        conn.close()
        return results

    def toggle_global_block(self, chat_id, blocker_id, message=None):
        """Вкл/выкл режима 'Спринг стоп все'"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM global_blocks WHERE chat_id = ? AND blocker_id = ?",
            (chat_id, blocker_id)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "DELETE FROM global_blocks WHERE chat_id = ? AND blocker_id = ?",
                (chat_id, blocker_id)
            )
            conn.commit()
            conn.close()
            return False
        else:
            cursor.execute(
                "INSERT INTO global_blocks (chat_id, blocker_id, message) VALUES (?, ?, ?)",
                (chat_id, blocker_id, message)
            )
            # При новом включении глобального блока удаляем старые исключения
            cursor.execute(
                "DELETE FROM global_block_exceptions WHERE chat_id = ? AND blocker_id = ?",
                (chat_id, blocker_id)
            )
            conn.commit()
            conn.close()
            return True

    def get_global_block(self, chat_id, blocker_id):
        """Возвращает флаг и текст глобальной блокировки"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message FROM global_blocks WHERE chat_id = ? AND blocker_id = ?",
            (chat_id, blocker_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return False, None
        return True, row[0]

    def toggle_global_block_exception(self, chat_id, blocker_id, allowed_id):
        """Тоггл исключения для режима 'Спринг стоп все'"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM global_block_exceptions WHERE chat_id = ? AND blocker_id = ? AND allowed_id = ?",
            (chat_id, blocker_id, allowed_id)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "DELETE FROM global_block_exceptions WHERE chat_id = ? AND blocker_id = ? AND allowed_id = ?",
                (chat_id, blocker_id, allowed_id)
            )
            conn.commit()
            conn.close()
            return False
        else:
            cursor.execute(
                "INSERT INTO global_block_exceptions (chat_id, blocker_id, allowed_id) VALUES (?, ?, ?)",
                (chat_id, blocker_id, allowed_id)
            )
            conn.commit()
            conn.close()
            return True

    def is_global_block_exception(self, chat_id, blocker_id, allowed_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM global_block_exceptions WHERE chat_id = ? AND blocker_id = ? AND allowed_id = ?",
            (chat_id, blocker_id, allowed_id)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def upsert_user_profile(self, user):
        if user is None:
            return
        user_id = getattr(user, "id", None)
        if user_id is None:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        username = getattr(user, "username", None)
        username_lower = username.lower() if username else None
        first_name = getattr(user, "first_name", None)
        last_name = getattr(user, "last_name", None)
        cursor.execute(
            """
            INSERT INTO user_profiles (user_id, username, username_lower, first_name, last_name, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                username_lower = excluded.username_lower,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, username, username_lower, first_name, last_name)
        )
        conn.commit()
        conn.close()

    def get_user_by_username(self, username: str):
        if not username:
            return None
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, first_name, username FROM user_profiles WHERE username_lower = ?",
            (username.lower(),)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "user_id": row[0],
                "first_name": row[1],
                "username": row[2]
            }
        return None

    def can_send_support_message(self, user_id, cooldown_seconds=30):
        """Проверка, может ли пользователь отправить сообщение (антиспам)"""
        import time
        conn = self.get_connection()
        cursor = conn.cursor()
        
        current_time = int(time.time())
        
        cursor.execute(
            "SELECT last_message_time FROM last_support_time WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if result:
            last_time = result[0]
            time_passed = current_time - last_time
            
            if time_passed < cooldown_seconds:
                conn.close()
                return False, cooldown_seconds - time_passed
        
        # Обновляем время последнего сообщения
        cursor.execute(
            "INSERT OR REPLACE INTO last_support_time (user_id, last_message_time) VALUES (?, ?)",
            (user_id, current_time)
        )
        conn.commit()
        conn.close()
        return True, 0

db = Database()

# ==================== FSM States ====================
class BotStates(StatesGroup):
    waiting_global_autoresponder = State()
    waiting_support_message = State()
    waiting_admin_reply = State()  # Ожидание ответа админа

# ==================== Клавиатуры ====================
def get_main_keyboard():
    """Главная клавиатура в личных сообщениях"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Глобальный автоответчик")],
            [KeyboardButton(text="👨‍🔧 Тех.поддержка"), KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


SUBSCRIBE_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔔 Подписаться", url=REQUIRED_CHANNEL_URL)],
    [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
])

SUBSCRIBE_GROUP_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔔 Подписаться на Silent Power", url=REQUIRED_CHANNEL_URL)]
])


async def is_user_subscribed(user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in {"member", "administrator", "creator"}
    except TelegramBadRequest:
        return False


async def ensure_channel_subscription(message: types.Message) -> bool:
    if message.chat.type != "private" or not REQUIRED_CHANNEL:
        return True
    if await is_user_subscribed(message.from_user.id):
        return True
    await message.answer(
        "Чтобы пользоваться ботом, подпишитесь на канал Silent и вернитесь сюда.",
        reply_markup=SUBSCRIBE_KEYBOARD
    )
    return False


async def ensure_group_subscription(message: types.Message) -> bool:
    if message.chat.type not in {"group", "supergroup"} or not REQUIRED_CHANNEL or not message.from_user:
        return True
    if await is_user_subscribed(message.from_user.id):
        return True
    await send_temp_answer(
        message,
        "Чтобы пользоваться командами SpringtrapSilent, подпишитесь на канал Silent Power и повторите команду.",
        reply_markup=SUBSCRIBE_GROUP_KEYBOARD
    )
    return False


def build_support_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    ban_info = db.get_support_ban(user_id) or {"block_media": False, "block_all": False}
    media_text = "🚫 Запретить медиа" if not ban_info["block_media"] else "♻️ Разрешить медиа"
    full_text = "⛔️ Полный бан" if not ban_info["block_all"] else "♻️ Разрешить пользователя"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{user_id}")],
        [
            InlineKeyboardButton(text=media_text, callback_data=f"support_media_{user_id}"),
            InlineKeyboardButton(text=full_text, callback_data=f"support_full_{user_id}")
        ]
    ])


async def send_temp_answer(message: types.Message, text: str, *, delay: int = 20, **kwargs) -> None:
    """Отправляет ответ, который автоматически удалится через delay секунд."""
    sent_message = await message.answer(text, **kwargs)

    async def _delete_later():
        try:
            await asyncio.sleep(delay)
            await sent_message.delete()
        except Exception as e:
            logger.debug(f"Не удалось удалить временное сообщение: {e}")

    asyncio.create_task(_delete_later())


def record_user_profiles_from_message(message: types.Message):
    """Сохранить информацию об участвующих пользователях для поиска по username."""
    if message.from_user:
        db.upsert_user_profile(message.from_user)
    if message.reply_to_message and message.reply_to_message.from_user:
        db.upsert_user_profile(message.reply_to_message.from_user)


def extract_mentioned_usernames(message: types.Message) -> list[str]:
    usernames: list[str] = []

    def _extract_from(text: str | None, entities: list[types.MessageEntity] | None):
        if not text or not entities:
            return
        for entity in entities:
            if entity.type == "mention":
                mention_text = text[entity.offset: entity.offset + entity.length]
                if mention_text.startswith("@"):
                    usernames.append(mention_text[1:])

    _extract_from(message.text, message.entities)
    _extract_from(message.caption, message.caption_entities)
    return usernames


def gather_targets_from_message(message: types.Message) -> list[dict]:
    """Возвращает список пользователей, которых мог адресовать отправитель (ответ или упоминание)."""
    targets: list[dict] = []
    seen_ids: set[int] = set()
    seen_usernames: set[str] = set()

    def add_target(user_id: int | None, display_name: str | None, username: str | None = None):
        if user_id:
            if user_id in seen_ids:
                return
            seen_ids.add(user_id)
        elif username:
            uname = username.lower()
            if uname in seen_usernames:
                return
            seen_usernames.add(uname)
        else:
            return

        name = display_name or (f"@{username}" if username else (f"ID{user_id}" if user_id else ""))
        targets.append({"user_id": user_id, "name": name or None, "username": username})

    # Адресат из ответа
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        db.upsert_user_profile(target_user)
        add_target(target_user.id, target_user.first_name, target_user.username)

    def process_entities(text: str | None, entities: list[types.MessageEntity] | None):
        if not text or not entities:
            return
        for entity in entities:
            if entity.type == "text_mention" and entity.user:
                db.upsert_user_profile(entity.user)
                add_target(entity.user.id, entity.user.first_name, entity.user.username)
            elif entity.type == "mention":
                mention_text = text[entity.offset: entity.offset + entity.length]
                if mention_text.startswith("@"):
                    username = mention_text[1:]
                    profile = db.get_user_by_username(username)
                    if profile:
                        add_target(
                            profile["user_id"],
                            profile.get("first_name"),
                            profile.get("username")
                        )
                    else:
                        add_target(None, mention_text, username)

    process_entities(message.text, message.entities)
    process_entities(message.caption, message.caption_entities)

    return targets


def count_swears_in_text(text: str | None) -> int:
    if not text:
        return 0
    lower_text = text.lower()
    tokens = WORD_PATTERN.findall(lower_text)
    return sum(1 for token in tokens if token in SWEAR_WORDS)


async def process_swear_stats(message: types.Message):
    if message.chat.type in {"group", "supergroup"} and message.from_user:
        combined_text_parts = [part for part in (message.text, message.caption) if part]
        if not combined_text_parts:
            return
        joined_text = " \n".join(combined_text_parts)
        lower_joined = joined_text.lower()
        if not any(word in lower_joined for word in SWEAR_WORDS):
            return
        swear_count = count_swears_in_text(joined_text)
        if swear_count > 0:
            record_user_profiles_from_message(message)
            db.increment_swear(message.chat.id, message.from_user.id, swear_count)


async def send_swear_ranking(message: types.Message):
    ranking = db.get_swear_ranking(message.chat.id, SWEAR_RANK_ENTRIES)
    if not ranking:
        await message.answer("📊 В этом чате пока нет данных по матам.")
        return

    lines = ["🤬 Топ по матюкам:\n"]
    for idx, (user_id, count) in enumerate(ranking, start=1):
        name = await get_chat_user_name(message.chat.id, user_id)
        lines.append(f"{idx}. {name} — {count}")

    await message.answer("\n".join(lines))


async def get_chat_user_name(chat_id: int, user_id: int) -> str:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        user = member.user
        if user.full_name:
            return user.full_name
        if user.username:
            return f"@{user.username}"
    except Exception:
        pass
    return f"ID{user_id}"


async def send_block_profile(message: types.Message, target_user_id: int, title_name: str | None = None):
    blocked_ids = db.get_blocks_by_blocker(message.chat.id, target_user_id)
    display_name = title_name or await get_chat_user_name(message.chat.id, target_user_id)
    text_lines = [
        f"📊 Профиль блокировок: {display_name}",
        f"Всего заблокировано: {len(blocked_ids)}"
    ]

    if blocked_ids:
        text_lines.append("\nЗаблокированы:")
        for idx, blocked_id in enumerate(blocked_ids, start=1):
            blocked_name = await get_chat_user_name(message.chat.id, blocked_id)
            text_lines.append(f"{idx}. {blocked_name}")
    else:
        text_lines.append("\nПока никого не заблокировал(а).")

    await message.answer("\n".join(text_lines))


async def send_block_ranking(message: types.Message):
    blocks = db.get_chat_blocks(message.chat.id)
    if not blocks:
        await message.answer("📋 В этом чате нет активных блокировок.")
        return

    stats: dict[int, int] = {}
    for blocker_id, _ in blocks:
        stats[blocker_id] = stats.get(blocker_id, 0) + 1

    ranking = sorted(stats.items(), key=lambda item: (-item[1], item[0]))[:MAX_RANK_ENTRIES]

    lines = ["🏆 Рейтинг блокировок чата:\n"]
    for idx, (user_id, count) in enumerate(ranking, start=1):
        name = await get_chat_user_name(message.chat.id, user_id)
        lines.append(f"{idx}. {name} — {count}")

    await message.answer("\n".join(lines))


def remove_target_mentions(text: str, targets: list[dict]) -> str:
    if not text:
        return text
    result = text
    for target in targets:
        username = target.get("username")
        if username:
            pattern = rf"@{re.escape(username)}\b"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    # Удаляем лишние пробелы
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def extract_personal_message(after_command_text: str, targets: list[dict]) -> str | None:
    if not after_command_text:
        return None

    candidate = after_command_text.strip()

    newline_index = candidate.find('\n')
    if newline_index != -1:
        candidate = candidate[newline_index + 1:]

    candidate = candidate.lstrip("-—:").strip()
    candidate = remove_target_mentions(candidate, targets)
    return candidate or None


async def resolve_targets_with_fetch(chat_id: int, targets: list[dict]):
    for target in targets:
        if target.get("user_id") or not target.get("username"):
            continue
        username = target["username"]
        resolved_user = None

        username_with_at = username if username.startswith("@") else f"@{username}"
        try:
            chat_obj = await bot.get_chat(username_with_at)
            if chat_obj and getattr(chat_obj, "type", None) == "private":
                resolved_user = chat_obj
        except TelegramBadRequest:
            resolved_user = None

        if resolved_user is None:
            continue

        target["user_id"] = resolved_user.id
        target["name"] = resolved_user.first_name or getattr(resolved_user, "full_name", None) or target.get("name") or username_with_at
        target["username"] = resolved_user.username or username
        db.upsert_user_profile(resolved_user)

# ==================== Обработчики команд ====================

@dp.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added(event: types.ChatMemberUpdated):
    """Обработчик добавления бота в группу"""
    if event.chat.type not in {"group", "supergroup"}:
        return
    added_by = getattr(event, "from_user", None)
    await event.answer(
        "👋 Спасибо за добавление SpringtrapSilent!\n\n"
        "📝 Доступные команды:\n"
        "• Ответьте на сообщение пользователя командой 'Спринг стоп' для блокировки\n"
        "• 'Спринг стоп' + текст для установки персонального автоответчика\n"
        "• 'Спринг список' для просмотра блокировок в чате\n"
        "• 'Топ маты' / 'Топ матов' для рейтинга по количеству матов\n"
        "• 'Спринг стоп все' для включения/выключения режима и указания персонального автоответчика (либо глобального в ЛС)\n"
        "• Командой 'Спринг стоп' по конкретному пользователю можно убрать его из общего блок-листа\n\n"
        "⚠️ ВАЖНО: Сделайте бота администратором с правом удаления сообщений!\n\n"
        + ("ℹ️ Чтобы пользоваться командами бота, подпишитесь на [канал](https://t.me/silentpower_V).\n\n"
           if REQUIRED_CHANNEL else "")
        + "💬 Напишите мне в личку для настройки глобального автоответчика.",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start (только в личных сообщениях)"""
    if message.chat.type != "private":
        return
    if not await ensure_channel_subscription(message):
        return

    await message.answer(WELCOME_TEXT, reply_markup=get_main_keyboard())

@dp.message(F.text.func(lambda text: isinstance(text, str) and text.lower().startswith("спринг список")))
async def cmd_list(message: types.Message):
    """Команда 'Спринг список' - рейтинг и профили блокировок"""
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в групповых чатах.")
        return
    if not await ensure_group_subscription(message):
        return

    text = message.text.strip()
    lower_text = text.lower()

    record_user_profiles_from_message(message)
    targets = gather_targets_from_message(message)
    await resolve_targets_with_fetch(message.chat.id, targets)

    if lower_text.startswith("спринг список мой"):
        await send_block_profile(message, message.from_user.id)
        return

    if targets:
        target = targets[0]
        target_id = target.get("user_id")
        target_name = target.get("name")
        if target_id:
            await send_block_profile(message, target_id, target_name)
        else:
            await send_temp_answer(
                message,
                "❌ Не удалось определить пользователя. Убедитесь, что он ранее писал в чате."
            )
        return

    await send_block_ranking(message)

@dp.message(F.text.func(lambda text: isinstance(text, str) and text.strip().lower() == "бот"))
async def ping_bot(message: types.Message):
    """Простая проверка активности по слову 'бот'"""
    await message.answer("Че надо")

@dp.message(F.text.func(lambda text: isinstance(text, str) and "спринг стоп" in text.lower()))
async def cmd_joy_stop(message: types.Message):
    """Команда 'Спринг стоп' - блокировка/разблокировка"""
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в групповых чатах.")
        return
    if not await ensure_group_subscription(message):
        return
    
    blocker_id = message.from_user.id
    record_user_profiles_from_message(message)
    targets = gather_targets_from_message(message)
    await resolve_targets_with_fetch(message.chat.id, targets)
    text = message.text
    text_lower = text.lower()
    cmd_pos = text_lower.find("спринг стоп")
    if cmd_pos == -1:
        return

    after_command_text = text[cmd_pos + len("спринг стоп"):]
    tail_lower = text_lower[cmd_pos:].lstrip()

    # Обработка режима "Спринг стоп все"
    global_block_enabled, global_block_message = db.get_global_block(message.chat.id, blocker_id)

    if tail_lower.startswith("спринг стоп все"):
        remaining_text = text[cmd_pos + len("спринг стоп все"):]
        global_message = extract_personal_message(remaining_text, targets)
        enabled = db.toggle_global_block(message.chat.id, blocker_id, global_message)
        blocker_name = message.from_user.first_name
        if enabled:
            if global_message:
                response = (
                    f"🔒 {blocker_name} включил(а) режим 'Спринг стоп все'. Никто не может отвечать на его сообщения.\n\n"
                    f"Персональный ответ:\n{global_message}"
                )
            else:
                response = f"🔒 {blocker_name} включил(а) режим 'Спринг стоп все'. Никто не может отвечать на его сообщения."
        else:
            response = f"🔓 {blocker_name} отключил(а) режим 'Спринг стоп все'. Теперь пользователи снова могут отвечать."
        await send_temp_answer(message, response)
        return

    personal_message = extract_personal_message(after_command_text, targets)

    # Обычный режим требует указать пользователя (ответом или @username)
    if not targets:
        await send_temp_answer(
            message,
            "❌ Укажите пользователя: ответьте на его сообщение или добавьте @username в команду."
        )
        return

    target = targets[0]
    blocked_id = target.get("user_id")
    blocked_name = target.get("name") or "пользователь"

    if not blocked_id:
        await send_temp_answer(
            message,
            "❌ Не удалось определить пользователя. Убедитесь, что он ранее писал в чате."
        )
        return

    # Нельзя заблокировать самого себя
    if blocker_id == blocked_id:
        await message.answer("❌ Вы не можете заблокировать самого себя.")
        return

    # Если включен "Спринг стоп все", то команда работает как исключение
    if global_block_enabled:
        allowed = db.toggle_global_block_exception(message.chat.id, blocker_id, blocked_id)
        blocker_name = message.from_user.first_name
        if allowed:
            response = (
                f"🔓 {blocker_name} разрешил(а) пользователю {blocked_name} отвечать, даже когда включён режим 'Спринг стоп все'."
            )
        else:
            response = (
                f"🔒 {blocker_name} снова запретил(а) пользователю {blocked_name} отвечать в режиме 'Спринг стоп все'."
            )
        await send_temp_answer(message, response)
        return

    # Переключаем блокировку
    is_blocked = db.toggle_block(
        message.chat.id,
        blocker_id,
        blocked_id,
        personal_message
    )

    blocker_name = message.from_user.first_name
    blocked_name = target.get("name") or "пользователь"

    if is_blocked:
        if personal_message:
            response = f"🔒 {blocker_name} запретил(а) пользователю {blocked_name} отвечать на свои сообщения и установил(а) персональный автоответчик."
        else:
            response = f"🔒 {blocker_name} запретил(а) пользователю {blocked_name} отвечать на свои сообщения."
    else:
        response = f"🔓 {blocker_name} разрешил(а) пользователю {blocked_name} снова отвечать на свои сообщения."

    await send_temp_answer(message, response)


@dp.message(F.text.func(
    lambda text: isinstance(text, str) and text.strip().lower().startswith(("топ маты", "топ матов"))
))
async def cmd_swear_top(message: types.Message):
    if message.chat.type != "private":
        if not await ensure_group_subscription(message):
            return
        await send_swear_ranking(message)
    else:
        await message.answer("Команда работает только в групповых чатах.")
        return

@dp.message((F.chat.type == "group") | (F.chat.type == "supergroup"))
async def check_reply_block(message: types.Message):
    """Проверка сообщений на попытку связаться с пользователем, который ограничил ответы."""
    if not message.from_user:
        return

    await process_swear_stats(message)

    replier_id = message.from_user.id
    record_user_profiles_from_message(message)
    targets = gather_targets_from_message(message)

    if not targets:
        return

    blocked_target = None
    blocker_id = None
    personal_message = None

    for target in targets:
        target_id = target.get("user_id")
        if not target_id:
            continue

        global_block_enabled, global_block_message = db.get_global_block(message.chat.id, target_id)
        if global_block_enabled and not db.is_global_block_exception(message.chat.id, target_id, replier_id):
            blocked_target = target
            blocker_id = target_id
            personal_message = global_block_message
            break

        is_blocked, personal_msg = db.is_blocked(message.chat.id, target_id, replier_id)
        if is_blocked:
            blocked_target = target
            blocker_id = target_id
            personal_message = personal_msg
            break

    if not blocked_target:
        return

    try:
        await message.delete()

        autoresponder = personal_message or db.get_global_autoresponder(blocker_id)
        if not autoresponder:
            autoresponder = "Пользователь установил ограничение на ответы к своим сообщениям."

        replier_mention = message.from_user.mention_html()
        target_name = blocked_target.get("name") or "этот пользователь"
        text = (
            f"{replier_mention}, {html.escape(target_name)} установил(а) для вас следующий ответ:\n\n"
            f"\"{html.escape(autoresponder)}\""
        )

        await send_temp_answer(message, text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при обработке заблокированного сообщения: {e}")
        await message.answer(
            "⚠️ Не удалось удалить сообщение. Убедитесь, что бот является администратором с правом удаления сообщений."
        )

# ==================== Обработчики для личных сообщений ====================

@dp.message(F.text == "✍️ Глобальный автоответчик")
async def global_autoresponder_menu(message: types.Message, state: FSMContext):
    """Меню глобального автоответчика"""
    if message.chat.type != "private":
        return
    if not await ensure_channel_subscription(message):
        return
    
    # Очищаем любое предыдущее состояние
    await state.clear()
    
    current = db.get_global_autoresponder(message.from_user.id)
    
    text = "✍️ Глобальный автоответчик\n\n"
    if current:
        text += f"Текущий автоответчик:\n\"{current}\"\n\n"
    else:
        text += "У вас пока не установлен глобальный автоответчик.\n\n"
    
    text += "Отправьте мне новый текст автоответчика или /cancel для отмены."
    
    await message.answer(text)
    await state.set_state(BotStates.waiting_global_autoresponder)

@dp.message(BotStates.waiting_global_autoresponder)
async def save_global_autoresponder(message: types.Message, state: FSMContext):
    """Сохранение глобального автоответчика"""
    if not await ensure_channel_subscription(message):
        await state.clear()
        return
    # Проверяем, нажата ли кнопка меню
    if message.text == "👨‍🔧 Тех.поддержка":
        await state.clear()
        await support_menu(message, state)
        return
    
    if message.text == "❓ Помощь":
        await state.clear()
        await help_menu(message, state)
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        return
    
    db.set_global_autoresponder(message.from_user.id, message.text)
    await state.clear()
    await message.answer(
        "✅ Глобальный автоответчик успешно установлен!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "👨‍🔧 Тех.поддержка")
async def support_menu(message: types.Message, state: FSMContext):
    """Меню тех.поддержки"""
    if message.chat.type != "private":
        return
    if not await ensure_channel_subscription(message):
        return
    
    # Очищаем любое предыдущее состояние
    await state.clear()
    
    await message.answer(
        "👨‍🔧 Тех.поддержка\n\n"
        "Опишите вашу проблему или вопрос, и я передам его администраторам. Можете приложить медиа.\n\n"
        "Отправьте /cancel для отмены."
    )
    await state.set_state(BotStates.waiting_support_message)


@dp.message(BotStates.waiting_support_message)
async def save_support_message(message: types.Message, state: FSMContext):
    """Сохранение сообщения в тех.поддержку"""
    if not await ensure_channel_subscription(message):
        await state.clear()
        return
    # Проверяем, нажата ли кнопка меню
    if message.text == "✍️ Глобальный автоответчик":
        await state.clear()
        await global_autoresponder_menu(message, state)
        return

    if message.text == "❓ Помощь":
        await state.clear()
        await help_menu(message, state)
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_main_keyboard())
        return
    
    ban_info = db.get_support_ban(message.from_user.id)
    if ban_info and ban_info["block_all"]:
        await message.answer(
            "",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    if ban_info and ban_info["block_media"] and message.content_type in SUPPORT_MEDIA_TYPES:
        await message.answer("🚫 Вам запрещено отправлять медиа в техподдержку. Опишите проблему текстом.")
        return

    # Проверка антиспама
    can_send, wait_time = db.can_send_support_message(message.from_user.id, cooldown_seconds=30)
    if not can_send:
        await message.answer(
            f"⏰ Пожалуйста, подождите {wait_time} сек. перед отправкой следующего сообщения.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    # Сохраняем в БД
    stored_text = message.text or message.caption or f"<{message.content_type}>"
    db.save_support_message(message.from_user.id, stored_text)

    # Отправляем администратору, если ID указан
    if ADMIN_ID:
        try:
            admin_id = int(ADMIN_ID)
            user_info = f"От: {message.from_user.first_name}"
            if message.from_user.username:
                user_info += f" (@{message.from_user.username})"
            user_info += f"\nID: {message.from_user.id}"

            keyboard = build_support_admin_keyboard(message.from_user.id)

            header_lines = ["📩 Новое сообщение в тех.поддержку:", "", user_info]
            if message.text:
                header_lines.append("\nСообщение:\n" + message.text)
            elif message.caption:
                header_lines.append("\nПодпись:\n" + message.caption)
            else:
                header_lines.append(f"\nТип контента: {message.content_type}")

            await bot.send_message(
                admin_id,
                "\n".join(header_lines),
                reply_markup=keyboard
            )

            if message.content_type in SUPPORT_MEDIA_TYPES:
                await message.copy_to(admin_id)

            success_text = "✅ Ваше сообщение отправлено администратору!\n" \
                          "Он свяжется с вами в ближайшее время."
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу: {e}")
            success_text = "✅ Ваше сообщение сохранено!\n" \
                          "Администраторы увидят его при следующей проверке."
    else:
        success_text = "✅ Ваше сообщение сохранено в базу данных!\n" \
                      "Для прямой отправки администратору добавьте ADMIN_ID в .env файл."
    
    await state.clear()
    await message.answer(success_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "❓ Помощь")
async def help_menu(message: types.Message, state: FSMContext):
    """Меню помощи"""
    if message.chat.type != "private":
        return
    if not await ensure_channel_subscription(message):
        await state.clear()
        return
    
    # Очищаем состояние при переходе в помощь
    await state.clear()
    
    await message.answer(
        "❓ Помощь по SpringtrapSilent\n\n"
        "📝 Команды в групповых чатах:\n\n"
        "1️⃣ Спринг стоп\n"
        "Ответьте на сообщение пользователя этой командой, чтобы заблокировать/разблокировать ему возможность отвечать на ваши сообщения.\n\n"
        "1️⃣➕ Спринг стоп все\n"
        "Останавливает всех: никто не сможет отвечать на ваши сообщения до повторного выключения.\n\n"
        "2️⃣ Спринг стоп + текст\n"
        "Напишите команду 'Спринг стоп' и с новой строки ваш текст автоответчика. "
        "Этот текст будет показываться заблокированному пользователю при попытке ответить вам.\n\n"
        "3️⃣ Спринг список\n"
        "Показывает список всех блокировок в текущем чате.\n\n"
        "4️⃣ Топ маты / Топ матов\n"
        "Выводит рейтинг пользователей чата по количеству зафиксированных матов.\n\n"
        "⚙️ Настройки в личных сообщениях:\n\n"
        "• Глобальный автоответчик - текст по умолчанию для всех блокировок\n"
        "• Тех.поддержка - связь с администраторами\n"
        "• Помощь - это сообщение\n\n"
        "⚠️ Важно: Бот должен быть администратором чата с правом удаления сообщений!",
        reply_markup=get_main_keyboard()
    )

# ==================== Команды администратора ====================

@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку 'Ответить'"""
    # Проверяем, что это администратор
    if not ADMIN_ID or str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("У вас нет прав администратора", show_alert=True)
        return
    
    # Извлекаем ID пользователя
    user_id = int(callback.data.split("_")[1])
    
    # Сохраняем ID в состоянии
    await state.update_data(reply_to_user_id=user_id)
    await state.set_state(BotStates.waiting_admin_reply)
    
    await callback.message.answer(
        f"✏️ Напишите ваш ответ пользователю {user_id}:\n\n"
        "Отправьте /cancel для отмены."
    )
    await callback.answer()

@dp.message(BotStates.waiting_admin_reply)
async def send_admin_reply(message: types.Message, state: FSMContext):
    """Отправка ответа админа пользователю"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return
    
    # Получаем ID пользователя
    data = await state.get_data()
    user_id = data.get("reply_to_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя не найден.")
        await state.clear()
        return
    
    try:
        if message.text:
            await bot.send_message(
                user_id,
                f"💬 Ответ от администратора:\n\n{message.text}"
            )
        else:
            await bot.send_message(user_id, "💬 Ответ от администратора:")
            await message.copy_to(user_id)

        await message.answer(
            f"✅ Ответ отправлен пользователю {user_id}!\n\n"
            + (f"Текст ответа:\n{message.text}" if message.text else "Медиа-файл отправлен.")
        )

    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()


@dp.callback_query(F.data.startswith("support_media_"))
async def toggle_support_media(callback: types.CallbackQuery):
    if not ADMIN_ID or str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    new_state = db.toggle_support_media_ban(user_id)
    text = "Медиа запрещены" if new_state else "Медиа снова разрешены"
    await callback.answer(text)
    await callback.message.edit_reply_markup(reply_markup=build_support_admin_keyboard(user_id))


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery):
    if not REQUIRED_CHANNEL:
        await callback.answer("Подписка не требуется", show_alert=True)
        return
    if await is_user_subscribed(callback.from_user.id):
        await callback.answer("Подписка подтверждена!", show_alert=True)
        await callback.message.answer(WELCOME_TEXT, reply_markup=get_main_keyboard())
    else:
        await callback.answer("Подписка не найдена. Проверьте, что подписаны на канал.", show_alert=True)


@dp.callback_query(F.data.startswith("support_full_"))
async def toggle_support_full(callback: types.CallbackQuery):
    if not ADMIN_ID or str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("У вас нет прав", show_alert=True)
        return

    user_id = int(callback.data.split("_")[-1])
    new_state = db.toggle_support_full_ban(user_id)
    text = "Пользователь заблокирован в поддержке" if new_state else "Пользователь снова может писать"
    await callback.answer(text)
    await callback.message.edit_reply_markup(reply_markup=build_support_admin_keyboard(user_id))

# ==================== Запуск бота ====================
async def main():
    logger.info("Запуск JoyGuard...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
