import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import os
import time
import bcrypt
from datetime import datetime, date, time as dt_time, timedelta
from models import Base, User, CategoryService, TimeSlot, Client, CompanyDescription
from apscheduler.schedulers.background import BackgroundScheduler

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Настройка базы данных
DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)
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


def wait_for_db(engine, retries=5, delay=5):
    for i in range(retries):
        try:
            with engine.connect() as connection:
                logger.info("Подключение к базе данных успешно!")
                return True
        except OperationalError as e:
            logger.error(f"Попытка {i + 1}/{retries}: Не удалось подключиться к БД. Ошибка: {e}")
            time.sleep(delay)
    raise Exception("Не удалось подключиться к БД после нескольких попыток.")


def generate_time_slots(start_time_str, end_time_str, duration_minutes, slot_date, worker_id, category_id):
    slots = []
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()

    current_time = datetime.combine(slot_date, start_time)
    end_datetime = datetime.combine(slot_date, end_time)

    while current_time + timedelta(minutes=duration_minutes) <= end_datetime:
        slots.append(TimeSlot(
            id_category_service=category_id,
            id_employer=worker_id,
            date=slot_date,
            time_start=current_time.time(),
            id_time_width_minutes_end=category_id
        ))
        current_time += timedelta(minutes=duration_minutes)

    return slots


