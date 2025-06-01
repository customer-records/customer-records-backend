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
from apscheduler.schedulers.background import BackgroundScheduler

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
            "Столик для двоих",
            "Столик от 4 до 6 гостей",
            "Столик от 4 до 6 гостей с Xbox",
            "Столик от 4 до 6 гостей с PlayStation",
            "VIP комната от 4 до 6 гостей"
        ]
        categories = []
        for name in service_names:
            cat = CategoryService(
                name_category=name,
                time_width_minutes_end=120,
                services_array=[name]
            )
            categories.append(cat)
        session.add_all(categories)
        session.commit()
        logger.info("Категории услуг добавлены: %s", [c.id for c in categories])

        # 2. Информация о компании
        company = CompanyDescription(
            company_name="Beerloga",
            company_description="Уютная кальянная с авторскими смесями и гостеприимной атмосферой",
            company_adress_country="Россия",
            company_adress_city="Казань",
            company_adress_street="Мавлютого",
            company_adress_house_number="46",
            company_adress_house_number_index="000000",
            time_work_start=dt_time(14, 0),
            time_work_end=dt_time(2, 0),
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

        # 3. Добавляем специалистов-кальянщиков и генерируем слоты для каждой услуги
        salt = bcrypt.gensalt()
        slots = []
        # дни работы специалистов
        sergey_days = {0, 2, 4, 6}  # Пн, Ср, Пт, Вс
        nikita_days = {1, 3, 5}     # Вт, Чт, Сб
        for cat in categories:
            # создаем Сергея для этой услуги
            sergey = User(
                role="owner",
                email=f"sergey_{cat.id}@beerloga.ru",
                password=bcrypt.hashpw(f"sergeypass{cat.id}".encode(), salt).decode(),
                name="Кальянщик",
                last_name="Сергей",
                phone_number="79000000001",
                id_category_service=cat.id,
                chat_id="300000001",
                tg_name=f"hookah_sergey_{cat.id}"
            )
            # создаем Никиту для этой услуги
            nikita = User(
                role="worker",
                email=f"nikita_{cat.id}@beerloga.ru",
                password=bcrypt.hashpw(f"nikitapass{cat.id}".encode(), salt).decode(),
                name="Кальянщик",
                last_name="Никита",
                phone_number="79000000002",
                id_category_service=cat.id,
                chat_id="300000002",
                tg_name=f"hookah_nikita_{cat.id}"
            )
            session.add_all([sergey, nikita])
            session.flush()  # чтобы получить ID
            # генерация слотов для этой и следующих 6 дней (текущая неделя)
            today = date.today()
            for delta in range(7):
                d = today + timedelta(days=delta)
                if d.weekday() in sergey_days:
                    slots.extend(generate_time_slots(dt_time(16,30), dt_time(2,0), 120, d, sergey.id, cat.id))
                if d.weekday() in nikita_days:
                    slots.extend(generate_time_slots(dt_time(16,30), dt_time(2,0), 120, d, nikita.id, cat.id))
        session.commit()
        session.add_all(slots)
        session.commit()
        logger.info("Специалисты и слоты добавлены для каждой услуги")

    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def generate_next_week_slots():
    """
    Генерирует слоты для следующей недели (начиная с ближайшего понедельника после текущей даты).
    Аналогично initialize_db, но только слоты — без пересоздания категорий и пользователей.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Вычисляем следующий понедельник:
        today = date.today()
        if today.weekday() == 6:  # если сегодня воскресенье
            next_monday = today + timedelta(days=1)
        else:
            next_monday = today + timedelta(days=(7 - today.weekday()))

        # Получаем категории и пользователей
        categories = session.query(CategoryService).all()
        # Специалисты по категориям: каждая категория имеет двух юзеров—«owner» (Сергей) и «worker» (Никита)
        # Для упрощения: ищем по id_category_service и role
        slots = []
        for cat in categories:
            sergey = session.query(User).filter_by(
                id_category_service=cat.id, role="owner"
            ).first()
            nikita = session.query(User).filter_by(
                id_category_service=cat.id, role="worker"
            ).first()
            sergey_days = {0, 2, 4, 6}  # Пн, Ср, Пт, Вс
            nikita_days = {1, 3, 5}     # Вт, Чт, Сб

            for delta in range(7):
                d = next_monday + timedelta(days=delta)
                if d.weekday() in sergey_days and sergey:
                    slots.extend(generate_time_slots(
                        dt_time(16,30), dt_time(2,0), 120, d, sergey.id, cat.id
                    ))
                if d.weekday() in nikita_days and nikita:
                    slots.extend(generate_time_slots(
                        dt_time(16,30), dt_time(2,0), 120, d, nikita.id, cat.id
                    ))
        if slots:
            session.add_all(slots)
            session.commit()
            logger.info(f"Автозаполнение: добавлены слоты для недели, начинающейся {next_monday}")
    except Exception as e:
        logger.error(f"Ошибка при автозаполнении на следующую неделю: {e}")
    finally:
        session.close()

if __name__ == '__main__':
    # 1. Инициализация БД и первоначальная загрузка
    initialize_db()

    # 2. Планировщик, который каждое воскресенье в 00:00 запускает автозаполнение на следующую неделю
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        generate_next_week_slots,
        trigger='cron',
        day_of_week='sun',
        hour=0,
        minute=0
    )
    scheduler.start()
    logger.info("Планировщик запущен. Автозаполнение слотов запланировано каждое воскресенье в 00:00.")

    try:
        # Поддерживаем процесс живым, чтобы планировщик работал
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Планировщик остановлен, сервис завершает работу.")
