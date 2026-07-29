from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class BusinessVariable(Base):
    """
    Admin-editable business constant (thresholds, feature flags, retention
    periods, currency codes, ...) — these used to only exist hardcoded
    inside every mapping XML's <GlobalVariables> block (see
    xml_mapping_parser.py), re-declared per file, editable only by hand-
    editing XML and restarting the server. This table is the single
    source of truth now; transform_mapping.py's _get_global_variables()
    prefers a DB row over the XML-embedded default of the same name.
    """
    __tablename__ = "business_variables"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    value = Column(String, nullable=False)
    var_type = Column(String, nullable=False, default="STRING")  # STRING | INTEGER | DECIMAL | BOOLEAN
    description = Column(Text, nullable=True)
    currency = Column(String, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updater = relationship("User", foreign_keys=[updated_by])
