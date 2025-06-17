FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y wget gnupg2 unzip xvfb libnss3 libgconf-2-4 libxi6 libxss1 libglib2.0-0 libgtk-3-0 \
                       chromium chromium-driver && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости и ставим
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код и статические файлы
COPY . .
# Копируем заранее подготовленную картинку истории
COPY story.JPEG /app/story.JPEG

# Создаём папку для профиля Chrome
RUN mkdir -p /app/chrome-data

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
