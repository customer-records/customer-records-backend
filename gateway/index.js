const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// Перенаправление запросов к сервису аутентификации
app.use('/auth', createProxyMiddleware({ target: 'http://auth:3000', changeOrigin: true }));

// Перенаправление запросов к сервису календаря
app.use('/calendar', createProxyMiddleware({ target: 'http://calendar:8000', changeOrigin: true }));

app.listen(4000, () => {
    console.log('Gateway запущен на порту 4000');
});