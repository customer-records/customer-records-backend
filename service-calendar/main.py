import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError
from dotenv import load_dotenv
from fastapi import Response
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from models import Base, CategoryService, TimeSlot, User, OnlineRegistration, Client, CompanyDescription  # Импорт всех моделей
import httpx
from ics import Calendar, Event
# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Создаем FastAPI приложение
app = FastAPI()

# Настройка CORS для разрешения запросов с любых источников
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели для запросов и ответов API
class ServiceResponse(BaseModel):
    id: int
    name_category: str
    services_array: List[str]
    time_width_minutes_end: int

class TimeSlotResponse(BaseModel):
    id: int
    date: str
    time_start: str
    time_end: str
    service_name: str
    specialist_name: str

class SpecialistResponse(BaseModel):
    id: int
    role: str
    name: str
    last_name: str
    sur_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    category_name: Optional[str] = None
    category_id: Optional[int] = None

class BookingRequest(BaseModel):
    time_slot_id: int
    client_id: int 
    company_id: int
    employer_id: int 

class BookingResponse(BaseModel):
    booking_id: int
    time_slot_id: int
    client_id: int
    company_id: int
    employer_id: int
    date_time_create: datetime
    status: str

class CompanyResponse(BaseModel):
    id: int
    company_name: str
    company_description: str
    company_adress_full: str
    time_work_start: str
    time_work_end: str
    work_days: List[str]

