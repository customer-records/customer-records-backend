require('dotenv').config();
const { Pool } = require('pg');
const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const pool = new Pool({
    user: process.env.DB_USER,
    host: process.env.DB_HOST,
    database: process.env.DB_NAME,
    password: process.env.DB_PASSWORD,
    port: 5432,
});

// Маршрут для регистрации сотрудника
app.post('/worker/register', async (req, res) => {
    const { 
        name, 
        last_name, 
        sur_name, 
        phone_number,
        chat_id,
        tg_name
    } = req.body;

    // Проверка обязательных полей
    if (!name || !last_name || !phone_number) {
        return res.status(400).json({ 
            status: 'error', 
            message: 'Name, last_name and phone_number are required' 
        });
    }

    try {
        // Проверка существования пользователя с таким номером телефона
        const userExists = await pool.query(
            'SELECT * FROM users WHERE phone_number = $1',
            [phone_number]
        );

        if (userExists.rows.length > 0) {
            return res.status(400).json({ 
                status: 'error', 
                message: 'User with this phone number already exists' 
            });
        }

        // Создание пользователя с ролью worker по умолчанию
        const newUser = await pool.query(
            `INSERT INTO users (
                role,
                name, 
                last_name, 
                sur_name, 
                phone_number,
                chat_id,
                tg_name
             ) VALUES ($1, $2, $3, $4, $5, $6, $7) 
             RETURNING *`,
            [
                'worker',
                name, 
                last_name, 
                sur_name || null,
                phone_number,
                chat_id || null,
                tg_name || null
            ]
        );

        res.status(201).json({
            status: 'success',
            user: {
                id: newUser.rows[0].id,
                role: newUser.rows[0].role,
                name: newUser.rows[0].name,
                last_name: newUser.rows[0].last_name,
                sur_name: newUser.rows[0].sur_name,
                phone_number: newUser.rows[0].phone_number,
                chat_id: newUser.rows[0].chat_id,
                tg_name: newUser.rows[0].tg_name
            },
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

// Маршрут для авторизации сотрудника
app.post('/worker/login', async (req, res) => {
    const { phone_number } = req.body;
    
    if (!phone_number) {
        return res.status(400).json({ 
            status: 'error', 
            message: 'Phone number is required' 
        });
    }

    try {
        // Поиск пользователя по номеру телефона
        const userResult = await pool.query(
            'SELECT * FROM users WHERE phone_number = $1', 
            [phone_number]
        );

        if (userResult.rows.length === 0) {
            return res.status(401).json({ 
                status: 'error', 
                message: 'User not found' 
            });
        }

        const user = userResult.rows[0];

        // Успешная авторизация
        res.json({
            status: 'success',
            user: {
                id: user.id,
                role: user.role,
                name: user.name,
                last_name: user.last_name,
                sur_name: user.sur_name,
                phone_number: user.phone_number,
                id_category_service: user.id_category_service,
                chat_id: user.chat_id,
                tg_name: user.tg_name
            },
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

// Маршрут для регистрации клиента (обновленная версия с логикой обновления)
app.post('/client/create', async (req, res) => {
    const { 
        name, 
        last_name, 
        sur_name, 
        phone_number, 
        tg_name,
        chat_id
    } = req.body;

    // Проверка обязательных полей
    if (!name || !phone_number) {
        return res.status(400).json({ 
            status: 'error', 
            message: 'Name and phone_number are required' 
        });
    }

    try {
        // Проверка существования клиента
        const clientExists = await pool.query(
            'SELECT * FROM clients WHERE phone_number = $1',
            [phone_number]
        );

        if (clientExists.rows.length > 0) {
            const existingClient = clientExists.rows[0];
            
            // Проверяем, есть ли у существующего клиента полные данные
            const hasFullData = existingClient.last_name && 
                              existingClient.sur_name && 
                              existingClient.tg_name && 
                              existingClient.chat_id;

            if (hasFullData) {
                // Если у клиента уже есть полные данные - возвращаем ошибку
                return res.status(400).json({ 
                    status: 'error', 
                    message: 'Client with full data already exists',
                    client: existingClient
                });
            }

            // Проверяем, пришли ли более полные данные в текущем запросе
            const hasNewData = last_name || sur_name || tg_name || chat_id;
            
            if (!hasNewData) {
                // Если новых данных нет - просто возвращаем существующего клиента
                return res.status(200).json({ 
                    status: 'success',
                    client: existingClient,
                    message: 'Client already exists' 
                });
            }

            // Обновляем данные клиента
            const updatedClient = await pool.query(
                `UPDATE clients SET
                    name = COALESCE($1, name),
                    last_name = COALESCE($2, last_name),
                    sur_name = COALESCE($3, sur_name),
                    tg_name = COALESCE($4, tg_name),
                    chat_id = COALESCE($5, chat_id)
                WHERE phone_number = $6
                RETURNING *`,
                [
                    name,
                    last_name || existingClient.last_name,
                    sur_name || existingClient.sur_name,
                    tg_name || existingClient.tg_name,
                    chat_id || existingClient.chat_id,
                    phone_number
                ]
            );

            return res.status(200).json({
                status: 'success',
                client: updatedClient.rows[0],
                message: 'Client data updated'
            });
        }

        // Если клиент не существует - создаем нового
        const newClient = await pool.query(
            `INSERT INTO clients (
                name, 
                last_name, 
                sur_name, 
                phone_number, 
                tg_name,
                chat_id
             ) VALUES ($1, $2, $3, $4, $5, $6) 
             RETURNING *`,
            [
                name, 
                last_name || null, 
                sur_name || null, 
                phone_number, 
                tg_name || null,
                chat_id || null
            ]
        );

        return res.status(201).json({
            status: 'success',
            client: newClient.rows[0],
            message: 'New client created'
        });
    } catch (error) {
        console.error(error);
        return res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

// Маршрут для поиска работника по номеру телефона
app.get('/user/find-by-phone/:phone_number', async (req, res) => {
    const { phone_number } = req.params;

    if (!phone_number) {
        return res.status(400).json({ 
            status: 'error', 
            message: 'Phone number is required' 
        });
    }

    try {
        // Нормализация номера телефона
        const cleanPhone = phone_number.replace(/\D/g, '');
        
        console.log('Searching for phone:', cleanPhone);
        
        // Поиск клиента по номеру телефона
        const clientResult = await pool.query(
            'SELECT * FROM users WHERE phone_number = $1 OR phone_number LIKE $2',
            [cleanPhone, `%${cleanPhone.slice(-10)}%`]
        );

        console.log('Found users:', clientResult.rows);
        
        if (clientResult.rows.length === 0) {
            return res.status(404).json({ 
                status: 'error', 
                message: 'User not found' 
            });
        }

        res.json({
            status: 'success',
            client: clientResult.rows[0]
        });
    } catch (error) {
        console.error('Error finding user by phone:', error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

// Маршрут для поиска клиента по номеру телефона
// Маршрут для поиска клиента по номеру телефона
app.get('/client/find-by-phone/:phone_number', async (req, res) => {
    const { phone_number } = req.params;

    if (!phone_number) {
        return res.status(400).json({ 
            status: 'error', 
            message: 'Phone number is required' 
        });
    }

    try {
        // Нормализация номера телефона
        const cleanPhone = phone_number.replace(/\D/g, '');
        
        // Поиск клиента по номеру телефона
        const clientResult = await pool.query(
            'SELECT * FROM clients WHERE phone_number = $1 OR phone_number LIKE $2',
            [cleanPhone, `%${cleanPhone.slice(-10)}%`]
        );
        
        if (clientResult.rows.length === 0) {
            return res.status(404).json({ 
                status: 'error', 
                message: 'Client not found' 
            });
        }

        const client = clientResult.rows[0];
        
        // Проверка заполненности обязательных полей для клиента
        const requiredFields = ['name', 'last_name', 'phone_number'];
        const hasAllRequiredFields = requiredFields.every(field => client[field]);
        
        if (!hasAllRequiredFields) {
            return res.status(404).json({ 
                status: 'error', 
                message: 'Client found but missing required fields (name, last_name)' 
            });
        }

        res.json({
            status: 'success',
            client: {
                id: client.id,
                name: client.name,
                last_name: client.last_name,
                sur_name: client.sur_name,
                phone_number: client.phone_number,
                tg_name: client.tg_name,
                chat_id: client.chat_id
            }
        });
    } catch (error) {
        console.error('Error finding client by phone:', error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

// Проверка подключения к базе данных
app.get('/check-db', async (req, res) => {
    try {
        const result = await pool.query('SELECT NOW()');
        res.json({ 
            status: 'success', 
            time: result.rows[0].now 
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Database connection failed' 
        });
    }
});

// Маршрут для получения всех пользователей
app.get('/users', async (req, res) => {
    try {
        const usersResult = await pool.query('SELECT * FROM users');

        res.json({
            status: 'success',
            users: usersResult.rows.map(user => ({
                id: user.id,
                role: user.role,
                name: user.name,
                last_name: user.last_name,
                sur_name: user.sur_name,
                phone_number: user.phone_number,
                id_category_service: user.id_category_service,
                chat_id: user.chat_id,
                tg_name: user.tg_name
            })),
        });
    } catch (error) {
        console.error(error);
        res.status(500).json({ 
            status: 'error', 
            message: 'Internal server error' 
        });
    }
});

app.listen(3000, () => {
    console.log('Auth service running on port 3000');
});