# service-whatsapp-parser/Dockerfile

FROM python:3.9-slim

RUN apt-get update && \
    apt-get install -y wget gnupg2 unzip xvfb libnss3 libgconf-2-4 libxi6 libxss1 libglib2.0-0 libgtk-3-0 \
                       chromium chromium-driver && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/chrome-data

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
