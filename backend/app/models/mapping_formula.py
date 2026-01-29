from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class MappingFormula(Base):
    __tablename__ = "mapping_formulas"

    id = Column(Integer, primary_key=True, index=True)
    message_description_id = Column(Integer, ForeignKey("message_descriptions.id", ondelete="CASCADE"))
    
    name = Column(String(200), nullable=False)
    
    # Chemins hiérarchiques au lieu de colonnes simples
    source_path = Column(String(500), nullable=False)  # Ex: "Body.Client.Identity.FirstName"
    target_path = Column(String(500), nullable=False)  # Ex: "CustomerData.Person.FirstName"
    
    # Niveaux de profondeur
    source_level = Column(Integer, default=1)  # 1, 2, ou 3
    target_level = Column(Integer, default=1)
    
    transformation_type = Column(String(50), nullable=False)
    transformation_rule = Column(Text, nullable=False)
    
    example_input = Column(String(500), nullable=True)
    example_output = Column(String(500), nullable=True)
    
    success_rate = Column(Float, default=0.0)
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationship
    message_description = relationship("MessageDescription", back_populates="mapping_formulas")