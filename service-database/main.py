import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os
import time
from datetime import datetime, date, time as dt_time, timedelta
from models import Base, CategoryService, CompanyDescription, User, TimeSlot
import bcrypt

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# URL базы данных
DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)
engine = create_engine(DATABASE_URL)

def wait_for_db(engine, retries=5, delay_seconds=5):
    for attempt in range(retries):
        try:
            with engine.connect():
                logger.info("Подключение к БД успешно!")
                return
        except OperationalError as e:
            logger.error(f"Попытка {attempt+1}/{retries}: ошибка: {e}")
            time.sleep(delay_seconds)
    raise RuntimeError("Не удалось подключиться к БД")

def generate_time_slots(start: dt_time, end: dt_time, duration_min: int,
                        slot_date: date, emp_id: int, cat_id: int):
    slots = []
    start_dt = datetime.combine(slot_date, start)
    end_dt = datetime.combine(slot_date, end)
    # если сквозь полночь, но в нашем случае не нужно
    if end <= start:
        end_dt += timedelta(days=1)
    curr = start_dt
    while curr + timedelta(minutes=duration_min) <= end_dt:
        slots.append(TimeSlot(
            id_category_service=cat_id,
            id_employer=emp_id,
            date=slot_date,
            time_start=curr.time(),
            id_time_width_minutes_end=cat_id
        ))
        curr += timedelta(minutes=duration_min)
    return slots

def initialize_db():
    wait_for_db(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # 1. Категории услуг
        service_names = [
            "Первичная онлайн консультация",
            "Стандартная онлайн консультация",
            "Стандартная офлайн консультация"
        ]
        categories = []
        for name in service_names:
            cat = CategoryService(
                name_category=name,
                time_width_minutes_end=60,
                services_array=[name]
            )
            categories.append(cat)
        session.add_all(categories)
        session.commit()
        logger.info("Категории услуг добавлены: %s", [c.id for c in categories])

        # 2. Описание практики
        company = CompanyDescription(
            company_name="MindCare",
            company_description="Онлайн и офлайн консультации психолога Анны Сергеевны",
            company_adress_country="Россия",
            company_adress_city="Москва",
            company_adress_street="Ленинградский проспект",
            company_adress_house_number="10",
            company_adress_house_number_index="000000",
            time_work_start=dt_time(10, 0),
            time_work_end=dt_time(22, 0),
            weekdays_work_1=True,
            weekdays_work_2=True,
            weekdays_work_3=True,
            weekdays_work_4=True,
            weekdays_work_5=True,
            weekdays_work_6=True,
            weekdays_work_7=True
        )
        session.add(company)
        session.commit()
        logger.info("Информация о компании добавлена: %s", company.id)

        # 3. Специалист: Анна Сергеевна — одна на все услуги
        salt = bcrypt.gensalt()
        slots = []
        today = date.today()
        for cat in categories:
            # уникальные email и chat_id для каждой услуги
            email = f"anna_{cat.id}@mindcare.ru"
            raw_password = "psychology123"
            anna = User(
                role="owner",
                email=email,
                password=bcrypt.hashpw(raw_password.encode(), salt).decode(),
                name="Анна",
                last_name="Сергеевна",
                phone_number="79001234567",
                id_category_service=cat.id,
                chat_id=f"40000000{cat.id}",
                tg_name=f"anna_psy_{cat.id}"
            )
            session.add(anna)
            session.flush()  # чтобы получить anna.id

            # генерируем слоты на неделю вперёд, каждый день
            for delta in range(7):
                d = today + timedelta(days=delta)
                slots.extend(generate_time_slots(
                    dt_time(10, 0),
                    dt_time(22, 0),
                    60,
                    d,
                    emp_id=anna.id,
                    cat_id=cat.id
                ))

        session.commit()
        session.add_all(slots)
        session.commit()
        logger.info("Пользователь и тайм-слоты добавлены для каждой услуги")

    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == '__main__':
    initialize_db()