# Настройка базы данных
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
logger.info(f"Подключение к базе данных по URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

wait_for_db(engine)

@app.post("/bookings/", response_class=Response)
def create_booking(booking: BookingRequest, db: Session = Depends(get_db)):
    """
    Создание бронирования временного слота, генерация ICS-файла и отправка уведомлений
    """
    try:
        # 1. Проверяем существование слота, клиента, компании и специалиста
        time_slot = db.query(TimeSlot).filter(TimeSlot.id == booking.time_slot_id).first()
        if not time_slot:
            raise HTTPException(status_code=404, detail="Time slot not found")

        client = db.query(Client).filter(Client.id == booking.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        company = db.query(CompanyDescription).filter(CompanyDescription.id == booking.company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        employer = db.query(User).filter(User.id == booking.employer_id).first()
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")

        # 2. Проверяем, что слот ещё не забронирован
        existing_booking = db.query(OnlineRegistration).filter(
            OnlineRegistration.id_time_slot == booking.time_slot_id
        ).first()
        if existing_booking:
            raise HTTPException(status_code=400, detail="This time slot is already booked")

        # 3. Получаем информацию об услуге
        service = db.query(CategoryService).filter(
            CategoryService.id == time_slot.id_category_service
        ).first()

        # 4. Создаём запись в базе
        new_booking = OnlineRegistration(
            id_client=booking.client_id,
            id_employer=booking.employer_id,
            id_time_slot=booking.time_slot_id,
            id_adress_company=booking.company_id,
            date_time_create=datetime.utcnow()
        )
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)

        # 5. Подготавливаем данные для уведомлений
        booking_data = {
            "client_name": f"{client.name} {client.last_name or ''}",
            "phone": client.phone_number,
            "appointment_date": time_slot.date.strftime("%d.%m.%Y"),
            "appointment_time": time_slot.time_start.strftime("%H:%M"),
            "service_name": service.name_category if service else "Не указана",
            "specialist_name": f"{employer.name} {employer.last_name}"
        }

        logger.info(
            "Новая запись создана:\n"
            f"  Дата: {time_slot.date}\n"
            f"  Время: {time_slot.time_start}\n"
            f"  Клиент: {booking_data['client_name']} (тел.: {booking_data['phone']})\n"
            f"  Услуга: {booking_data['service_name']}\n"
            f"  Специалист: {booking_data['specialist_name']}"
        )

        # 6. Отправка в телеграм-бот (если настроено)
        try:
            bot_service_url = f"http://{os.getenv('TELEGRAM_BOT_SERVICE')}/send-appointment"
            with httpx.Client(timeout=5.0) as client_http:
                resp = client_http.post(bot_service_url, json=booking_data)
                if resp.status_code != 200:
                    logger.error(f"Ошибка отправки в телеграм-бот: {resp.text}")
        except Exception as e:
            logger.error(f"Не удалось отправить данные в телеграм-бот: {e}")

        # 7. Отправка WhatsApp-уведомления
        try:
            whatsapp_url = os.getenv("WHATSAPP_SERVICE_URL")  # например "http://localhost:7001"
            with httpx.Client(timeout=5.0) as client_http:
                resp = client_http.post(
                    f"http://{whatsapp_url}/send-notification",
                    json=booking_data
                )
                if resp.status_code != 200:
                    logger.error(f"WhatsApp notification failed: {resp.text}")
        except Exception as e:
            logger.error(f"Error when sending WhatsApp notification: {e}")

        # 8. Генерация ICS-файла
        start_dt = datetime.combine(time_slot.date, time_slot.time_start)
        end_dt = start_dt + timedelta(minutes=service.time_width_minutes_end)
        calendar = Calendar()
        event = Event()
        event.name = f"Запись на приём: {service.name_category}"
        event.begin = start_dt
        event.end = end_dt
        event.description = (
            f"Клиент: {client.name} {client.last_name or ''}\n"
            f"Специалист: {employer.name} {employer.last_name}\n"
            f"Услуга: {service.name_category}"
        )
        event.location = (
            f"{company.company_adress_city}, "
            f"{company.company_adress_street} {company.company_adress_house_number}"
        )
        calendar.events.add(event)
        ics_content = str(calendar)

        headers = {
            "Content-Disposition": f"attachment; filename=appointment_{new_booking.id}.ics",
            "Content-Type": "text/calendar"
        }
        return Response(content=ics_content, media_type="text/calendar", headers=headers)

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Ошибка целостности данных при бронировании: {e}")
        raise HTTPException(status_code=400, detail="Data integrity error occurred while creating booking")

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании бронирования: {e}")
        raise HTTPException(status_code=500, detail="Internal server error occurred while creating booking")


@app.get("/services/", response_model=List[ServiceResponse])
def get_all_services(db: Session = Depends(get_db)):
    """Получение списка всех услуг с их подуслугами"""
    try:
        services = db.query(CategoryService).all()
        return [
            ServiceResponse(
                id=service.id,
                name_category=service.name_category,
                services_array=service.services_array or [],
                time_width_minutes_end=service.time_width_minutes_end
            ) for service in services
        ]
    except Exception as e:
        logger.error(f"Ошибка при получении списка услуг: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
from zoneinfo import ZoneInfo

@app.get("/timeslots/{date}", response_model=List[TimeSlotResponse])
def get_time_slots_by_date(date: str, db: Session = Depends(get_db)):
    """Получение всех доступных и актуальных временных слотов на конкретную дату (по московскому времени)"""
    try:
        logger.info(f"Запрос слотов на дату: {date}")

        # Устанавливаем московский часовой пояс
        moscow_tz = ZoneInfo("Europe/Moscow")
        now_moscow = datetime.now(tz=moscow_tz)
        logger.info(f"Текущее московское время: {now_moscow.isoformat()}")

        # Парсим дату из строки
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        # Получаем список занятых слотов
        booked_slot_ids = db.query(OnlineRegistration.id_time_slot).join(
            TimeSlot, OnlineRegistration.id_time_slot == TimeSlot.id
        ).filter(TimeSlot.date == target_date).all()
        booked_slot_ids = {slot.id_time_slot for slot in booked_slot_ids}

        # Фильтры для слотов
        filters = [
            TimeSlot.date == target_date,
            ~TimeSlot.id.in_(booked_slot_ids)
        ]

        # Исключаем прошедшие слоты, если сегодня
        if target_date == now_moscow.date():
            filters.append(TimeSlot.time_start > now_moscow.time())

        slots = db.query(TimeSlot, CategoryService, User).join(
            CategoryService, TimeSlot.id_category_service == CategoryService.id
        ).join(
            User, TimeSlot.id_employer == User.id
        ).filter(*filters).all()

        result = []
        for time_slot, category_service, user in slots:
            time_start = time_slot.time_start.strftime("%H:%M")
            duration = category_service.time_width_minutes_end
            time_end = (
                datetime.combine(datetime.min, time_slot.time_start) +
                timedelta(minutes=duration)
            ).time().strftime("%H:%M")

            result.append(TimeSlotResponse(
                id=time_slot.id,
                date=time_slot.date.strftime("%Y-%m-%d"),
                time_start=time_start,
                time_end=time_end,
                service_name=category_service.name_category,
                specialist_name=f"{user.name} {user.last_name}"
            ))

        return result

    except Exception as e:
        logger.error(f"Ошибка при получении слотов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    
@app.get("/specialists/", response_model=List[SpecialistResponse])
def get_all_specialists(category_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Получение списка всех специалистов клиники с возможностью фильтрации по category_id"""
    try:
        query = db.query(
            User,
            CategoryService.name_category
        ).outerjoin(
            CategoryService, User.id_category_service == CategoryService.id
        ).filter(
            User.role.in_(["worker", "owner"])
        )

        # Если указан category_id, добавляем фильтрацию
        if category_id is not None:
            query = query.filter(User.id_category_service == category_id)

        specialists = query.all()

        return [
            SpecialistResponse(
                id=user.id,
                role=user.role,
                name=user.name,
                last_name=user.last_name,
                sur_name=user.sur_name,
                email=user.email or None,
                phone_number=user.phone_number,
                category_name=category_name,
                category_id=user.id_category_service
            ) for user, category_name in specialists
        ]
    except Exception as e:
        logger.error(f"Ошибка при получении списка специалистов: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/company/", response_model=CompanyResponse)
def get_company_info(db: Session = Depends(get_db)):
    """Получение информации о компании"""
    try:
        company = db.query(CompanyDescription).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Формируем полный адрес
        address_parts = [
            company.company_adress_country,
            company.company_adress_city,
            company.company_adress_street,
            company.company_adress_house_number
        ]
        full_address = ", ".join(filter(None, address_parts))
        
        # Формируем список рабочих дней
        work_days = []
        weekdays = [
            ("weekdays_work_1", "Понедельник"),
            ("weekdays_work_2", "Вторник"),
            ("weekdays_work_3", "Среда"),
            ("weekdays_work_4", "Четверг"),
            ("weekdays_work_5", "Пятница"),
            ("weekdays_work_6", "Суббота"),
            ("weekdays_work_7", "Воскресенье")
        ]
        
        for attr, day_name in weekdays:
            if getattr(company, attr):
                work_days.append(day_name)
        
        return CompanyResponse(
            id=company.id,
            company_name=company.company_name,
            company_description=company.company_description,
            company_adress_full=full_address,
            time_work_start=company.time_work_start.strftime("%H:%M"),
            time_work_end=company.time_work_end.strftime("%H:%M"),
            work_days=work_days
        )
    except Exception as e:
        logger.error(f"Ошибка при получении информации о компании: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/")
def read_root():
    logger.info("Обработан запрос к корневому маршруту")
    return {"message": "Добро пожаловать в систему управления стоматологической клиникой Denta - rell!"}