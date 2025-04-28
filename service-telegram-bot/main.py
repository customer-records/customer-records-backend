import os
import json
from dotenv import load_dotenv
from telegram import Bot
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn
from multiprocessing import Process, Manager
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_INFO")
bot = Bot(token=BOT_TOKEN)

# Используем менеджер процессов для разделяемой памяти
manager = Manager()
users_db = manager.dict()  # Теперь словарь доступен между процессами

def run_bot():
    """Запуск Telegram бота в отдельном процессе"""
    from telegram.ext import Updater, CommandHandler
    
    updater = Updater(BOT_TOKEN, use_context=True)
    
    def start(update, context):
        user = update.effective_user
        users_db[update.message.chat_id] = {
            'username': user.username or "Unknown",
            'chat_id': update.message.chat_id
        }
        update.message.reply_text(
            "🤖 Бот готов к работе!\n"
            "Я буду отправлять вам уведомления о новых записях клиентов.\n"
            f"Ваш chat_id: {update.message.chat_id}"
        )
        print(f"New subscriber: {update.message.chat_id}")  # Логирование
    
    updater.dispatcher.add_handler(CommandHandler("start", start))
    print("Telegram бот запущен...")
    updater.start_polling()
    updater.idle()

@app.post("/send-appointment")
async def send_notification(request: Request):
    try:
        body = await request.body()
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format")
        
        # Проверяем наличие всех необходимых полей
        required_fields = {
            'client_name', 
            'phone', 
            'appointment_date',
            'appointment_time',
            'service_name',
            'specialist_name'
        }
        
        if not required_fields.issubset(data.keys()):
            missing = required_fields - set(data.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing)}"
            )
        
        if not users_db:
            print("No subscribers in users_db:", dict(users_db))
            return JSONResponse(
                content={"status": "No active subscribers"},
                status_code=200
            )
        
        success_count = 0
        for chat_id, user_data in users_db.items():
            try:
                # Форматируем дату и время
                appointment_datetime = f"{data['appointment_date']} {data['appointment_time']}"
                try:
                    dt = datetime.strptime(appointment_datetime, "%Y-%m-%d %H:%M")
                    formatted_datetime = dt.strftime("%d.%m.%Y в %H:%M")
                except ValueError:
                    formatted_datetime = appointment_datetime
                
                # Формируем информативное сообщение
                message = (
                    "📅 *Новая запись в клинике*\n\n"
                    f"👤 *Клиент:* {data['client_name']}\n"
                    f"📞 *Телефон:* {data['phone']}\n"
                    f"⏰ *Дата и время:* {formatted_datetime}\n"
                    f"🏥 *Услуга:* {data['service_name']}\n"
                    f"👨‍⚕️ *Специалист:* {data['specialist_name']}\n\n"
                    "_Уведомление создано автоматически_"
                )
                
                bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown"
                )
                success_count += 1
                print(f"Sent to {chat_id} ({user_data['username']})")
            except Exception as e:
                print(f"Ошибка отправки для chat_id {chat_id}: {str(e)}")
        
        return JSONResponse(
            content={
                "status": "success",
                "notifications_sent": success_count,
                "total_subscribers": len(users_db)
            },
            status_code=200
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == '__main__':
    bot_process = Process(target=run_bot)
    bot_process.start()
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=5000,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\nОстановка сервера...")
        bot_process.terminate()
        bot_process.join()