require("dotenv").config();
process.env.TZ = "Europe/Moscow";

const express = require("express");
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const { Pool } = require("pg");
const path = require("path");
const cors = require("cors");
const schedule = require("node-schedule");
const moment = require("moment-timezone");
const app = express();
app.use(express.json());
app.use(cors());

// Настройка подключения к PostgreSQL
const pool = new Pool({
  user: process.env.DB_USER,
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  password: process.env.DB_PASSWORD,
  port: 5432,
});

// Хранилище кодов подтверждения
const codesStorage = new Map();

// Шаблоны сообщений
const MESSAGE_TEMPLATES = [
  `🔐 Ваш код подтверждения: *{code}*\n\nИспользуйте этот код для входа в систему.\n⚠️ Никому не сообщайте этот код!`,
  `🛡️ Код безопасности: *{code}*\n\nВведите его для подтверждения действия.\n❌ Не передавайте код третьим лицам!`,
  `🔒 Ваш одноразовый код: *{code}*\n\nДействителен в течение 5 минут.\n🚫 Сообщение содержит конфиденциальную информацию!`,
];

// Инициализация WhatsApp клиента с сохранением сессии
const whatsappClient = new Client({
  puppeteer: {
    executablePath:
      process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--single-process",
      "--disable-gpu",
    ],
  },
  authStrategy: new LocalAuth({
    dataPath: path.join(__dirname, ".wwebjs_auth"),
  }),
  restartOnAuthFail: true,
});

// Обработчики событий WhatsApp
whatsappClient.on("qr", (qr) => {
  qrcode.generate(qr, { small: true });
  console.log("QR код сгенерирован, отсканируйте его через WhatsApp");
});

whatsappClient.on("authenticated", () => {
  console.log("Аутентификация WhatsApp успешна!");
});

whatsappClient.on("auth_failure", (msg) => {
  console.error("Ошибка аутентификации:", msg);
});

whatsappClient.on("ready", () => {
  console.log("WhatsApp клиент готов к работе");
});

whatsappClient.on("message", (message) => {
  console.log("Получено сообщение:", message.body);
});

whatsappClient.initialize().catch((err) => {
  console.error("Ошибка инициализации WhatsApp:", err);
});

// Генерация случайной задержки
const getRandomDelay = () => Math.floor(Math.random() * 15000) + 5000; // 5-20 секунд

// Получение случайного шаблона сообщения
const getRandomTemplate = (code) => {
  const template =
    MESSAGE_TEMPLATES[Math.floor(Math.random() * MESSAGE_TEMPLATES.length)];
  return template.replace("{code}", code);
};

// Универсальная функция отправки WhatsApp-сообщения
async function sendWhatsAppMessage(phone, messageContent) {
  const cleanPhone = phone.replace(/\D/g, "");
  const whatsappNumber = `${cleanPhone}@c.us`;
  try {
    await whatsappClient.sendMessage(whatsappNumber, messageContent);
    console.log(
      `Сообщение "${messageContent}" отправлено на номер ${cleanPhone}`
    );
  } catch (err) {
    console.error(`Ошибка при отправке сообщения на ${cleanPhone}:`, err);
  }
}

// Проверка подключения к БД и WhatsApp клиента
app.get("/health", async (req, res) => {
  try {
    await pool.query("SELECT NOW()");
    res.json({
      status: "ok",
      whatsapp: whatsappClient.info ? "connected" : "disconnected",
      db: "connected",
    });
  } catch (error) {
    console.error("Database connection error:", error);
    res.status(500).json({
      status: "error",
      whatsapp: whatsappClient.info ? "connected" : "disconnected",
      db: "disconnected",
    });
  }
});

// Отправка кода через WhatsApp
app.post("/send-code/:phone_number", async (req, res) => {
  const { phone_number } = req.params;

  try {
    if (!whatsappClient.info) {
      return res.status(503).json({
        status: "error",
        message: "WhatsApp client not ready",
      });
    }
    const cleanPhone = phone_number.replace(/\D/g, "");
    const code = Math.floor(1000 + Math.random() * 9000).toString();
    codesStorage.set(cleanPhone, code);

    // Добавляем случайную задержку
    const delay = getRandomDelay();
    console.log(`Отправка кода через ${delay / 1000} секунд...`);

    setTimeout(async () => {
      try {
        const message = getRandomTemplate(code);
        await sendWhatsAppMessage(cleanPhone, message);
      } catch (err) {
        console.error("Ошибка при отправке сообщения:", err);
      }
    }, delay);

    res.json({
      status: "success",
      message: "Code will be sent via WhatsApp",
      phone: cleanPhone,
      code: code,
      delay_seconds: delay / 1000,
    });
  } catch (error) {
    console.error("Error:", error);
    res.status(500).json({
      status: "error",
      message: "Failed to process request",
    });
  }
});

