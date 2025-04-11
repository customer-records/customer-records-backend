from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
import logging
import random
from typing import Dict, Tuple, Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

class TelegramBot:
    def __init__(self):
        self.TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        self._validate_token()
        self.bot = Bot(token=self.TOKEN)
        self.dp = Dispatcher()
        
        # Инициализация подключения к БД
        self.db_engine = create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
            f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
        )
        self.Session = sessionmaker(bind=self.db_engine)
        
        # Хранилище данных: 
        # {user_id: {"code": str, "phone": str, "username": str, "chat_id": int}}
        self.user_data: Dict[int, Dict[str, str]] = {}
        self.phone_requests = set()
        self.logger = self._setup_logging()
        
        # Регистрация обработчиков
        self.dp.message(CommandStart())(self._handle_start)
        self.dp.message(lambda m: m.contact)(self._handle_phone)

    def _validate_token(self):
        if not self.TOKEN or len(self.TOKEN) < 30:
            raise ValueError("Invalid Telegram bot token")

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _check_user_exists(self, tg_username: str) -> bool:
        """Проверяет существование пользователя в БД по tg_name"""
        with self.Session() as session:
            # Проверяем в таблицах users и clients
            query = text("""
                SELECT EXISTS(
                    SELECT 1 FROM users WHERE tg_name = :username
                    UNION
                    SELECT 1 FROM clients WHERE tg_name = :username
                )
            """)
            result = session.execute(query, {"username": tg_username}).scalar()
            return bool(result)

    def store_user_data(self, chat_id: int, phone: str, username: str, code: str):
        """Сохраняет данные пользователя"""
        self.user_data[chat_id] = {
            "code": code,
            "phone": phone,
            "username": username,
            "chat_id": chat_id
        }

    def get_user_info_by_code(self, code: str) -> Optional[Tuple[str, str, int]]:
        """Получает информацию о пользователе по коду"""
        for user_id, data in self.user_data.items():
            if data["code"] == code:
                return (data["phone"], data["username"], data["chat_id"])
        return None

    def clear_user_data_by_code(self, code: str) -> bool:
        """Очищает данные пользователя по коду"""
        for user_id, data in list(self.user_data.items()):
            if data["code"] == code:
                del self.user_data[user_id]
                return True
        return False

    def get_user_by_phone(self, phone: str) -> Optional[Dict[str, str]]:
        """Получает пользователя по номеру телефона"""
        for data in self.user_data.values():
            if data["phone"] == phone:
                return data
        return None

    def clear_user_data(self, chat_id: int) -> bool:
        """Очищает данные пользователя по chat_id"""
        if chat_id in self.user_data:
            del self.user_data[chat_id]
            return True
        return False

    async def _handle_start(self, message: types.Message):
        """Обработчик команды /start"""
        try:
            user_id = message.from_user.id
            tg_username = message.from_user.username
            
            if not tg_username:
                await message.answer(
                    "Для работы с ботом у вас должен быть установлен username в Telegram. "
                    "Пожалуйста, установите его в настройках Telegram и попробуйте снова."
                )
                return
            
            # Проверяем, зарегистрирован ли пользователь
            if self._check_user_exists(tg_username):
                await message.answer(
                    "Вы уже зарегистрированы в системе. "
                    "Коды подтверждения будут приходить автоматически при необходимости."
                )
                return
                
            # Новый пользователь - просим номер телефона
            self.logger.info(f"New user started: {tg_username}")
            await self._request_phone_number(message)

        except Exception as e:
            self.logger.error(f"Start handler error: {e}", exc_info=True)
            await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

    async def _request_phone_number(self, message: types.Message):
        """Запрашивает номер телефона у нового пользователя"""
        request_contact = KeyboardButton(
            text="📱 Отправить номер телефона",
            request_contact=True
        )
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[request_contact]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await message.answer(
            "Добро пожаловать! Для регистрации нам нужен ваш номер телефона:",
            reply_markup=keyboard
        )
        self.phone_requests.add(message.from_user.id)

    async def _handle_phone(self, message: types.Message):
        """Обработчик отправки номера телефона"""
        try:
            user_id = message.from_user.id
            if user_id not in self.phone_requests:
                return await message.answer("Пожалуйста, сначала нажмите /start")

            phone_number = message.contact.phone_number
            if not phone_number:
                raise ValueError("Phone number not provided")

            tg_username = message.from_user.username
            
            # Сохраняем информацию о пользователе
            code = str(random.randint(1000, 9999))
            self.store_user_data(
                chat_id=user_id,
                phone=phone_number,
                username=tg_username,
                code=code
            )
            
            await message.answer(
                f"✅ Спасибо! Ваш номер {phone_number} принят.\n\n"
                f"🔐 Ваш код подтверждения: <b>{code}</b>\n\n"
                "Используйте этот код для входа в систему.\n"
                "⚠️ Никому не сообщайте этот код!",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )

            self.phone_requests.discard(user_id)

        except Exception as e:
            self.logger.error(f"Phone handler error: {e}", exc_info=True)
            await message.answer("Ошибка при обработке номера. Пожалуйста, попробуйте /start")

    async def start(self):
        """Запуск бота"""
        try:
            self.logger.info("Starting bot...")
            bot_info = await self.bot.get_me()
            self.logger.info(f"Bot @{bot_info.username} ready!")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            self.logger.critical(f"Bot failed to start: {e}", exc_info=True)
            raise
        finally:
            await self._shutdown()

    async def _shutdown(self):
        """Корректное завершение работы"""
        if hasattr(self, 'bot') and self.bot:
            await self.bot.session.close()
            self.db_engine.dispose()
            self.logger.info("Bot and DB connections closed")