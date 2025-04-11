FROM node:18-slim

# Установка зависимостей для Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Установка последней версии Chromium
RUN apt-get update && apt-get install -y chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

EXPOSE 7001
CMD ["node", "index.js"]