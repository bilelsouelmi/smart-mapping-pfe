from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MappingFormula(Base):
    __tablename__ = "mapping_formulas"

    id = Column(Integer, primary_key=True, index=True)
    message_description_id = Column(Integer, ForeignKey("message_descriptions.id"), nullable=False)
    
    name = Column(String, nullable=False)  # e.g., "Numero to client_id"
    source_column = Column(String, nullable=False)
    target_column = Column(String, nullable=False)
    
    transformation_type = Column(String, nullable=False)  # direct, date_format, name_split, etc.
    transformation_rule = Column(Text, nullable=False)  # Actual transformation logic/code
    
    example_input = Column(String, nullable=True)
    example_output = Column(String, nullable=True)
    
    success_rate = Column(Float, default=0.0)  # 0.0 to 1.0
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relations
    message_description = relationship("MessageDescription", back_populates="mapping_formulas")