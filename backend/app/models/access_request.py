from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AccessRequest(Base):
    """
    A regular user's request for permission to update or delete an
    ALREADY-APPROVED Message Description — admins can always do this
    directly, but a non-admin needs an admin to explicitly grant it for
    that specific record and action first (see the enforcement in
    message_descriptions.py's update/delete routes).

    One-time-use by design: approval doesn't open a standing permission
    window, it authorizes exactly one action, consumed (status ->
    'used') the moment it's exercised — the same "specific, logged,
    single-use authorization" pattern real banking change-control uses,
    rather than a broad or time-limited grant that's harder to reason
    about after the fact.
    """
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ondelete='SET NULL': granting/denying/using a request must survive
    # the Message Description itself later being deleted (reject = delete,
    # or an admin pulling an approved reference) — a compliance record of
    # "who asked for what, when, and what an admin decided" shouldn't
    # vanish or block that deletion just because its subject is gone.
    # md_file_name_snapshot below is what keeps it readable afterward,
    # same reasoning as Notification.message elsewhere in this project.
    message_description_id = Column(Integer, ForeignKey("message_descriptions.id", ondelete="SET NULL"), nullable=True)
    md_file_name_snapshot = Column(String, nullable=True)
    action_requested = Column(String, nullable=False)  # 'update' | 'delete'
    reason = Column(Text, nullable=True)

    # pending -> approved -> used, or pending -> denied
    status = Column(String, nullable=False, default="pending")
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requester = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    message_description = relationship("MessageDescription")
