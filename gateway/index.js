const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const morgan = require("morgan");
const cors = require("cors");

const app = express();

// Логирование запросов и CORS
app.use(morgan("combined"));
app.use(cors());

// Эндпоинт статуса сервиса
app.get("/health", (req, res) => {
  res.status(200).json({ status: "OK" });
});

// Проксирование на сервис аутентификации (auth_psy)
app.use(
  "/auth",
  createProxyMiddleware({
    target: "http://auth_psy:3000",
    changeOrigin: true,
    pathRewrite: { "^/auth": "" },
    onError: (err, req, res) => {
      console.error("Auth service error:", err);
      res.status(502).json({ error: "Auth service unavailable" });
    },
  })
);

// Проксирование на сервис календаря (calendar_psy)
app.use(
  "/calendar",
  createProxyMiddleware({
    target: "http://calendar_psy:8000",
    changeOrigin: true,
    pathRewrite: { "^/calendar": "" },
    onError: (err, req, res) => {
      console.error("Calendar service error:", err);
      res.status(502).json({ error: "Calendar service unavailable" });
    },
  })
);

// Проксирование на Telegram Code Sender (telegram-code-sender-psy)
app.use(
  "/telegram",
  createProxyMiddleware({
    target: "http://telegram-code-sender-psy:7000",
    changeOrigin: true,
    pathRewrite: { "^/telegram": "" },
    onError: (err, req, res) => {
      console.error("Telegram code sender error:", err);
      res.status(502).json({ error: "Telegram code sender unavailable" });
    },
  })
);

// Проксирование на WhatsApp Code Sender (whatsapp-code-sender-psy)
app.use(
  "/whatsapp",
  createProxyMiddleware({
    target: "http://whatsapp-code-sender-psy:7001",
    changeOrigin: true,
    pathRewrite: { "^/whatsapp": "" },
    onError: (err, req, res) => {
      console.error("WhatsApp code sender error:", err);
      res.status(502).json({ error: "WhatsApp code sender unavailable" });
    },
  })
);

// Проксирование на Telegram Bot (telegram-bot-psy)
app.use(
  "/bot",
  createProxyMiddleware({
    target: "http://telegram-bot-psy:5000",
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
  console.error("Gateway_psy error:", err);
  res.status(500).json({ error: "Internal server error" });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`Gateway_psy запущен на порту ${PORT}`);
  console.log("Маршруты:");
  console.log("- /auth/*     -> auth_psy:3000");
  console.log("- /calendar/* -> calendar_psy:8000");
  console.log("- /telegram/* -> telegram-code-sender-psy:7000");
  console.log("- /whatsapp/* -> whatsapp-code-sender-psy:7001");
  console.log("- /bot/*      -> telegram-bot-psy:5000");
});
