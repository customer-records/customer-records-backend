require('dotenv').config(); // Загружаем переменные из .env
const { Pool } = require('pg');
const express = require('express');

const app = express();

const pool = new Pool({
    user: process.env.DB_USER,          // Имя пользователя
    host: process.env.DB_HOST,          // Хост
    database: process.env.DB_NAME,      // Имя базы данных
    password: process.env.DB_PASSWORD,  // Пароль
    port: process.env.DB_PORT,          // Порт
});

// Проверка подключения к базе данных
app.get('/check-db', async (req, res) => {
    try {
        const result = await pool.query('SELECT NOW()');
        res.json({ status: 'success', time: result.rows[0].now });
    } catch (error) {
        console.error(error);
        res.status(500).json({ status: 'error', message: 'Database connection failed' });
    }
});

app.listen(3000, () => {
    console.log('Auth service running on port 3000');
});