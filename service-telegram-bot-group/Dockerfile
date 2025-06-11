FROM python:3.10-slim

# 1) Устанавливаем tzdata для zoneinfo
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Копируем приложение
COPY . .

# 4) Экспонируем порт
EXPOSE 8020

# 5) Запускаем сервер
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
