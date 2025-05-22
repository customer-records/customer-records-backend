// gateway_test/src/index.js
const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const morgan = require("morgan");
const cors = require("cors");

const app = express();

// Логирование запросов и CORS
app.use(morgan("combined"));
app.use(cors());

// Здоровье шлюза
app.get("/health", (req, res) => {
  res.status(200).json({ status: "OK" });
});

// Проксирование на тестовый Auth
app.use(
  "/auth",
  createProxyMiddleware({
    target: "http://auth_test:3000",
    changeOrigin: true,
    pathRewrite: { "^/auth": "" },
    onError: (err, req, res) => {
      console.error("Auth service error:", err);
      res.status(502).json({ error: "Auth service unavailable" });
    },
  })
);

// Проксирование на тестовый Calendar
app.use(
  "/calendar",
  createProxyMiddleware({
    target: "http://calendar_test:8000",
    changeOrigin: true,
    pathRewrite: { "^/calendar": "" },
    onError: (err, req, res) => {
      console.error("Calendar service error:", err);
      res.status(502).json({ error: "Calendar service unavailable" });
    },
  })
);

// Проксирование на тестовый Telegram Code Sender
app.use(
  "/telegram",
  createProxyMiddleware({
    target: "http://telegram-code-sender-test:7000",
    changeOrigin: true,
    pathRewrite: { "^/telegram": "" },
    onError: (err, req, res) => {
      console.error("Telegram code sender error:", err);
      res.status(502).json({ error: "Telegram code sender unavailable" });
    },
  })
);

// Проксирование на тестовый WhatsApp Code Sender
app.use(
  "/whatsapp",
  createProxyMiddleware({
    target: "http://whatsapp-code-sender-test:7001",
    changeOrigin: true,
    pathRewrite: { "^/whatsapp": "" },
    onError: (err, req, res) => {
      console.error("WhatsApp code sender error:", err);
      res.status(502).json({ error: "WhatsApp code sender unavailable" });
    },
  })
);

// Проксирование на тестовый Telegram Bot (webhook)
app.use(
  "/bot",
  createProxyMiddleware({
    target: "http://telegram-bot-test:5000",
    changeOrigin: true,
    pathRewrite: { "^/bot": "" },
    onError: (err, req, res) => {
      console.error("Telegram bot error:", err);
      res.status(502).json({ error: "Telegram bot service unavailable" });
    },
  })
);

// Если в тестовом окружении нет parser-сервиса, этот блок можно удалить или закомментировать:
// app.use(
//   "/parser",
//   createProxyMiddleware({
//     target: "http://parser_test:3002",
//     changeOrigin: true,
//     pathRewrite: { "^/parser": "" },
//     onError: (err, req, res) => {
//       console.error("Parser service error:", err);
//       res.status(502).json({ error: "Parser service unavailable" });
//     },
//   })
// );

// Обработка несуществующих маршрутов
app.use((req, res) => {
  res.status(404).json({ error: "Route not found" });
});

// Глобальная обработка ошибок
app.use((err, req, res, next) => {
  console.error("Gateway error:", err);
  res.status(500).json({ error: "Internal server error" });
});

// Запуск на порту 4000 (в контейнере), проброс на хост 4002
const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`Gateway_test запущен на порту ${PORT}`);
  console.log("Маршруты:");
  console.log("- /auth/*     -> auth_test:3000");
  console.log("- /calendar/* -> calendar_test:8000");
  console.log("- /telegram/* -> telegram-code-sender-test:7000");
  console.log("- /whatsapp/* -> whatsapp-code-sender-test:7001");
  console.log("- /bot/*      -> telegram-bot-test:5000");
  // console.log("- /parser/*   -> parser_test:3002");
});
