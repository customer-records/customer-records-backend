const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const morgan = require("morgan");
const cors = require("cors");

const app = express();

// Логирование запросов
app.use(morgan("combined"));
app.use(cors());

// Эндпоинт статуса
app.get("/health", (req, res) => {
  res.status(200).json({ status: "OK" });
});

// Перенаправление запросов к сервису аутентификации
app.use(
  "/auth",
  createProxyMiddleware({
    target: "http://auth-dockm:3000",
    changeOrigin: true,
    pathRewrite: { "^/auth": "" },
    onError: (err, req, res) => {
      console.error("Auth service error:", err);
      res.status(502).json({ error: "Auth service unavailable" });
    },
  })
);

// Перенаправление запросов к сервису календаря
app.use(
  "/calendar",
  createProxyMiddleware({
    target: "http://calendar-dockm:8000",
    changeOrigin: true,
    pathRewrite: { "^/calendar": "" },
    onError: (err, req, res) => {
      console.error("Calendar service error:", err);
      res.status(502).json({ error: "Calendar service unavailable" });
    },
  })
);

// Перенаправление запросов к сервису telegram-code-sender
app.use(
  "/telegram",
  createProxyMiddleware({
    target: "http://telegram-code-sender-dockm:7000",
    changeOrigin: true,
    pathRewrite: { "^/telegram": "" },
    onError: (err, req, res) => {
      console.error("Telegram code sender error:", err);
      res.status(502).json({ error: "Telegram code sender unavailable" });
    },
  })
);

// Перенаправление запросов к сервису whatsapp-code-sender
app.use(
  "/whatsapp",
  createProxyMiddleware({
    target: "http://whatsapp-code-sender-dockm:7001",
    changeOrigin: true,
    pathRewrite: { "^/whatsapp": "" },
    onError: (err, req, res) => {
      console.error("WhatsApp code sender error:", err);
      res.status(502).json({ error: "WhatsApp code sender unavailable" });
    },
  })
);

// Перенаправление запросов к сервису telegram-bot
app.use(
  "/bot",
  createProxyMiddleware({
    target: "http://telegram-bot-dockm:5000",
    changeOrigin: true,
    pathRewrite: { "^/bot": "" },
    onError: (err, req, res) => {
      console.error("Telegram bot error:", err);
      res.status(502).json({ error: "Telegram bot service unavailable" });
    },
  })
);

// Обработка несуществующих маршрутов
app.use((req, res) => {
  res.status(404).json({ error: "Route not found" });
});

// Глобальная обработка ошибок
app.use((err, req, res, next) => {
  console.error("Gateway error:", err);
  res.status(500).json({ error: "Internal server error" });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`gateway-dockm запущен на порту ${PORT}`);
  console.log("Доступные маршруты:");
  console.log("- /auth/*      -> auth-dockm:3000");
  console.log("- /calendar/*  -> calendar-dockm:8000");
  console.log("- /telegram/*  -> telegram-code-sender-dockm:7000");
  console.log("- /whatsapp/*  -> whatsapp-code-sender-dockm:7001");
  console.log("- /bot/*       -> telegram-bot-dockm:5000");
});
