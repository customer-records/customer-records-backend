# service-whatsapp-parser/main.py

import os
import time
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
import shutil

from whatsapp_parser import send_story, capture_and_print_qr

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("whatsapp-parser")

app = FastAPI(title="WhatsApp Parser Service")

@app.on_event("startup")
def ensure_whatsapp_login():
    profile_path = os.path.abspath("./chrome-data")
    os.makedirs(profile_path, exist_ok=True)

    # Отладочный вывод, чтобы убедиться, что вызывается startup
    logger.info("Startup hook triggered — готовимся к захвату QR-кода")
    print("[DEBUG] Внутри ensure_whatsapp_login, profile_path =", profile_path)

    # Печатаем QR-CODE ASCII
    try:
        capture_and_print_qr(profile_path)
        logger.info("QR-код был выведен в консоль")
    except Exception as e:
        logger.error("Ошибка при выводе QR-кода: %s", e)

    print("[DEBUG] Завершили ensure_whatsapp_login — сервис продолжает запускать маршруты")

@app.post("/story/")
async def post_story(file: UploadFile = File(...)):
    temp_dir = "/tmp/whatsapp_parser"
    os.makedirs(temp_dir, exist_ok=True)
    saved_path = os.path.join(temp_dir, file.filename)
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        send_story(saved_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке истории: {e}")

    return {"detail": "История успешно отправлена"}

@app.get("/health/")
def health_check():
    return {"status": "ok"}
