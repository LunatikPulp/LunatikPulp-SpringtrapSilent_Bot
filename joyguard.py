import logging
import asyncio
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN") or 
# ID администратора для тех.поддержки
ADMIN_ID = os.getenv("ADMIN_ID") or 

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

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
        
        # Таблица для антиспама (время последнего сообщения)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS last_support_time (
                user_id INTEGER PRIMARY KEY,
                last_message_time INTEGER NOT NULL
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

# ==================== Обработчики команд ====================

@dp.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added(event: types.ChatMemberUpdated):
    """Обработчик добавления бота в группу"""
    await event.answer(
        "👋 Спасибо за добавление SpringtrapSilent!\n\n"
        "📝 Доступные команды:\n"
        "• Ответьте на сообщение пользователя командой 'Спринг стоп' для блокировки\n"
        "• 'Спринг стоп' + текст для установки персонального автоответчика\n"
        "• 'Спринг список' для просмотра блокировок в чате\n\n"
        "⚠️ ВАЖНО: Сделайте бота администратором с правом удаления сообщений!\n\n"
        "💬 Напишите мне в личку для настройки глобального автоответчика."
    )

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    if message.chat.type == "private":
        await message.answer(
            "👋 Добро пожаловать в SpringtrapSilent!\n\n"
            "Здесь вы можете настроить свой глобальный автоответчик при персональном муте пользователя "
            "(он будет использоваться, если вы не указали персональный) ",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "👋 SpringtrapSilent активен!\n\n"
            "📝 Команды:\n"
            "• Ответьте на сообщение пользователя командой 'Спринг стоп' для блокировки\n"
            "• 'Спринг стоп' + текст для установки персонального автоответчика\n"
            "• 'Спринг список' для просмотра блокировок в чате\n\n"
            "⚠️ Бот должен быть администратором с правом удаления сообщений!"
        )

@dp.message(F.text.lower().startswith("спринг список"))
async def cmd_list(message: types.Message):
    """Команда 'Спринг список' - показать все блокировки в чате"""
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в групповых чатах.")
        return
    
    blocks = db.get_chat_blocks(message.chat.id)
    
    if not blocks:
        await message.answer("📋 В этом чате нет активных блокировок.")
        return
    
    # Группируем блокировки по блокирующему
    blocks_dict = {}
    for blocker_id, blocked_id in blocks:
        if blocker_id not in blocks_dict:
            blocks_dict[blocker_id] = []
        blocks_dict[blocker_id].append(blocked_id)
    
    # Формируем сообщение
    text = "📋 Список персональных блокировок в этом чате:\n\n"
    
    for blocker_id, blocked_list in blocks_dict.items():
        try:
            blocker = await bot.get_chat_member(message.chat.id, blocker_id)
            blocker_name = blocker.user.first_name
            
            blocked_names = []
            for blocked_id in blocked_list:
                try:
                    blocked = await bot.get_chat_member(message.chat.id, blocked_id)
                    blocked_names.append(blocked.user.first_name)
                except:
                    blocked_names.append(f"ID{blocked_id}")
            
            text += f"• Пользователь {blocker_name} заблокировал(а) ответы от: {', '.join(blocked_names)}.\n"
        except:
            text += f"• Пользователь ID{blocker_id} заблокировал некоторых пользователей.\n"
    
    await message.answer(text)

@dp.message(F.text.lower().startswith("спринг стоп"))
async def cmd_joy_stop(message: types.Message):
    """Команда 'Спринг стоп' - блокировка/разблокировка"""
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в групповых чатах.")
        return
    
    # Проверяем, что это ответ на сообщение
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя, которого хотите заблокировать/разблокировать.")
        return
    
    blocker_id = message.from_user.id
    blocked_id = message.reply_to_message.from_user.id
    
    # Нельзя заблокировать самого себя
    if blocker_id == blocked_id:
        await message.answer("❌ Вы не можете заблокировать самого себя.")
        return
    
    # Проверяем, есть ли персональное сообщение
    text = message.text.strip()
    lines = text.split('\n')
    
    personal_message = None
    if len(lines) > 1:
        # Есть персональное сообщение
        personal_message = '\n'.join(lines[1:]).strip()
    
    # Переключаем блокировку
    is_blocked = db.toggle_block(
        message.chat.id,
        blocker_id,
        blocked_id,
        personal_message
    )
    
    blocker_name = message.from_user.first_name
    blocked_name = message.reply_to_message.from_user.first_name
    
    if is_blocked:
        if personal_message:
            response = f"🔒 {blocker_name} запретил(а) пользователю {blocked_name} отвечать на свои сообщения и установил(а) персональный автоответчик."
        else:
            response = f"🔒 {blocker_name} запретил(а) пользователю {blocked_name} отвечать на свои сообщения."
    else:
        response = f"🔓 {blocker_name} разрешил(а) пользователю {blocked_name} снова отвечать на свои сообщения."
    
    await message.answer(response)

