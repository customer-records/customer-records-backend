import os
from dotenv import load_dotenv
from telegram import Bot

# Загружаем переменные из .env
load_dotenv()

# # Токен бота и ID чата
# TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
# CHAT_ID = os.getenv('CHAT_ID')

# # Функция для отправки уведомления
# def send_notification(message: str) -> None:
#     bot = Bot(token=TELEGRAM_TOKEN)
#     bot.send_message(chat_id=CHAT_ID, text=message)

# Основная функция
if __name__ == '__main__':
    # send_notification("Микросервис телеграм-бота запущен!")
    print("Уведомление отправлено.")