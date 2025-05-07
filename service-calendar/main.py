import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, IntegrityError
from dotenv import load_dotenv
import os
import time
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from models import Base, CategoryService, TimeSlot, User, OnlineRegistration, Client, CompanyDescription  # Импорт всех моделей
import httpx

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

@app.post("/bookings/", response_model=BookingResponse)
def create_booking(booking: BookingRequest, db: Session = Depends(get_db)):
    """
    Создание бронирования временного слота
    """
    try:
        # Проверяем существование временного слота
        time_slot = db.query(TimeSlot).filter(TimeSlot.id == booking.time_slot_id).first()
        if not time_slot:
            raise HTTPException(status_code=404, detail="Time slot not found")

        # Проверяем существование клиента
        client = db.query(Client).filter(Client.id == booking.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Проверяем существование компании
        company = db.query(CompanyDescription).filter(CompanyDescription.id == booking.company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Проверяем существование сотрудника
        employer = db.query(User).filter(User.id == booking.employer_id).first()
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")

        # Проверяем, не занят ли уже этот слот
        existing_booking = db.query(OnlineRegistration).filter(
            OnlineRegistration.id_time_slot == booking.time_slot_id
        ).first()
        
        if existing_booking:
            raise HTTPException(
                status_code=400,
                detail="This time slot is already booked"
            )

        # Получаем информацию об услуге
        service = db.query(CategoryService).filter(
            CategoryService.id == time_slot.id_category_service
        ).first()

        # Создаем новую запись бронирования
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

        booking_data = {
            "client_name": f"{client.name} {client.last_name or ''}",
            "phone": client.phone_number,
            "appointment_date": str(time_slot.date),
            "appointment_time": time_slot.time_start.strftime("%H:%M"),
            "service_name": service.name_category if service else "Не указана",
            "specialist_name": f"{employer.name} {employer.last_name}"
        }

        # Логируем детали записи
        logger.info(
            "Новая запись создана:\n"
            f"Дата: {time_slot.date}\n"
            f"Время: {time_slot.time_start}\n"
            f"Клиент: {booking_data['client_name']} (тел.: {booking_data['phone']})\n"
            f"Услуга: {booking_data['service_name']}\n"
            f"Специалист: {booking_data['specialist_name']}"
        )

        # Отправляем данные в сервис телеграм-бота
        try:
            bot_service_url = f"http://{os.getenv('TELEGRAM_BOT_SERVICE')}/send-appointment"
            with httpx.Client() as client:
                response = client.post(
                    bot_service_url,
                    json=booking_data,
                    timeout=5.0
                )
                if response.status_code != 200:
                    logger.error(f"Ошибка отправки в телеграм-бот: {response.text}")
        except Exception as e:
            logger.error(f"Не удалось отправить данные в телеграм-бот: {str(e)}")

        return BookingResponse(
            booking_id=new_booking.id,
            time_slot_id=new_booking.id_time_slot,
            client_id=new_booking.id_client,
            company_id=new_booking.id_adress_company,
            employer_id=new_booking.id_employer,
            date_time_create=new_booking.date_time_create,
            status="success"
        )

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Ошибка целостности данных при бронировании: {e}")
        raise HTTPException(
            status_code=400,
            detail="Data integrity error occurred while creating booking"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании бронирования: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred while creating booking"
        )

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

@app.get("/timeslots/{date}", response_model=List[TimeSlotResponse])
def get_time_slots_by_date(date: str, db: Session = Depends(get_db)):
    """Получение всех доступных временных слотов на конкретную дату"""
    try:
        logger.info(f"Запрос слотов на дату: {date}")
        
        # Парсим дату из строки
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            logger.info(f"Дата успешно преобразована: {target_date}")
        except ValueError as ve:
            logger.error(f"Ошибка формата даты: {ve}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Получаем текущее время на сервере
        now = datetime.now()
        current_time = now.time()
        current_date = now.date()
        
        # Получаем список занятых слотов на указанную дату
        booked_slot_ids = db.query(OnlineRegistration.id_time_slot).join(
            TimeSlot, OnlineRegistration.id_time_slot == TimeSlot.id
        ).filter(
            TimeSlot.date == target_date
        ).all()
        booked_slot_ids = {slot.id_time_slot for slot in booked_slot_ids}
        
        # Базовый запрос для свободных слотов
        query = db.query(
            TimeSlot,
            CategoryService,
            User
        ).join(
            CategoryService, TimeSlot.id_category_service == CategoryService.id
        ).join(
            User, TimeSlot.id_employer == User.id
        ).filter(
            TimeSlot.date == target_date,
            ~TimeSlot.id.in_(booked_slot_ids)  # Исключаем занятые слоты
        )
        
        # Если запрашивается сегодняшняя дата, добавляем фильтр по времени
        if target_date == current_date:
            query = query.filter(TimeSlot.time_start >= current_time)
            logger.info(f"Применена фильтрация по текущему времени: {current_time}")
        
        slots = query.all()
        logger.info(f"Найдено свободных слотов: {len(slots)}")

        result = []
        for slot in slots:
            time_slot, category_service, user = slot
            
            time_start = time_slot.time_start
            duration = category_service.time_width_minutes_end
            
            # Вычисляем время окончания
            time_end = (datetime.combine(datetime.min, time_start) + 
                      timedelta(minutes=duration)).time()
            
            result.append(TimeSlotResponse(
                id=time_slot.id,
                date=time_slot.date.strftime("%Y-%m-%d"),
                time_start=time_start.strftime("%H:%M"),
                time_end=time_end.strftime("%H:%M"),
                service_name=category_service.name_category,
                specialis_name=f"{user.name} {user.last_name}"
            ))
        
        if not result:
            logger.info("Нет доступных слотов на указанную дату")
        
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