@dp.message(F.reply_to_message)
async def check_reply_block(message: types.Message):
    """Проверка всех ответов на заблокированность"""
    if message.chat.type == "private":
        return
    
    replier_id = message.from_user.id
    original_author_id = message.reply_to_message.from_user.id
    
    # Проверяем, заблокирован ли ответ
    is_blocked, personal_message = db.is_blocked(
        message.chat.id,
        original_author_id,
        replier_id
    )
    
    if is_blocked:
        try:
            # Удаляем сообщение заблокированного пользователя
            await message.delete()
            
            # Получаем автоответчик
            if personal_message:
                autoresponder = personal_message
            else:
                autoresponder = db.get_global_autoresponder(original_author_id)
                if not autoresponder:
                    autoresponder = "Пользователь установил ограничение на ответы к своим сообщениям."
            
            # Отправляем временное сообщение
            replier_mention = message.from_user.mention_html()
            original_author_name = message.reply_to_message.from_user.first_name
            
            temp_message = await message.answer(
                f"{replier_mention}, {original_author_name} установил(а) для вас следующий ответ:\n\n"
                f"\"{autoresponder}\"",
                parse_mode="HTML"
            )
            
            # Удаляем временное сообщение через 12 секунд
            await asyncio.sleep(12)
            await temp_message.delete()
            
        except Exception as e:
            logger.error(f"Ошибка при обработке заблокированного ответа: {e}")
            # Если не удалось удалить, отправляем предупреждение админам
            await message.answer(
                "⚠️ Не удалось удалить сообщение. Убедитесь, что бот является администратором с правом удаления сообщений."
            )

# ==================== Обработчики для личных сообщений ====================

@dp.message(F.text == "✍️ Глобальный автоответчик")
async def global_autoresponder_menu(message: types.Message, state: FSMContext):
    """Меню глобального автоответчика"""
    if message.chat.type != "private":
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
    
    # Очищаем любое предыдущее состояние
    await state.clear()
    
    await message.answer(
        "👨‍🔧 Тех.поддержка\n\n"
        "Опишите вашу проблему или вопрос, и я передам его администраторам.\n\n"
        "Отправьте /cancel для отмены."
    )
    await state.set_state(BotStates.waiting_support_message)

@dp.message(BotStates.waiting_support_message)
async def save_support_message(message: types.Message, state: FSMContext):
    """Сохранение сообщения в тех.поддержку"""
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
    db.save_support_message(message.from_user.id, message.text)
    
    # Отправляем администратору, если ID указан
    if ADMIN_ID:
        try:
            admin_id = int(ADMIN_ID)
            user_info = f"От: {message.from_user.first_name}"
            if message.from_user.username:
                user_info += f" (@{message.from_user.username})"
            user_info += f"\nID: {message.from_user.id}"
            
            # Создаем кнопку "Ответить"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_{message.from_user.id}")]
            ])
            
            await bot.send_message(
                admin_id,
                f"📩 Новое сообщение в тех.поддержку:\n\n"
                f"{user_info}\n\n"
                f"Сообщение:\n{message.text}",
                reply_markup=keyboard
            )
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
    
    # Очищаем состояние при переходе в помощь
    await state.clear()
    
    await message.answer(
        "❓ Помощь по JoyGuard\n\n"
        "📝 Команды в групповых чатах:\n\n"
        "1️⃣ Спринг стоп\n"
        "Ответьте на сообщение пользователя этой командой, чтобы заблокировать/разблокировать ему возможность отвечать на ваши сообщения.\n\n"
        "2️⃣ Спринг стоп + текст\n"
        "Напишите команду 'Спринг стоп' и с новой строки ваш текст автоответчика. "
        "Этот текст будет показываться заблокированному пользователю при попытке ответить вам.\n\n"
        "3️⃣ Спринг список\n"
        "Показывает список всех блокировок в текущем чате.\n\n"
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
        # Отправляем ответ пользователю
        await bot.send_message(
            user_id,
            f"💬 Ответ от администратора:\n\n{message.text}"
        )
        
        await message.answer(
            f"✅ Ответ отправлен пользователю {user_id}!\n\n"
            f"Текст ответа:\n{message.text}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()

# ==================== Запуск бота ====================
async def main():
    logger.info("Запуск JoyGuard...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
