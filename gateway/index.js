const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const morgan = require('morgan');
const cors = require('cors');

const app = express();

// Логирование запросов
app.use(morgan('combined'));
app.use(cors());

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'OK' });
});
// Перенаправление запросов к сервису аутентификации
app.use('/auth', createProxyMiddleware({ 
  target: 'http://auth:3000', 
  changeOrigin: true,
  pathRewrite: {
    '^/auth': ''
  },
  onError: (err, req, res) => {
    console.error('Auth service error:', err);
    res.status(502).json({ error: 'Auth service unavailable' });
  }
}));

// Перенаправление запросов к сервису календаря
app.use('/calendar', createProxyMiddleware({ 
  target: 'http://calendar:8000',
  changeOrigin: true,
  pathRewrite: {
    '^/calendar': ''
  },
  onError: (err, req, res) => {
    console.error('Calendar service error:', err);
    res.status(502).json({ error: 'Calendar service unavailable' });
  }
}));

// Перенаправление запросов к сервису telegram-code-sender
app.use('/telegram', createProxyMiddleware({ 
  target: 'http://telegram-code-sender:7000',
  changeOrigin: true,
  pathRewrite: {
    '^/telegram': ''
  },
  onError: (err, req, res) => {
    console.error('Telegram code sender error:', err);
    res.status(502).json({ error: 'Telegram service unavailable' });
  }
}));
// Перенаправление запросов к сервису whatsapp-code-sender
app.use('/whatsapp', createProxyMiddleware({ 
  target: 'http://whatsapp-code-sender:7001',
  changeOrigin: true,
  pathRewrite: {
    '^/whatsapp': ''
  },
  onError: (err, req, res) => {
    console.error('WhatsApp code sender error:', err);
    res.status(502).json({ error: 'WhatsApp service unavailable' });
  }
}));
// Перенаправление запросов к сервису telegram-bot (webhook)
app.use('/bot', createProxyMiddleware({ 
  target: 'http://telegram-bot:3001',
  changeOrigin: true,
  pathRewrite: {
    '^/bot': ''
  },
  onError: (err, req, res) => {
    console.error('Telegram bot error:', err);
    res.status(502).json({ error: 'Telegram bot service unavailable' });
  }
}));

// Перенаправление запросов к сервису парсера
app.use('/parser', createProxyMiddleware({ 
  target: 'http://parser:3002',
  changeOrigin: true,
  pathRewrite: {
    '^/parser': ''
  },
  onError: (err, req, res) => {
    console.error('Parser service error:', err);
    res.status(502).json({ error: 'Parser service unavailable' });
  }
}));

// Обработка несуществующих маршрутов
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

// Обработка ошибок
app.use((err, req, res, next) => {
  console.error('Gateway error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`Gateway запущен на порту ${PORT}`);
  console.log('Доступные маршруты:');
  console.log('- /auth/* -> Auth service');
  console.log('- /calendar/* -> Calendar service');
  console.log('- /telegram/* -> Telegram code sender');
  console.log('- /bot/* -> Telegram bot');
  console.log('- /parser/* -> Parser service');
  console.log('- /whatsapp/* -> WhatsApp code sender');
});