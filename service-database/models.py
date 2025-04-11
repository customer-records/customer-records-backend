from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Date, Time, DateTime, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)  # owner или worker
    email = Column(String, unique=True, nullable=True)
    password = Column(String, nullable=True)
    name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    sur_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=False)
    date_time_created = Column(DateTime, default=datetime.utcnow)
    date_time_edited = Column(DateTime, onupdate=datetime.utcnow)
    id_category_service = Column(Integer, ForeignKey("category_service.id"), nullable=True)
    google_api_key = Column(String, nullable=True)
    google_client_id = Column(String, nullable=True)
    google_calendar_id = Column(String, nullable=True)
    google_token_autorization = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)  # Новое поле: ID чата Telegram
    tg_name = Column(String, nullable=True)  # Новое поле: Имя в Telegram
    
    category_service = relationship("CategoryService", back_populates="users")
    time_slots = relationship("TimeSlot", back_populates="employer")
    online_registrations = relationship("OnlineRegistration", back_populates="employer")

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=True)
    password = Column(String, nullable=True)
    name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    sur_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=False)
    whatsapp = Column(String, nullable=True)
    tg_name = Column(String, nullable=True)
    chat_id = Column(String, nullable=True)  # Новое поле: ID чата Telegram
    
    online_registrations = relationship("OnlineRegistration", back_populates="client")

class OnlineRegistration(Base):
    __tablename__ = "online_registration"

    id = Column(Integer, primary_key=True, index=True)
    id_client = Column(Integer, ForeignKey("clients.id"))
    id_employer = Column(Integer, ForeignKey("users.id"))
    id_time_slot = Column(Integer, ForeignKey("time_slot.id"))
    date_time_create = Column(DateTime, default=datetime.utcnow)
    date_time_edit = Column(DateTime, onupdate=datetime.utcnow)
    id_adress_company = Column(Integer, ForeignKey("company_description.id"))
    
    client = relationship("Client", back_populates="online_registrations")
    employer = relationship("User", back_populates="online_registrations")
    time_slot = relationship("TimeSlot", back_populates="online_registrations")
    company = relationship("CompanyDescription", back_populates="online_registrations")

class CompanyDescription(Base):
    __tablename__ = "company_description"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    company_description = Column(String, nullable=True)
    company_adress_country = Column(String, nullable=False)
    company_adress_city = Column(String, nullable=False)
    company_adress_street = Column(String, nullable=False)
    company_adress_house_number = Column(String, nullable=False)
    company_adress_house_number_index = Column(String, nullable=False)
    time_work_start = Column(Time, nullable=False)
    time_work_end = Column(Time, nullable=False)
    weekdays_work_1 = Column(Boolean, default=False)
    weekdays_work_2 = Column(Boolean, default=False)
    weekdays_work_3 = Column(Boolean, default=False)
    weekdays_work_4 = Column(Boolean, default=False)
    weekdays_work_5 = Column(Boolean, default=False)
    weekdays_work_6 = Column(Boolean, default=False)
    weekdays_work_7 = Column(Boolean, default=False)
    
    online_registrations = relationship("OnlineRegistration", back_populates="company")

class TimeSlot(Base):
    __tablename__ = "time_slot"

    id = Column(Integer, primary_key=True, index=True)
    id_category_service = Column(Integer, ForeignKey("category_service.id"))
    id_employer = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, nullable=False)
    time_start = Column(Time, nullable=False)
    id_time_width_minutes_end = Column(Integer, ForeignKey("category_service.id"))
    
    category_service = relationship("CategoryService", foreign_keys=[id_category_service], back_populates="time_slots")
    employer = relationship("User", back_populates="time_slots")
    time_width = relationship("CategoryService", foreign_keys=[id_time_width_minutes_end], back_populates="time_width_slots")
    online_registrations = relationship("OnlineRegistration", back_populates="time_slot")

class CategoryService(Base):
    __tablename__ = "category_service"

    id = Column(Integer, primary_key=True, index=True)
    name_category = Column(String, nullable=False)
    time_width_minutes_end = Column(Integer, nullable=False)
    services_array = Column(ARRAY(String), nullable=True)
    
    users = relationship("User", back_populates="category_service")
    time_slots = relationship("TimeSlot", foreign_keys="[TimeSlot.id_category_service]", back_populates="category_service")
    time_width_slots = relationship("TimeSlot", foreign_keys="[TimeSlot.id_time_width_minutes_end]", back_populates="time_width")