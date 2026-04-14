from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class StandardElement(Base):
    __tablename__ = "standard_elements"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    element_id = Column(String(50), unique=True, nullable=False, index=True)
    element_name = Column(String(200), nullable=False)
    
    # Catégorie et domaine
    category = Column(String(100), nullable=False)  # Identity, Address, Contact, Account, Transaction
    business_domain = Column(String(100), nullable=False, default="Banking")
    
    # Paths hiérarchiques
    source_path = Column(String(500), nullable=True)  # Ex: Client.Identity.FirstName
    target_path = Column(String(500), nullable=True)  # Ex: Person.FirstName
    iso20022_path = Column(String(500), nullable=True)  # Ex: pain.001.001.03/Dbtr/Nm
    
    # Type et format
    data_type = Column(String(50), nullable=False)  # string, integer, decimal, date, boolean
    structure_type = Column(String(20), default="simple")  # simple, map, hmap, array, object  ← AJOUTEZ CETTE LIGNE
    format_pattern = Column(String(200), nullable=True)  # Ex: YYYY-MM-DD, +XXX XXXXXXXX
    
    # Description et documentation
    description = Column(Text, nullable=True)
    example_value = Column(String(500), nullable=True)
    
    # Validation rules
    is_required = Column(Boolean, default=False)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    validation_regex = Column(String(500), nullable=True)
    
    # Metadata
    tags = Column(JSON, nullable=True)  # ["pii", "financial", "mandatory"]
    related_elements = Column(JSON, nullable=True)  # [{"id": "PERS_LNAME", "relation": "complement"}]
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    success_rate = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())