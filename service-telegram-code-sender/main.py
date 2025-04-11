from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
from telegram_client import TelegramBot
import asyncio
import logging
import random
import os
from typing import Optional, Dict, Tuple

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Настройка базы данных
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
logger.info(f"Подключение к базе данных по URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация бота
bot = TelegramBot()

@app.on_event("startup")
async def startup():
    """Запуск бота при старте сервиса"""
    asyncio.create_task(bot.start())
    logger.info("Service started")

@app.get("/health")
async def health():
    """Проверка работоспособности"""
    return {"status": "ok", "bot": "running"}

@app.get("/verify-code/{code}")
async def verify_code(code: str):
    """
    Проверка кода и получение номера телефона
    Возвращает номер телефона, username и chat_id если код действителен
    """
    result = bot.get_user_info_by_code(code)
    if not result:
        raise HTTPException(status_code=404, detail="Code not found or expired")
    
    phone, username, chat_id = result
    return {
        "status": "success",
        "phone": phone,
        "username": username,
        "chat_id": chat_id,
        "code": code
    }

@app.post("/clear-code/{code}")
async def clear_code(code: str):
    """
    Очистка использованного кода и связанных данных пользователя
    Возвращает успешный статус, если код был найден и удален
    """
    if not bot.clear_user_data_by_code(code):
        raise HTTPException(status_code=404, detail="Code not found")
    
    return {
        "status": "success",
        "message": "Code and user data cleared"
    }

@app.post("/send_code/user/{phone_number}")
async def send_code_to_user(phone_number: str):
    """
    Отправка кода подтверждения клиенту (из таблицы Users)
    по номеру телефона через Telegram
    """
    try:
        db = SessionLocal()
        
        # Нормализация номера телефона
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        # Правильный запрос с использованием text()
        query = text("""
            SELECT chat_id, tg_name 
            FROM users 
            WHERE phone_number = :phone 
            OR phone_number LIKE :clean_phone
        """)
        
        # Ищем клиента по номеру телефона
        user = db.execute(
            query,
            {"phone": phone_number, "clean_phone": f"%{clean_phone[-10:]}"}
        ).fetchone()
        
        if not user or not user.chat_id:
            raise HTTPException(
                status_code=404,
                detail="user not found or has no linked Telegram account"
            )
        
        # Генерируем и отправляем код
        code = str(random.randint(1000, 9999))
        bot.store_user_data(
            chat_id=user.chat_id,
            phone=clean_phone,
            username=user.tg_name,
            code=code
        )
        
        await bot.bot.send_message(
            chat_id=user.chat_id,
            text=f"🔐 Ваш код подтверждения: <b>{code}</b>\n\n"
                 "Используйте этот код для входа в систему.\n"
                 "⚠️ Никому не сообщайте этот код!",
            parse_mode="HTML"
        )
        
        return {
            "status": "success",
            "message": "Code sent to user's Telegram",
            "phone": clean_phone,
            "username": user.tg_name,
            "chat_id": user.chat_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send code to user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while sending code"
        )
    finally:
        db.close()

@app.post("/send_code/client/{phone_number}")
async def send_code_to_client(phone_number: str):
    """
    Отправка кода подтверждения клиенту (из таблицы clients)
    по номеру телефона через Telegram
    """
    try:
        db = SessionLocal()
        
        # Нормализация номера телефона
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        # Правильный запрос с использованием text()
        query = text("""
            SELECT chat_id, tg_name 
            FROM clients 
            WHERE phone_number = :phone 
            OR phone_number LIKE :clean_phone
        """)
        
        # Ищем клиента по номеру телефона
        client = db.execute(
            query,
            {"phone": phone_number, "clean_phone": f"%{clean_phone[-10:]}"}
        ).fetchone()
        
        if not client or not client.chat_id:
            raise HTTPException(
                status_code=404,
                detail="Client not found or has no linked Telegram account"
            )
        
        # Генерируем и отправляем код
        code = str(random.randint(1000, 9999))
        bot.store_user_data(
            chat_id=client.chat_id,
            phone=clean_phone,
            username=client.tg_name,
            code=code
        )
        
        await bot.bot.send_message(
            chat_id=client.chat_id,
            text=f"🔐 Ваш код подтверждения: <b>{code}</b>\n\n"
                 "Используйте этот код для входа в систему.\n"
                 "⚠️ Никому не сообщайте этот код!",
            parse_mode="HTML"
        )
        
        return {
            "status": "success",
            "message": "Code sent to client's Telegram",
            "phone": clean_phone,
            "username": client.tg_name,
            "chat_id": client.chat_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send code to client: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while sending code"
        )
    finally:
        db.close()