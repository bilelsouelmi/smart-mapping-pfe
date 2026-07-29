from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PendingDeliveryRetry(Base):
    """
    A pipeline run whose Config OUT step (the delivery to REST/RabbitMQ/
    Kafka/FILE) failed — see config_consommation_routes.py's
    _execute_pipeline. The transform itself already succeeded by the time
    this row is created (the "audit copy" this points to, in outputs/, is
    proof the mapping ran fine); only DELIVERY failed, so retrying means
    resending that same already-transformed content, never re-consuming
    or re-transforming.

    This matters most for a RabbitMQ/Kafka-sourced Config IN: those
    messages are acknowledged/consumed from the source queue the moment
    they're read (see Config IN's basic_get/consumer.close()), so if
    delivery then fails, the message is already gone from the source —
    without this row and its audit-copy file, that transform would be
    silently lost forever with no way to redeliver it. A FILE-sourced
    Config IN doesn't have this problem (the source file is only moved to
    processed/ on a clean success), but gets a row here too for the same
    "come back and see what's stuck" visibility.
    """
    __tablename__ = "pending_delivery_retries"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("config_consommations.id"), nullable=True)
    pipeline_name = Column(String, nullable=False)
    config_out_id = Column(Integer, ForeignKey("transport_configs.id"), nullable=True)
    transport_type = Column(String, nullable=False)  # REST | RABBITMQ | KAFKA | FILE
    output_filename = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="pending")  # pending | delivered | abandoned
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    pipeline = relationship("ConfigConsommation", foreign_keys=[pipeline_id])
    config_out = relationship("TransportConfig", foreign_keys=[config_out_id])