// Проверка кода
app.get("/verify-code/:code", async (req, res) => {
  const { code } = req.params;

  try {
    // Ищем код в хранилище
    let foundPhone = null;
    let foundChatId = null;
    let foundUsername = null;

    for (const [phone, storedCode] of codesStorage.entries()) {
      if (storedCode === code) {
        foundPhone = phone;

        // Попробуем найти пользователя в базе данных
        try {
          const userResult = await pool.query(
            `SELECT chat_id, tg_name FROM clients 
             WHERE phone_number = $1 OR phone_number LIKE $2`,
            [foundPhone, `%${foundPhone.slice(-10)}%`]
          );

          if (userResult.rows.length > 0) {
            foundChatId = userResult.rows[0].chat_id || null;
            foundUsername = userResult.rows[0].tg_name || null;
          }
        } catch (dbError) {
          console.error("Database query error:", dbError);
        }

        break;
      }
    }

    if (foundPhone) {
      res.json({
        status: "success",
        phone: foundPhone,
        username: foundUsername,
        chat_id: foundChatId,
        code: code,
      });
    } else {
      res.status(404).json({
        status: "error",
        message: "Code not found or expired",
      });
    }
  } catch (error) {
    console.error("Error verifying code:", error);
    res.status(500).json({
      status: "error",
      message: "Internal server error",
    });
  }
});

// Очистка кода
app.delete("/clear-code/:code", async (req, res) => {
  const { code } = req.params;

  try {
    let cleared = false;
    for (const [phone, storedCode] of codesStorage.entries()) {
      if (storedCode === code) {
        codesStorage.delete(phone);
        cleared = true;
        break;
      }
    }

    if (cleared) {
      res.json({ status: "success", message: "Code cleared" });
    } else {
      res.status(404).json({ status: "error", message: "Code not found" });
    }
  } catch (error) {
    console.error("Error clearing code:", error);
    res.status(500).json({ status: "error", message: "Failed to clear code" });
  }
});

// Отправка напоминания о записи
app.post("/send-notification", async (req, res) => {
  const {
    phone,
    client_name,
    appointment_date, // 'YYYY-MM-DD'
    appointment_time, // 'HH:MM'
    service_name,
    specialist_name,
  } = req.body;

  // Валидация
  if (!phone || !client_name || !appointment_date || !appointment_time) {
    return res.status(400).json({
      status: "error",
      message:
        "Необходимо указать phone, client_name, appointment_date, appointment_time",
    });
  }
  if (!whatsappClient.info) {
    return res.status(503).json({
      status: "error",
      message: "WhatsApp client not ready",
    });
  }

  // Фабрика текста уведомления
  const buildMessage = () =>
    `Здравствуйте, ${client_name}!\n` +
    `Напоминаем о вашей записи на услугу: *${service_name}*.\n` +
    `Специалист: *${specialist_name}*.\n` +
    `Дата: *${appointment_date}*, время: *${appointment_time}*.\n` +
    `Ждём вас! 😊`;

  // 1) Сразу при бронировании
  await sendWhatsAppMessage(phone, buildMessage());

  // 2) Парсим дату/время визита и приводим к московскому 08:00
  const visitMoment = moment
    .tz(
      `${appointment_date} ${appointment_time}`,
      "YYYY-MM-DD HH:mm",
      "Europe/Moscow"
    )
    .hour(8)
    .minute(0)
    .second(0);

  const now = moment.tz("Europe/Moscow");

  // Хелпер для планирования
  function scheduleReminder(targetMoment, label) {
    if (targetMoment.isAfter(now)) {
      console.log(
        `Планируем напоминание "${label}" на ${targetMoment.format()}`
      );
      schedule.scheduleJob(targetMoment.toDate(), async () => {
        console.log(`Отправляем напоминание: ${label}`);
        await sendWhatsAppMessage(phone, buildMessage());
      });
    } else {
      console.log(
        `Пропускаем "${label}", время ${targetMoment.format()} уже прошло`
      );
    }
  }

  // 3 дня до визита
  scheduleReminder(
    visitMoment.clone().subtract(3, "days"),
    "за 3 дня до визита"
  );

  // 1 день до визита
  scheduleReminder(
    visitMoment.clone().subtract(1, "day"),
    "за 1 день до визита"
  );

  // В день визита в 08:00
  scheduleReminder(visitMoment, "в день визита");

  res.json({ status: "success", message: "Notifications scheduled" });
});

// Запуск сервера
const PORT = process.env.PORT || 7001;
app.listen(PORT, () => {
  console.log(`WhatsApp Code Sender service running on port ${PORT}`);
});

// Обработка SIGINT
process.on("SIGINT", async () => {
  console.log("Shutting down...");
  try {
    await whatsappClient.destroy();
    await pool.end();
    console.log("Resources cleaned up");
  } catch (err) {
    console.error("Error during shutdown:", err);
  } finally {
    process.exit();
  }
});
