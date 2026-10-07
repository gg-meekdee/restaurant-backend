from sqlalchemy import Column, Date, Integer
from app.models.base import Base

class DailyCounter(Base):
    __tablename__ = "daily_counters"

    date = Column(Date, primary_key=True)
    last_number = Column(Integer, nullable=False, default=0)