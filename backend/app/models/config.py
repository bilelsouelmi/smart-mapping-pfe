"""
Config IN/OUT Models
Supports: FILE, REST, RABBITMQ, KAFKA
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class TransportType(str, enum.Enum):
    FILE     = "FILE"
    REST     = "REST"
    RABBITMQ = "RABBITMQ"
    KAFKA    = "KAFKA"


class ConfigDirection(str, enum.Enum):
    IN  = "IN"
    OUT = "OUT"


class TransportConfig(Base):
    __tablename__ = "transport_configs"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String(100), nullable=False)
    direction    = Column(Enum(ConfigDirection), nullable=False)
    transport_type = Column(Enum(TransportType), nullable=False)
    mapping_id   = Column(Integer, ForeignKey("mappings.id"), nullable=True)
    is_active    = Column(Boolean, default=True)
    description  = Column(Text, nullable=True)

    # ── FILE ──────────────────────────────────────────────────────────────────
    file_path        = Column(String(500), nullable=True)
    file_pattern     = Column(String(100), nullable=True, default="*.txt,*.xml")
    file_output_path = Column(String(500), nullable=True)

    # ── REST (web service) ────────────────────────────────────────────────────
    rest_url        = Column(String(500), nullable=True)
    rest_method     = Column(String(10),  nullable=True, default="POST")
    rest_headers    = Column(JSONB,       nullable=True)
    rest_auth_type  = Column(String(50),  nullable=True)   # NONE, BASIC, BEARER
    rest_auth_value = Column(String(500), nullable=True)

    # ── RABBITMQ ──────────────────────────────────────────────────────────────
    rabbitmq_host        = Column(String(200), nullable=True, default="localhost")
    rabbitmq_port        = Column(Integer,     nullable=True, default=5672)
    rabbitmq_vhost       = Column(String(100), nullable=True, default="/")
    rabbitmq_username    = Column(String(100), nullable=True, default="guest")
    rabbitmq_password    = Column(String(100), nullable=True, default="guest")
    rabbitmq_queue       = Column(String(200), nullable=True)
    rabbitmq_exchange    = Column(String(200), nullable=True, default="")
    rabbitmq_routing_key = Column(String(200), nullable=True)

    # ── KAFKA ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers = Column(String(500), nullable=True)   # e.g. localhost:9092
    kafka_topic             = Column(String(200), nullable=True)
    kafka_group_id          = Column(String(200), nullable=True, default="smart-mapping-group")
    kafka_security_protocol = Column(String(50),  nullable=True, default="PLAINTEXT")
    kafka_sasl_mechanism    = Column(String(50),  nullable=True, default="PLAIN")
    kafka_sasl_username     = Column(String(100), nullable=True)
    kafka_sasl_password     = Column(String(100), nullable=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    mapping = relationship("Mapping", foreign_keys=[mapping_id])