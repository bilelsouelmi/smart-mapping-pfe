from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    """
    Append-only record of who did what, when — the compliance trail this
    project's own dataset formulas keep referencing ("AUDIT_RETENTION_YEARS",
    "logged for SOX financial controls") but never actually implemented
    until now.

    username is denormalized (stored as text, not just user_id) so the
    trail stays readable even if a user account is later deleted — the
    same reasoning as Notification.message. entity_id is nullable and
    NOT a foreign key on purpose: the row being logged (a Message
    Description, a Mapping, ...) is very often deleted moments later
    (reject = delete), and an audit entry must survive that.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