def create_initial_data(session):
    """
    Добавляет базовые записи в таблицы User, CategoryService, CompanyDescription и клиентов,
    если они ещё не существуют.
    """
    if session.query(User).first():
        return  # Данные уже есть, пропускаем

    # 1. Категории услуг
    categories = [
        CategoryService(
            name_category="Хирург имплантолог",
            time_width_minutes_end=10,
            services_array=["Консультация хирурга имплантация/удаление"]
        ),
        CategoryService(
            name_category="Терапевт-ортопед",
            time_width_minutes_end=15,
            services_array=["Первичная консультация терапевта​"]
        ),
        CategoryService(
            name_category="Стоматолог-терапевт",
            time_width_minutes_end=15,
            services_array=["Первичная консультация терапевта​"]
        )
    ]
    session.add_all(categories)
    session.commit()

    # 2. Информация о компании
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

    # 3. Владелец (owner)
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw("owner123".encode('utf-8'), salt)
    owner = User(
        role="owner",
        email="renat@dentapro.ru",
        password=hashed_password.decode('utf-8'),
        name="Ринат",
        last_name="Сергеев",
        sur_name="Леонидович",
        phone_number="79172759797",
        id_category_service=categories[1].id,  # Терапевт-ортопед
        google_api_key="dentapro_api_key",
        google_client_id="dentapro_client_id",
        google_calendar_id="dentapro_calendar_id",
        chat_id="100000001",
        tg_name="dr_gadisov"
    )
    session.add(owner)
    session.commit()

    # 4. Работники (workers)
    workers = [
        User(
            role="worker",
            email="rinat@dentapro.ru",
            password=bcrypt.hashpw("doctor1pass".encode('utf-8'), salt).decode('utf-8'),
            name="Ренат",
            last_name="Гадисов",
            sur_name="Фамильевич",
            phone_number="79274770444",
            id_category_service=categories[0].id,  # Хирург имплантолог
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

    # 5. Клиенты (clients)
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


def generate_week_slots(session, start_date: date):
    """
    Генерирует и сохраняет временные слоты для заданной недели, начиная со start_date (понедельник).
    Если слоты на какую-либо дату уже существуют, они не дублируются.
    """
    owner = session.query(User).filter(User.role == "owner").first()
    workers = session.query(User).filter(User.role == "worker").all()
    categories = session.query(CategoryService).all()

    all_time_slots = []
    for day_offset in range(7):
        current_date = start_date + timedelta(days=day_offset)
        weekday_num = current_date.weekday()  # 0-ПН, 6-ВС
        weekday_name = WEEKDAYS[weekday_num]

        existing_for_day = session.query(TimeSlot).filter(TimeSlot.date == current_date).first()
        if existing_for_day:
            continue

        if weekday_name in WORK_SCHEDULE["Гадисов Ренат Фамильевич"]["days"]:
            slots = generate_time_slots(
                WORK_SCHEDULE["Гадисов Ренат Фамильевич"]["hours"][0],
                WORK_SCHEDULE["Гадисов Ренат Фамильевич"]["hours"][1],
                WORK_SCHEDULE["Гадисов Ренат Фамильевич"]["duration"],
                current_date,
                workers[0].id,
                categories[0].id
            )
            all_time_slots.extend(slots)

        if weekday_name in WORK_SCHEDULE["Сергеев Ринат Леонидович"]["days"]:
            slots = generate_time_slots(
                WORK_SCHEDULE["Сергеев Ринат Леонидович"]["hours"][0],
                WORK_SCHEDULE["Сергеев Ринат Леонидович"]["hours"][1],
                WORK_SCHEDULE["Сергеев Ринат Леонидович"]["duration"],
                current_date,
                owner.id,
                categories[1].id
            )
            all_time_slots.extend(slots)

        if weekday_name in WORK_SCHEDULE["Бареева Светлана Геннадьевна"]["days"]:
            slots = generate_time_slots(
                WORK_SCHEDULE["Бареева Светлана Геннадьевна"]["hours"][0],
                WORK_SCHEDULE["Бареева Светлана Геннадьевна"]["hours"][1],
                WORK_SCHEDULE["Бареева Светлана Геннадьевна"]["duration"],
                current_date,
                workers[1].id,
                categories[2].id
            )
            all_time_slots.extend(slots)

        if weekday_name in WORK_SCHEDULE["Шарипова Альфия Маратовна"]["days"]:
            slots = generate_time_slots(
                WORK_SCHEDULE["Шарипова Альфия Маратовна"]["hours"][0],
                WORK_SCHEDULE["Шарипова Альфия Маратовна"]["hours"][1],
                WORK_SCHEDULE["Шарипова Альфия Маратовна"]["duration"],
                current_date,
                workers[2].id,
                categories[2].id
            )
            all_time_slots.extend(slots)

    if all_time_slots:
        session.add_all(all_time_slots)
        session.commit()
        logger.info(f"Добавлены временные слоты для недели, начинающейся {start_date}")


def refresh_weekly_slots():
    """
    Функция, запускаемая раз в неделю по расписанию (каждое воскресенье),
    чтобы сгенерировать временные слоты на следующую неделю.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        today = date.today()
        # Если сегодня воскресенье, то хотим именно следующий понедельник:
        # next_monday = сегодня + 1 день
        if today.weekday() == 6:
            next_monday = today + timedelta(days=1)
        else:
            # Иначе: найти ближайший следующий понедельник
            next_monday = today + timedelta(days=(7 - today.weekday()))
        logger.info(f"Запуск еженедельного создания слотов. Следующий понедельник: {next_monday}")
        generate_week_slots(session, next_monday)
    except Exception as e:
        logger.error(f"Ошибка при еженедельном обновлении слотов: {e}")
    finally:
        session.close()


def initialize_db_and_slots():
    """
    Вызывается при старте сервиса: создаёт базовые данные,
    затем генерирует либо текущую неделю, либо следующую (если сегодня воскресенье),
    а потом запускает планировщик.
    """
    wait_for_db(engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Таблицы созданы успешно!")

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        create_initial_data(session)

        today = date.today()
        # Если сегодня воскресенье, формируем сразу слоты на следующую неделю
        if today.weekday() == 6:
            current_monday = today + timedelta(days=1)
        else:
            # иначе — понедельник текущей недели
            current_monday = today - timedelta(days=today.weekday())
        logger.info(f"Создание слотов для недели (понедельник = {current_monday})")
        generate_week_slots(session, current_monday)

    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Инициализация БД и данных (включая слоты)
    initialize_db_and_slots()

    # Планировщик: каждое воскресенье в 00:00
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_weekly_slots,
        trigger='cron',
        day_of_week='sun',
        hour=0,
        minute=0
    )
    scheduler.start()
    logger.info("Планировщик запущен. Слоты будут обновляться каждое воскресенье.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Планировщик остановлен, сервис завершает работу.")
