# service-whatsapp-parser/main.py

import os
import logging
from fastapi import FastAPI
from whatsapp_parser import capture_and_save_qr

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

    logger.info("Startup hook triggered — готовимся к захвату QR-кода")
    capture_and_save_qr(profile_path)
    logger.info("QR-код сохранён и запрошен для сканирования")

@app.get("/health/")
def health_check():
    return {"status": "ok"}
