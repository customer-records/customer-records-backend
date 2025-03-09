import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Загружаем переменные из .env
load_dotenv()

# Функция для парсинга
def parse_website(url: str) -> str:
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.title.string  # Пример: возвращаем заголовок страницы

# Основная функция
if __name__ == '__main__':
    url = "https://example.com"  # Замените на URL для парсинга
    title = parse_website(url)
    print(f"Заголовок страницы: {title}")