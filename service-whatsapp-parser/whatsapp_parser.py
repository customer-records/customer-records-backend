# service-whatsapp-parser/whatsapp_parser.py

import os
import time
import base64
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image

# Пути к установленным через apt
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
CHROME_BINARY_PATH = "/usr/bin/chromium"


def _generate_qr_ascii(qr_base64: str) -> str:
    """
    Декодирует Base64-изображение QR и возвращает его в виде ASCII-art (строка).
    """
    qr_data = base64.b64decode(qr_base64)
    img = Image.open(BytesIO(qr_data)).convert("L")
    width, height = img.size
    new_width = 40
    new_height = int((height / width) * new_width / 2)
    img = img.resize((new_width, new_height))
    img = img.point(lambda x: 0 if x < 128 else 255, '1')

    pixels = img.load()
    lines = []
    for y in range(new_height):
        line = ""
        for x in range(new_width):
            line += "██" if pixels[x, y] == 0 else "  "
        lines.append(line)
    return "\n".join(lines)


def capture_and_print_qr(profile_path: str):
    """
    Открывает WhatsApp Web в headless, ждёт появления QR-кода,
    затем печатает его в консоль как ASCII-art (print, а не logger).
    Добавлены отладочные принты и более точный селектор canvas.
    """
    print("[DEBUG] Запуск ChromeDriver для захвата QR-кода...")
    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    options.add_argument(f"--user-data-dir={profile_path}")

    try:
        service = ChromeService(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"[ERROR] Не удалось запустить ChromeDriver: {e}")
        return

    print("[DEBUG] Открываем страницу WhatsApp Web...")
    try:
        driver.get("https://web.whatsapp.com/")
    except Exception as e:
        print(f"[ERROR] Ошибка при переходе на WhatsApp Web: {e}")
        driver.quit()
        return

    print("[DEBUG] Ждём появления элемента <canvas> с aria-label='Scan this QR code to link a device!' ...")
    try:
        qr_canvas = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "canvas[aria-label='Scan this QR code to link a device!']")
            )
        )
    except Exception as e:
        print(f"[ERROR] Элемент <canvas> с QR не найден: {e}")
        driver.quit()
        return

    print("[DEBUG] Элемент <canvas> найден, снимаем скриншот...")
    try:
        qr_base64 = qr_canvas.screenshot_as_base64
    except Exception as e:
        print(f"[ERROR] Не удалось получить Base64 из <canvas>: {e}")
        driver.quit()
        return

    driver.quit()
    print("[DEBUG] Закрыли браузер после захвата QR-кода.")

    ascii_qr = _generate_qr_ascii(qr_base64)
    # Печатаем ASCII-QR напрямую в stdout, чтобы ведущие пробелы сохранились
    print("\n=== Сканируйте QR-код ниже (ASCII) ===\n")
    print(ascii_qr)
    print("\n=== Конец QR-кода ===\n")
