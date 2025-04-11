import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os
import time
import bcrypt
from datetime import datetime
from models import Base, User, CategoryService, TimeSlot, Client, OnlineRegistration, CompanyDescription

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Настройка базы данных
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
logger.info(f"Подключение к базе данных по URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

# Ожидание подключения к базе данных
def wait_for_db(engine, retries=5, delay=5):
    for i in range(retries):
        try:
            with engine.connect() as connection:
                logger.info("Подключение к базе данных успешно!")
                return True
        except OperationalError as e:
            logger.error(f"Попытка {i + 1}/{retries}: Не удалось подключиться к базе данных. Ошибка: {e}")
            time.sleep(delay)
    raise Exception("Не удалось подключиться к базе данных после нескольких попыток.")

def initialize_db():
    # Ожидаем доступность БД
    wait_for_db(engine)
    
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы созданы успешно!")
    
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Проверяем, есть ли уже данные в базе
        if not session.query(User).first():
            # Добавляем категории услуг для стоматологии с массивами услуг (3 категории)
            categories = [
                CategoryService(
                    name_category="Ортодонт",
                    time_width_minutes_end=60,
                    services_array=[
                        "Консультация",
                        "Установка брекет-систем",
                        "Коррекция прикуса у детей",
                        "Ретенционный период"
                    ]
                ),
                CategoryService(
                    name_category="Терапевтическая стоматология",
                    time_width_minutes_end=45,
                    services_array=[
                        "Лечение кариеса",
                        "Лечение пульпита",
                        "Реставрация зубов",
                        "Лечение периодонтита"
                    ]
                ),
                CategoryService(
                    name_category="Хирургия",
                    time_width_minutes_end=90,
                    services_array=[
                        "Удаление зуба",
                        "Имплантация",
                        "Синус-лифтинг",
                        "Костная пластика"
                    ]
                )
            ]
            session.add_all(categories)
            session.commit()

            # Добавляем стоматологическую клинику
            company = CompanyDescription(
                company_name="Denta - rell",
                company_description="Современная стоматологическая клиника с высококвалифицированными специалистами",
                company_adress_country="Россия",
                company_adress_city="Москва",
                company_adress_street="Стоматологическая",
                company_adress_house_number="15",
                company_adress_house_number_index="123456",
                time_work_start=datetime.strptime("08:00", "%H:%M").time(),
                time_work_end=datetime.strptime("20:00", "%H:%M").time(),
                weekdays_work_1=True,
                weekdays_work_2=True,
                weekdays_work_3=True,
                weekdays_work_4=True,
                weekdays_work_5=True,
                weekdays_work_6=True,
                weekdays_work_7=False
            )
            session.add(company)
            session.commit()

            # Хэшируем пароль для владельца
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw("dentist123".encode('utf-8'), salt)

            # Добавляем владельца (главного врача)
            owner = User(
                role="owner",
                email="chief@denta-rell.ru",
                password=hashed_password.decode('utf-8'),
                name="Алексей",
                last_name="Петров",
                sur_name="Сергеевич",
                phone_number="+79123456789",
                id_category_service=categories[0].id,
                google_api_key="dent_api_key",
                google_client_id="dent_client_id",
                google_calendar_id="dent_calendar_id",
                chat_id="123456789",
                tg_name="chief_dentist"
            )
            session.add(owner)
            session.commit()

            # Добавляем стоматологов (2 специалиста)
            dentists = [
                User(
                    role="worker",
                    email="dentist1@denta-rell.ru",
                    password=bcrypt.hashpw("doctor1pass".encode('utf-8'), salt).decode('utf-8'),
                    name="Ирина",
                    last_name="Иванова",
                    sur_name="Владимировна",
                    phone_number="+79876543210",
                    id_category_service=categories[1].id,
                    chat_id="987654321",
                    tg_name="dr_ivanova"
                ),
                User(
                    role="worker",
                    email="dentist2@denta-rell.ru",
                    password=bcrypt.hashpw("doctor2pass".encode('utf-8'), salt).decode('utf-8'),
                    name="Сергей",
                    last_name="Смирнов",
                    sur_name="Александрович",
                    phone_number="+79876543211",
                    id_category_service=categories[2].id,
                    chat_id="555555555",
                    tg_name="dr_smirnov"
                )
            ]
            session.add_all(dentists)
            session.commit()

            # Добавляем клиентов
            clients = [
                Client(
                    email="client1@example.com",
                    password=bcrypt.hashpw("clientpass1".encode('utf-8'), salt).decode('utf-8'),
                    name="Мария",
                    last_name="Сидорова",
                    phone_number="+79111111111",
                    tg_name="mary_sidorova",
                    chat_id="111111111"
                ),
                Client(
                    email="client2@example.com",
                    password=bcrypt.hashpw("clientpass2".encode('utf-8'), salt).decode('utf-8'),
                    name="Андрей",
                    last_name="Кузнецов",
                    phone_number="+79222222222",
                    tg_name="andrew_kuznetsov",
                    chat_id="222222222"
                )
            ]
            session.add_all(clients)
            session.commit()

            # Добавляем временные слоты на 09.04.2025
            date_09 = datetime(2025, 4, 9).date()
            time_slots_09 = [
                # Слоты для владельца (owner)
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_09,
                    time_start=datetime.strptime("09:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_09,
                    time_start=datetime.strptime("11:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_09,
                    time_start=datetime.strptime("14:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                
                # Слоты для первого стоматолога
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=dentists[0].id,
                    date=date_09,
                    time_start=datetime.strptime("10:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=dentists[0].id,
                    date=date_09,
                    time_start=datetime.strptime("13:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                
                # Слоты для второго стоматолога
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=dentists[1].id,
                    date=date_09,
                    time_start=datetime.strptime("11:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=dentists[1].id,
                    date=date_09,
                    time_start=datetime.strptime("15:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                )
            ]

            # Добавляем временные слоты на 10.04.2025
            date_10 = datetime(2025, 4, 10).date()
            time_slots_10 = [
                # Слоты для владельца (owner)
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_10,
                    time_start=datetime.strptime("10:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_10,
                    time_start=datetime.strptime("12:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_10,
                    time_start=datetime.strptime("16:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                
                # Слоты для первого стоматолога
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=dentists[0].id,
                    date=date_10,
                    time_start=datetime.strptime("09:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=dentists[0].id,
                    date=date_10,
                    time_start=datetime.strptime("14:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                
                # Слоты для второго стоматолога
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=dentists[1].id,
                    date=date_10,
                    time_start=datetime.strptime("11:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=dentists[1].id,
                    date=date_10,
                    time_start=datetime.strptime("17:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                )
            ]

            session.add_all(time_slots_09 + time_slots_10)
            session.commit()

            logger.info("Тестовые данные для стоматологии успешно добавлены в базу данных")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    initialize_db()