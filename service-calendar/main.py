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
from datetime import datetime, timedelta, date as _date
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

# Схемы для CRUD управления слотами (административные)
class AdminTimeSlotCreate(BaseModel):
    id_category_service: int
    id_employer: int
    date: str            # формат "YYYY-MM-DD"
    time_start: str      # формат "HH:MM"

class AdminTimeSlotUpdate(BaseModel):
    id_category_service: Optional[int] = None
    id_employer: Optional[int] = None
    date: Optional[str] = None
    time_start: Optional[str] = None

class AdminTimeSlotResponse(BaseModel):
    id: int
    id_category_service: int
    id_employer: int
    date: str
    time_start: str
    time_end: str

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
    """
    Возвращает доступные слоты на дату (МСК):
    - прошедшие даты → []
    - сегодня     → только future-slots
    - будущее     → все слоты
    """
    # 1. Текущее московское время
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_moscow = datetime.now(moscow_tz)
    # переводим в наивное время без tzinfo
    naive_now = now_moscow.replace(tzinfo=None).time()

    # 2. Парсим target_date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # 3. Если дата в прошлом — сразу пустой список
    if target_date < now_moscow.date():
        return []

    # 4. Собираем занятые слоты
    booked = (
        db.query(OnlineRegistration.id_time_slot)
          .join(TimeSlot, OnlineRegistration.id_time_slot == TimeSlot.id)
          .filter(TimeSlot.date == target_date)
          .scalars()
          .all()
    )
    booked_ids = set(booked)

    # 5. Формируем фильтры
    filters = [
        TimeSlot.date == target_date,
        ~TimeSlot.id.in_(booked_ids)
    ]
    # если сегодня — отсекаем уже прошедшие
    if target_date == now_moscow.date():
        filters.append(TimeSlot.time_start > naive_now)

    # 6. Делаем запрос
    rows = (
        db.query(TimeSlot, CategoryService, User)
          .join(CategoryService, TimeSlot.id_category_service == CategoryService.id)
          .join(User,         TimeSlot.id_employer          == User.id)
          .filter(*filters)
          .all()
    )

    # 7. Собираем ответ
    result: List[TimeSlotResponse] = []
    for ts, svc, usr in rows:
        start = ts.time_start.strftime("%H:%M")
        end   = (datetime.combine(datetime.min, ts.time_start)
                 + timedelta(minutes=svc.time_width_minutes_end)
                ).time().strftime("%H:%M")

        result.append(TimeSlotResponse(
            id               = ts.id,
            date             = ts.date.strftime("%Y-%m-%d"),
            time_start       = start,
            time_end         = end,
            service_name     = svc.name_category,
            specialist_name  = f"{usr.name} {usr.last_name}"
        ))

    return result
    
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

@app.get("/admin/timeslots/", response_model=List[AdminTimeSlotResponse])
def read_all_slots(db: Session = Depends(get_db)):
    """
    Возвращает все временные слоты (для администратора), включая вычисленное time_end.
    """
    slots = db.query(TimeSlot).all()
    result = []
    for slot in slots:
        # вычисляем time_end
        service = db.query(CategoryService).filter(CategoryService.id == slot.id_category_service).first()
        duration = service.time_width_minutes_end if service else 0
        end_time = (datetime.combine(_date.min, slot.time_start) + timedelta(minutes=duration)).time().strftime("%H:%M")
        result.append(AdminTimeSlotResponse(
            id=slot.id,
            id_category_service=slot.id_category_service,
            id_employer=slot.id_employer,
            date=slot.date.strftime("%Y-%m-%d"),
            time_start=slot.time_start.strftime("%H:%M"),
            time_end=end_time
        ))
    return result

@app.get("/admin/timeslots/{slot_id}/", response_model=AdminTimeSlotResponse)
def read_slot(slot_id: int, db: Session = Depends(get_db)):
    """
    Возвращает один временной слот по ID (для администратора).
    """
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="TimeSlot not found")
    service = db.query(CategoryService).filter(CategoryService.id == slot.id_category_service).first()
    duration = service.time_width_minutes_end if service else 0
    end_time = (datetime.combine(_date.min, slot.time_start) + timedelta(minutes=duration)).time().strftime("%H:%M")
    return AdminTimeSlotResponse(
        id=slot.id,
        id_category_service=slot.id_category_service,
        id_employer=slot.id_employer,
        date=slot.date.strftime("%Y-%m-%d"),
        time_start=slot.time_start.strftime("%H:%M"),
        time_end=end_time
    )

