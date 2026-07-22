from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    """
    Persistent in-app notification for a single recipient — used to close
    the maker-checker feedback loop: the proposer of a Message Description
    otherwise never finds out whether it was approved or rejected, since
    that decision happens on a completely different user's screen.

    Deliberately just a stored message string rather than a live
    reference to the Message Description it's about — rejection deletes
    the MD entirely, so a notification tied to that row by foreign key
    would go stale (or cascade-delete) the moment it fires.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    link = Column(String, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
