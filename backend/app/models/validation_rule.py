from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ValidationRule(Base):
    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    # MT type this rule belongs to
    mt_type = Column(String(20), nullable=False, index=True)  # MT103, MT202, MT940
    
    # Block and field identification
    block_name = Column(String(50), nullable=True)   # block1, block2, block4...
    field_tag = Column(String(50), nullable=True)    # :20, :32A, block1.ApplicationIdentifier
    field_name = Column(String(200), nullable=False) # TransactionReference, ApplicationIdentifier
    
    # Validation rules
    mandatory = Column(Boolean, default=False)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)
    fin_format = Column(String(50), nullable=True)   # 16x, 6!n, 3!a...
    pattern = Column(String(500), nullable=True)     # regex
    element_type = Column(String(50), nullable=True) # STRING, INTEGER, DECIMAL, DATE, CODE
    
    # Meta
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ValidationRule {self.mt_type} {self.field_tag}>"