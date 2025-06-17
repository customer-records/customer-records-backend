# service-whatsapp-parser/whatsapp_parser.py

import os
import base64
import logging
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Пути к установленным через apt
CHROMEDRIVER_PATH = "/usr/bin/chromedriver"
CHROME_BINARY_PATH = "/usr/bin/chromium"

logger = logging.getLogger("whatsapp-parser")

def capture_and_save_qr(profile_path: str):
    """
    Открывает WhatsApp Web в headless, ждёт появления QR-кода,
    сохраняет его в файл и логирует путь.
    """
    logger.info("Запуск ChromeDriver для захвата QR-кода...")
    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument(f"--user-data-dir={profile_path}")

    try:
        service = ChromeService(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        logger.error("Не удалось запустить ChromeDriver: %s", e)
        return

    try:
        logger.info("Открываем WhatsApp Web...")
        driver.get("https://web.whatsapp.com/")

        logger.info("Ждём появления QR-канвеса...")
        qr_canvas = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "canvas[aria-label='Scan this QR code to link a device!']")
            )
        )

        logger.info("Canvas найден, снимаем скриншот QR-кода...")
        qr_base64 = qr_canvas.screenshot_as_base64

        # декодируем и сохраняем в файл
        qr_data = base64.b64decode(qr_base64)
        qr_path = os.path.join(profile_path, "qr.png")
        with open(qr_path, "wb") as f:
            f.write(qr_data)

        logger.info("QR-код сохранён в файл: %s", qr_path)
        logger.info("Скопируйте и отсканируйте этот файл на телефоне для авторизации.")

    except Exception as e:
        logger.error("Ошибка при захвате или сохранении QR-кода: %s", e)

    finally:
        driver.quit()
        logger.info("ChromeDriver завершил работу.")

def send_story(image_path: str, profile_path: str = "./chrome-data"):
    """
    Публикует историю (статус) в WhatsApp Web, используя сохранённую сессию.
    """
    if not os.path.exists(image_path):
        logger.error("Файл для истории не найден: %s", image_path)
        return

    logger.info("Запуск ChromeDriver для публикации истории...")
    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_BINARY_PATH
    options.add_argument(f"--user-data-dir={profile_path}")

    try:
        service = ChromeService(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)

        logger.info("Открываем WhatsApp Web с сессией...")
        driver.get("https://web.whatsapp.com/")
        WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-tab='2']"))
        )

        logger.info("Кликаем 'Статус' и готовимся к публикации...")
        driver.find_element(By.CSS_SELECTOR, "button[data-tab='2']").click()
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "div[role='button'][tabindex='-1'] > div[role='button'][tabindex='-1']"
            ))
        ).click()

        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-icon='plus']"))
        ).click()

        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-icon='media-multiple']"))
        ).click()

        logger.info("Загружаем файл: %s", image_path)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        ).send_keys(os.path.abspath(image_path))

        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span[data-icon='send']"))
        ).click()

        logger.info("История успешно отправлена!")
    except Exception as e:
        logger.error("Ошибка при публикации истории: %s", e)
    finally:
        driver.quit()
        logger.info("ChromeDriver закрыт после публикации.")
