import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os
import time
import bcrypt
from datetime import datetime, time as dt_time, timedelta
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

# График работы специалистов
WORK_SCHEDULE = {
    "Гадисов Ренат Фамильевич": {
        "days": ["ПТ", "СБ"],
        "hours": ("9:00", "13:00"),
        "duration": 10
    },
    "Сергеев Ринат Леонидович": {
        "days": ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"],
        "hours": ("9:00", "19:00"),
        "duration": 15
    },
    "Бареева Светлана Геннадьевна": {
        "days": ["ВТ", "СР"],
        "hours": ("9:00", "14:00"),
        "duration": 15
    },
    "Шарипова Альфия Маратовна": {
        "days": ["СР", "ЧТ"],
        "hours": ("15:00", "19:00"),
        "duration": 15
    }
}

# Соответствие номеров дней недели и их обозначений
WEEKDAYS = {
    0: "ПН",
    1: "ВТ",
    2: "СР",
    3: "ЧТ",
    4: "ПТ",
    5: "СБ",
    6: "ВС"
}

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

def generate_time_slots(start_time_str, end_time_str, duration_minutes, date, worker_id, category_id):
    slots = []
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()
    
    current_time = datetime.combine(date, start_time)
    end_datetime = datetime.combine(date, end_time)
    
    while current_time + timedelta(minutes=duration_minutes) <= end_datetime:
        slots.append(TimeSlot(
            id_category_service=category_id,
            id_employer=worker_id,
            date=date,
            time_start=current_time.time(),
            id_time_width_minutes_end=category_id
        ))
        current_time += timedelta(minutes=duration_minutes)
    
    return slots

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

            # Создаем временные слоты для каждого специалиста на текущую неделю
            today = datetime.now().date()
            all_time_slots = []
            
            # Начинаем с сегодняшнего дня и добавляем слоты до конца недели
            for day in range(7):
                current_date = today + timedelta(days=day)
                weekday_num = current_date.weekday()  # 0-ПН, 6-ВС
                weekday_name = WEEKDAYS[weekday_num]
                
                # Гадисов Ренат (ПТ-СБ 9:00-13:00)
                if weekday_name in WORK_SCHEDULE["Гадисов Ренат Фамильевич"]["days"]:
                    slots = generate_time_slots(
                        "9:00", "13:00", 10,
                        current_date, workers[0].id, categories[0].id
                    )
                    all_time_slots.extend(slots)
                
                # Сергеев Ринат (ПН-СБ 9:00-19:00)
                if weekday_name in WORK_SCHEDULE["Сергеев Ринат Леонидович"]["days"]:
                    slots = generate_time_slots(
                        "9:00", "19:00", 15,
                        current_date, owner.id, categories[1].id
                    )
                    all_time_slots.extend(slots)
                
                # Бареева Светлана (ВТ-СР 9:00-14:00)
                if weekday_name in WORK_SCHEDULE["Бареева Светлана Геннадьевна"]["days"]:
                    slots = generate_time_slots(
                        "9:00", "14:00", 15,
                        current_date, workers[1].id, categories[2].id
                    )
                    all_time_slots.extend(slots)
                
                # Шарипова Альфия (СР-ЧТ 15:00-19:00)
                if weekday_name in WORK_SCHEDULE["Шарипова Альфия Маратовна"]["days"]:
                    slots = generate_time_slots(
                        "15:00", "19:00", 15,
                        current_date, workers[2].id, categories[2].id
                    )
                    all_time_slots.extend(slots)

            session.add_all(all_time_slots)
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