@app.post("/admin/timeslots/", response_model=AdminTimeSlotResponse, status_code=201)
def create_slot(payload: AdminTimeSlotCreate, db: Session = Depends(get_db)):
    """
    Создание нового временного слота (для администратора).
    """
    # Проверяем, что работник существует и его роль
    employer = db.query(User).filter(User.id == payload.id_employer).first()
    if not employer or employer.role not in ("worker", "owner"):
        raise HTTPException(status_code=404, detail="Employer not found or not a worker/owner")

    # Проверяем, что услуга существует
    service = db.query(CategoryService).filter(CategoryService.id == payload.id_category_service).first()
    if not service:
        raise HTTPException(status_code=404, detail="CategoryService not found")

    # Проверяем формат даты и времени
    try:
        slot_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
        slot_time = datetime.strptime(payload.time_start, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format. Date: YYYY-MM-DD, Time: HH:MM")

    # Проверяем коллизию: один и тот же работник, дата, время начала
    conflict = db.query(TimeSlot).filter(
        TimeSlot.id_employer == payload.id_employer,
        TimeSlot.date == slot_date,
        TimeSlot.time_start == slot_time
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="TimeSlot already exists for this employer at this datetime")

    # Сохраняем новый слот
    new_slot = TimeSlot(
        id_category_service=payload.id_category_service,
        id_employer=payload.id_employer,
        date=slot_date,
        time_start=slot_time,
        id_time_width_minutes_end=payload.id_category_service
    )
    db.add(new_slot)
    db.commit()
    db.refresh(new_slot)

    # Вычисляем time_end
    duration = service.time_width_minutes_end
    end_time = (datetime.combine(_date.min, slot_time) + timedelta(minutes=duration)).time().strftime("%H:%M")

    return AdminTimeSlotResponse(
        id=new_slot.id,
        id_category_service=new_slot.id_category_service,
        id_employer=new_slot.id_employer,
        date=new_slot.date.strftime("%Y-%m-%d"),
        time_start=new_slot.time_start.strftime("%H:%M"),
        time_end=end_time
    )

@app.put("/admin/timeslots/{slot_id}/", response_model=AdminTimeSlotResponse)
def update_slot(slot_id: int, payload: AdminTimeSlotUpdate, db: Session = Depends(get_db)):
    """
    Редактирование существующего временного слота (для администратора).
    """
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="TimeSlot not found")

    # Новые значения или старые, если не переданы
    new_category = payload.id_category_service if payload.id_category_service is not None else slot.id_category_service
    new_employer = payload.id_employer if payload.id_employer is not None else slot.id_employer
    new_date_str = payload.date if payload.date is not None else slot.date.strftime("%Y-%m-%d")
    new_time_str = payload.time_start if payload.time_start is not None else slot.time_start.strftime("%H:%M")

    # Проверяем, что работник существует, если меняется
    if payload.id_employer is not None:
        emp = db.query(User).filter(User.id == new_employer).first()
        if not emp or emp.role not in ("worker", "owner"):
            raise HTTPException(status_code=404, detail="Employer not found or not a worker/owner")

    # Проверяем, что услуга существует, если меняется
    if payload.id_category_service is not None:
        svc = db.query(CategoryService).filter(CategoryService.id == new_category).first()
        if not svc:
            raise HTTPException(status_code=404, detail="CategoryService not found")
    else:
        svc = db.query(CategoryService).filter(CategoryService.id == slot.id_category_service).first()

    # Проверяем формат даты и времени
    try:
        slot_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
        slot_time = datetime.strptime(new_time_str, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format. Date: YYYY-MM-DD, Time: HH:MM")

    # Проверяем коллизию: тот же работник, та же дата, то же время, другой ID
    conflict = db.query(TimeSlot).filter(
        TimeSlot.id_employer == new_employer,
        TimeSlot.date == slot_date,
        TimeSlot.time_start == slot_time,
        TimeSlot.id != slot.id
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Another TimeSlot already exists at this datetime")

    # Применяем изменения
    slot.id_category_service = new_category
    slot.id_employer = new_employer
    slot.date = slot_date
    slot.time_start = slot_time
    slot.id_time_width_minutes_end = new_category

    db.commit()
    db.refresh(slot)

    # Вычисляем time_end
    duration = svc.time_width_minutes_end
    end_time = (datetime.combine(_date.min, slot_time) + timedelta(minutes=duration)).time().strftime("%H:%M")

    return AdminTimeSlotResponse(
        id=slot.id,
        id_category_service=slot.id_category_service,
        id_employer=slot.id_employer,
        date=slot.date.strftime("%Y-%m-%d"),
        time_start=slot.time_start.strftime("%H:%M"),
        time_end=end_time
    )

@app.delete("/admin/timeslots/{slot_id}/", status_code=204)
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    """
    Удаление временного слота (для администратора).
    """
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="TimeSlot not found")
    db.delete(slot)
    db.commit()
    return Response(status_code=204)

@app.get("/")
def read_root():
    logger.info("Обработан запрос к корневому маршруту")
    return {"message": "Добро пожаловать в систему управления стоматологической клиникой Denta - rell!"}
