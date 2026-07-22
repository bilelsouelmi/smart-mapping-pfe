from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class MappingStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class MappingElementStatus(str, enum.Enum):
    PENDING = "pending"
    MAPPED = "mapped"
    SKIPPED = "skipped"


class Mapping(Base):
    __tablename__ = "mappings"

    id = Column(Integer, primary_key=True, index=True)
    message_description_id = Column(Integer, ForeignKey("message_descriptions.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(200), nullable=False)
    source = Column(String(100), nullable=False)   # mt_type e.g. MT103
    target = Column(String(100), nullable=False)   # iso_target e.g. pacs.008.001.08
    status = Column(Enum(MappingStatus), default=MappingStatus.DRAFT)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    message_description = relationship("MessageDescription", back_populates="mappings")
    mapping_elements = relationship("MappingElement", back_populates="mapping", cascade="all, delete-orphan")


class MappingElement(Base):
    __tablename__ = "mapping_elements"

    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey("mappings.id", ondelete="CASCADE"), nullable=False)
    msg_desc_element_id = Column(Integer, ForeignKey("message_description_elements.id", ondelete="SET NULL"), nullable=True)
    mapping_formula_id = Column(Integer, ForeignKey("mapping_formulas.id", ondelete="SET NULL"), nullable=True)

    source_field = Column(String(500), nullable=False)   # field tag e.g. :20:
    source_xpath = Column(String(500), nullable=True)    # XML xpath if applicable
    target_field = Column(String(500), nullable=False)   # ISO 20022 field e.g. GrpHdr/MsgId
    target_xpath = Column(String(500), nullable=True)    # XML xpath in target

    expression = Column(Text, nullable=True)             # formula expression applied
    is_mandatory = Column(Boolean, default=False)
    default_value = Column(String(500), nullable=True)
    status = Column(Enum(MappingElementStatus), default=MappingElementStatus.PENDING)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    mapping = relationship("Mapping", back_populates="mapping_elements")
    msg_desc_element = relationship("MessageDescriptionElement")
    mapping_formula = relationship("MappingFormula")