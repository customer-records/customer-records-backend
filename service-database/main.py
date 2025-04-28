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
            # Добавляем категории услуг с массивами услуг
            categories = [
                CategoryService(
                    name_category="Хирург имплантолог",
                    time_width_minutes_end=10,
                    services_array=[
                        "Консультация хирурга имплантация/удаление",
                    ]
                ),
                CategoryService(
                    name_category="Терапевт-ортопед",
                    time_width_minutes_end=15,
                    services_array=[
                        "Первичная консультация терапевта​",
                    ]
                ),
                CategoryService(
                    name_category="Стоматолог-терапевт",
                    time_width_minutes_end=15,
                    services_array=[
                        "Первичная консультация терапевта​",
                    ]
                )
            ]
            session.add_all(categories)
            session.commit()

            # Добавляем стоматологическую клинику
            company = CompanyDescription(
                company_name="Denta Rell",
                company_description="Современная стоматологическая клиника с высококвалифицированными специалистами",
                company_adress_country="Россия",
                company_adress_city="Казань",
                company_adress_street="Проспект Победы",
                company_adress_house_number="35 Б",
                company_adress_house_number_index="420000",
                time_work_start=datetime.strptime("09:00", "%H:%M").time(),
                time_work_end=datetime.strptime("19:00", "%H:%M").time(),
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
            hashed_password = bcrypt.hashpw("owner123".encode('utf-8'), salt)

            # Добавляем владельца (Гадисов Ренат Фамильевич)
            owner = User(
                role="owner",
                email="renat@dentapro.ru",
                password=hashed_password.decode('utf-8'),
                name="Ринат",
                last_name="Сергеев",
                sur_name="Леонидович",
                phone_number="79172759797",
                id_category_service=categories[1].id,  # Хирург имплантолог
                google_api_key="dentapro_api_key",
                google_client_id="dentapro_client_id",
                google_calendar_id="dentapro_calendar_id",
                chat_id="100000001",
                tg_name="dr_gadisov"
            )
            session.add(owner)
            session.commit()

            # Добавляем работников
            workers = [
                User(
                    role="worker",
                    email="rinat@dentapro.ru",
                    password=bcrypt.hashpw("doctor1pass".encode('utf-8'), salt).decode('utf-8'),
                    name="Ренат",
                    last_name="Гадисов",
                    sur_name="Фамильевич",
                    phone_number="79274770444",
                    id_category_service=categories[0].id,  # Терапевт-ортопед
                    chat_id="100000002",
                    tg_name="dr_sergeev"
                ),
                User(
                    role="worker",
                    email="svetlana@dentapro.ru",
                    password=bcrypt.hashpw("doctor2pass".encode('utf-8'), salt).decode('utf-8'),
                    name="Светлана",
                    last_name="Бареева",
                    sur_name="Геннадьевна",
                    phone_number="79872954242",
                    id_category_service=categories[2].id,  # Стоматолог-терапевт
                    chat_id="100000003",
                    tg_name="dr_bareeva"
                ),
                User(
                    role="worker",
                    email="alfiya@dentapro.ru",
                    password=bcrypt.hashpw("doctor3pass".encode('utf-8'), salt).decode('utf-8'),
                    name="Альфия",
                    last_name="Шарипова",
                    sur_name="Маратовна",
                    phone_number="79969029242",
                    id_category_service=categories[2].id,  # Стоматолог-терапевт
                    chat_id="100000004",
                    tg_name="dr_sharipova"
                )
            ]
            session.add_all(workers)
            session.commit()

            # Добавляем клиентов
            clients = [
                Client(
                    email="client1@example.com",
                    password=bcrypt.hashpw("clientpass1".encode('utf-8'), salt).decode('utf-8'),
                    name="Иван",
                    last_name="Иванов",
                    phone_number="79111111111",
                    tg_name="ivan_ivanov",
                    chat_id="200000001"
                ),
                Client(
                    email="client2@example.com",
                    password=bcrypt.hashpw("clientpass2".encode('utf-8'), salt).decode('utf-8'),
                    name="Елена",
                    last_name="Петрова",
                    phone_number="79222222222",
                    tg_name="elena_petrova",
                    chat_id="200000002"
                )
            ]
            session.add_all(clients)
            session.commit()

            # Добавляем временные слоты на 10.04.2025
            date_10 = datetime(2025, 4, 28).date()
            time_slots_10 = [
                # Слоты для владельца (Гадисов Ренат)
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_10,
                    time_start=datetime.strptime("09:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_10,
                    time_start=datetime.strptime("11:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                
                # Слоты для Сергеева Рината (Терапевт-ортопед)
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=workers[0].id,
                    date=date_10,
                    time_start=datetime.strptime("10:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=workers[0].id,
                    date=date_10,
                    time_start=datetime.strptime("13:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                
                # Слоты для Бареевой Светланы (Стоматолог-терапевт)
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[1].id,
                    date=date_10,
                    time_start=datetime.strptime("09:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[1].id,
                    date=date_10,
                    time_start=datetime.strptime("14:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                
                # Слоты для Шариповой Альфии (Стоматолог-терапевт)
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[2].id,
                    date=date_10,
                    time_start=datetime.strptime("10:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[2].id,
                    date=date_10,
                    time_start=datetime.strptime("15:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                )
            ]

            # Добавляем временные слоты на 11.04.2025
            date_11 = datetime(2025, 4, 29).date()
            time_slots_11 = [
                # Слоты для владельца (Гадисов Ренат)
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_11,
                    time_start=datetime.strptime("10:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                TimeSlot(
                    id_category_service=categories[0].id,
                    id_employer=owner.id,
                    date=date_11,
                    time_start=datetime.strptime("12:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[0].id
                ),
                
                # Слоты для Сергеева Рината (Терапевт-ортопед)
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=workers[0].id,
                    date=date_11,
                    time_start=datetime.strptime("09:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                TimeSlot(
                    id_category_service=categories[1].id,
                    id_employer=workers[0].id,
                    date=date_11,
                    time_start=datetime.strptime("14:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[1].id
                ),
                
                # Слоты для Бареевой Светланы (Стоматолог-терапевт)
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[1].id,
                    date=date_11,
                    time_start=datetime.strptime("11:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[1].id,
                    date=date_11,
                    time_start=datetime.strptime("16:00", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                
                # Слоты для Шариповой Альфии (Стоматолог-терапевт)
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[2].id,
                    date=date_11,
                    time_start=datetime.strptime("10:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                ),
                TimeSlot(
                    id_category_service=categories[2].id,
                    id_employer=workers[2].id,
                    date=date_11,
                    time_start=datetime.strptime("15:30", "%H:%M").time(),
                    id_time_width_minutes_end=categories[2].id
                )
            ]

            session.add_all(time_slots_10 + time_slots_11)
            session.commit()

            logger.info("Данные для стоматологической клиники успешно добавлены в базу данных")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    initialize_db()