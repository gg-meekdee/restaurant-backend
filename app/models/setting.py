from sqlalchemy import Column, String
from app.models.base import Base

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)