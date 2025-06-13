import os
import logging
import asyncio
from fastapi import FastAPI
from telegram import Bot, MessageEntity
from telegram.error import TelegramError, Conflict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
)
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# 1) Загрузка .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_GROUP")
if not BOT_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN_GROUP в .env")

# 2) Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 3) Инициализация бота и FastAPI
bot = Bot(token=BOT_TOKEN)
app = FastAPI()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
TARGET_CHAT_ID = None

async def mention_listener():
    """
    Фоновый polling: ловим упоминание @botusername, определяем chat_id и шлем привет.
    """
    global TARGET_CHAT_ID
    offset = None
    me = await bot.get_me()
    username = me.username.lower()

    while TARGET_CHAT_ID is None:
        try:
            updates = await bot.get_updates(
                offset=offset, timeout=5, allowed_updates=["message"]
            )
            for upd in updates:
                offset = upd.update_id + 1
                msg = upd.message
                if not msg or not msg.entities:
                    continue
                for ent in msg.entities:
                    if ent.type == MessageEntity.MENTION:
                        mention = msg.parse_entity(ent).lstrip("@").lower()
                        if mention == username:
                            TARGET_CHAT_ID = msg.chat.id
                            logger.info("Определён chat_id через упоминание: %s", TARGET_CHAT_ID)
                            # Приветственное сообщение
                            await bot.send_message(
                                chat_id=TARGET_CHAT_ID,
                                text=(
                                    "Привет! Спасибо за упоминание. "
                                    "Я буду напоминать вам каждый день в 18:00 МСК."
                                )
                            )
                            logger.info("Приветственное сообщение отправлено в %s", TARGET_CHAT_ID)
                            break
            if offset is not None:
                await bot.get_updates(offset=offset)
        except Conflict:
            logger.warning("Conflict polling — повтор через секунду")
        except Exception as e:
            logger.error("Ошибка в mention_listener: %s", e)
        await asyncio.sleep(1)

async def send_daily_message():
    """
    Рассылка сообщений в 18:00 МСК в зависимости от дня недели.
    """
    global TARGET_CHAT_ID
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    logger.info("send_daily_message запущен в %s", now.strftime("%Y-%m-%d %H:%M:%S %Z"))
    if not TARGET_CHAT_ID:
        logger.warning("chat_id не определён — рассылка пропущена")
        return

    weekday = now.weekday()  # 0=Понедельник ... 6=Воскресенье
    texts = {
        0: "🌙 Всем добрый вечер!\n\n"
           "Сегодня у нас соревнование с кальянщиком 🪕✨. Кто окажется победителем в UFC или MK11, "
           "тот получит скидку 50% на следующий кальян! 🎉\n\n"
           "Приглашаем всех провести этот вечер в уютной атмосфере и с отличным настроением и вкусным кальяном😊.",
        1: "Доброго вечера!\n\n"
           "🎵 Приглашаем вас провести приятный вечер в уютной атмосфере под спокойную музыку. 🍃 "
           "Для вашего удовольствия мы приготовим самый вкусный кальян.\n\n🙂 Ждем вас!",
        2: "Всем добрый вечер! 🌙\n\n"
           "Приглашаем вас насладиться китайскими чаями в нашей уютной атмосфере. 🏮 "
           "В ассортименте представлены такие сорта, как молочный улун, да хун пао, пуэр и те гуань инь. 🍵\n\n"
           "🎉 Сегодня действует скидка 25% на весь чайный ассортимент! 💰\n\n"
           "Приходите провести вечер в спокойной, расслабляющей обстановке при просмотре фильма "
           "с чашечкой ароматного чая🫖 и приятным кальяном. 🪕",
        3: "🌿 Уважаемые гости, добрый вечер! 🌙\n\n"
           "Попробуйте свежие вкусы или создайте уникальные миксы, чтобы расширить границы "
           "своего табачного опыта. 🧉 Мы уверены, что вы найдете что-то особенное среди наших новинок. "
           "До встречи! ✨\n\nА так же ждём всех на кино вечер ☺️",
        4: "🌙 Всем добрый вечер!\n\n"
           "🎶 Ждем вас, чтобы провести этот вечер под приятную музыку и вкусный кальян. 🪕 "
           "А при заказе кальяна — шот в подарок! 🍸\n\n✨ Всем хороших выходных! ✨",
        5: "Всем добрый вечер! 🌙\n\n"
           "Ждём всех в этот прекрасный выходной, чтобы провести вечер в приятной атмосфере под хорошую музыку 🎶\n\n"
           "🔥 Акция дня:\n"
           "— Кто закажет сегодня кальян — шот в подарок! 🎁\n"
           "— А для тех, кто не пьёт или хочет отдохнуть от алкоголя — чай в подарок 🍵\n\nДо встречи! 👋",
        6: "Добрый вечер ! 🌞\n"
           "Сегодня мы рады предложить вам скидку 35% на чай Те Гуань Инь. Этот сорт чая "
           "прекрасно помогает расслабиться и насладиться моментом спокойствия. 🍵🧘‍♂️\n"
           "Приглашаем всех провести вечер в уютной атмосфере, наслаждаясь вкусом чая и кальяна. 🪔"
    }
    text = texts.get(weekday)
    try:
        await bot.send_message(chat_id=TARGET_CHAT_ID, text=text)
        logger.info("Ежедневное сообщение отправлено в %s", TARGET_CHAT_ID)
    except TelegramError as e:
        logger.error("Ошибка при отправке рассылки: %s", e)

def job_listener(event):
    job_id = event.job_id
    if event.code == EVENT_JOB_ADDED:
        logger.info("Задача добавлена в планировщик: %s", job_id)
    elif event.code == EVENT_JOB_EXECUTED:
        logger.info("Задача успешно выполнена: %s", job_id)
    elif event.code == EVENT_JOB_ERROR:
        logger.error(
            "Задача %s завершилась с ошибкой: %s",
            job_id,
            getattr(event, 'exception', 'Неизвестная ошибка')
        )

@app.on_event("startup")
async def on_startup():
    # Время старта сервиса
    startup_time = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S %Z")
    logger.info("Сервис запущен в %s", startup_time)

    # Запускаем упоминания
    asyncio.create_task(mention_listener())
    logger.info("mention_listener запущен")

    # Добавляем слушатель событий APScheduler
    scheduler.add_listener(
        job_listener,
        EVENT_JOB_ADDED | EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
    )

    # Планируем ежедневную рассылку в 18:00 МСК
    job = scheduler.add_job(
        send_daily_message,
        trigger="cron",
        hour=18,
        minute=0,
        id="daily_18_00"
    )
    logger.info(
        "Запланирована ежедневная рассылка (job_id=%s) — каждый день в 18:00 МСК", 
        job.id
    )

    scheduler.start()
    logger.info("Планировщик запущен")

@app.get("/")
async def health_check():
    return {
        "status": "running",
        "chat_id": TARGET_CHAT_ID,
        "time": datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S %Z")
    }
