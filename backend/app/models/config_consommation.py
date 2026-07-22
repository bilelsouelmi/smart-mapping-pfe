from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship


class ConfigConsommation(Base):
    __tablename__ = "config_consommations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    config_in_id = Column(Integer, ForeignKey("transport_configs.id"), nullable=False)
    mapping_id = Column(Integer, ForeignKey("mappings.id"), nullable=False)
    config_out_id = Column(Integer, ForeignKey("transport_configs.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    config_in = relationship("TransportConfig", foreign_keys="[ConfigConsommation.config_in_id]", lazy="joined")
    config_out = relationship("TransportConfig", foreign_keys="[ConfigConsommation.config_out_id]", lazy="joined")
    mapping = relationship("Mapping", foreign_keys="[ConfigConsommation.mapping_id]", lazy="joined")