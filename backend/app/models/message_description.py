from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MessageDescription(Base):
    __tablename__ = "message_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # CSV, XML, JSON, Excel
    source_system = Column(String, nullable=True)
    target_system = Column(String, nullable=True)
    business_domain = Column(String, nullable=True)  # Banking, Insurance, etc.
    
    # JSON fields
    column_structure = Column(JSON, nullable=True)  # [{name, type, format}, ...]
    sample_data = Column(JSON, nullable=True)  # Sample rows
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relations
    user = relationship("User", back_populates="message_descriptions")
    mapping_formulas = relationship("MappingFormula", back_populates="message_description", cascade="all, delete-orphan")