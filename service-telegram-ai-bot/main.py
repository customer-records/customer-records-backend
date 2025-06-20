import os
import uuid
import time
import logging
import requests
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ----------------------------
# Настройка логгера
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("telegram-ai-bot")

# ----------------------------
# Жёстко заданные креденшалы GigaChat
# ----------------------------
GIGACHAT_AUTH_KEY = "NjM2NDJmNDAtNTgyZi00YWJkLThhMDctZTc0YWZkN2NhMmE1OjU5ZjZjYzk2LTgyYjAtNDg5Yi05NTUzLTljNTY4NDUwZmIzNQ=="
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"

# Токен Telegram бота из окружения
TELEGRAM_BOT_TOKEN_AI = os.getenv("TELEGRAM_BOT_TOKEN_AI")
if not TELEGRAM_BOT_TOKEN_AI:
    logger.error("Переменная окружения TELEGRAM_BOT_TOKEN_AI не задана")

# ----------------------------
# Глобальные переменные для хранения access_token GigaChat
# ----------------------------
_current_token = None
_token_expires_at = 0  # UNIX-метка, когда токен истекает

def fetch_gigachat_access_token() -> str:
    global _current_token, _token_expires_at

    token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    rq_uuid = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": rq_uuid,
        "Authorization": f"Basic {GIGACHAT_AUTH_KEY}"
    }
    data = {"scope": GIGACHAT_SCOPE}

    try:
        resp = requests.post(token_url, headers=headers, data=data, timeout=10, verify=False)
        resp.raise_for_status()
    except Exception:
        logger.exception("Не удалось получить access_token от GigaChat:")
        return ""

    resp_json = resp.json()
    token = resp_json.get("access_token")
    expires_at = resp_json.get("expires_at", 0)

    if token:
        _current_token = token
        _token_expires_at = expires_at
        logger.info("Получили новый GigaChat token, expires_at=%s", expires_at)
        return token
    else:
        logger.error("Не удалось извлечь access_token из ответа GigaChat API")
        return ""

def get_valid_token() -> str:
    global _current_token, _token_expires_at

    now_ts = int(time.time())
    if _current_token and now_ts + 30 < _token_expires_at:
        return _current_token

    return fetch_gigachat_access_token()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Я виртуальный администратор стоматологической клиники Denta Rell."
    )

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    token = get_valid_token()
    if not token:
        await update.message.reply_text("Сервис временно недоступен (не удалось получить токен).")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "model": "GigaChat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты — виртуальный администратор стоматологической клиники Denta Rell (сайт: app.denta-rell.ru). "
                    "Отвечай только на вопросы, связанные с услугами, акциями, расписанием, специалистами и записью в клинику. "
                    "Запрещено отвечать на любые вопросы о себе, о своих технологиях, устройстве, происхождении, личности, компании Sber, GigaChat, Telegram или искусственном интеллекте. "
                    "Не упоминай слова 'я бот', 'я ИИ', 'я модель', 'я ассистент', 'GigaChat', 'искусственный интеллект' и всё подобное. "
                    "Если клиент задаёт вопрос не по теме стоматологии, услуг или записи — мягко перенаправь его, например: «Пожалуйста, уточните, чем мы можем помочь вам в рамках стоматологической клиники Denta Rell». "
                    "Твоя задача — помогать как администратор: кратко, профессионально, вежливо и только по теме. "
                    "В каждом подходящем случае предлагай записаться онлайн на сайте app.denta-rell.ru."
                )
            },
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 200
    }

    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as http_err:
        status = http_err.response.status_code
        if status in (401, 403):
            logger.info("Получен %s, пробуем обновить токен и повторить...", status)
            token = fetch_gigachat_access_token()
            if not token:
                await update.message.reply_text("Не удалось обновить токен GigaChat.")
                return
            headers["Authorization"] = f"Bearer {token}"
            try:
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    resp = await client.post(
                        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    resp.raise_for_status()
            except Exception:
                logger.exception("Повторный запрос к GigaChat тоже упал:")
                await update.message.reply_text("Ошибка при обращении к GigaChat.")
                return
        else:
            logger.exception("HTTP ошибка при обращении к GigaChat:")
            await update.message.reply_text("Ошибка при обращении к GigaChat.")
            return
    except Exception:
        logger.exception("Ошибка при обращении к GigaChat:")
        await update.message.reply_text("Ошибка при обращении к GigaChat.")
        return

    try:
        data = resp.json()
        choices = data.get("choices") or []
        if not choices or "message" not in choices[0]:
            raise ValueError("Неправильный формат ответа GigaChat")
        content = choices[0]["message"].get("content", "").strip()
        if not content:
            raise ValueError("Пустой результат от GigaChat")
        await update.message.reply_text(content)
    except Exception:
        logger.exception("Не удалось разобрать ответ от GigaChat:")
        await update.message.reply_text("Не удалось получить ответ от GigaChat.")

def main():
    if not TELEGRAM_BOT_TOKEN_AI:
        logger.error("Переменная окружения TELEGRAM_BOT_TOKEN_AI не задана")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN_AI).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_handler))

    logger.info("Telegram AI Bot с GigaChat запущен (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
