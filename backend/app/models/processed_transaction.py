from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ProcessedTransaction(Base):
    """
    One row per successfully-transformed MT103 — the actual data behind
    duplicate detection (see transform_mapping.py's
    _check_duplicate_reference). The dataset's own <Conditions> block for
    MAPPING_01 (field :20: -> MsgId) documents exactly this:
    "NOT exists_in_processed_messages(formatted_msg_id, today) -> PROCEED
    else REJECT with error 'Duplicate message ID detected'" — until now
    nothing implemented exists_in_processed_messages(); this table +
    that check are the implementation, scoped by DUPLICATE_DETECTION_WINDOW_DAYS.
    """
    __tablename__ = "processed_transactions"

    id = Column(Integer, primary_key=True, index=True)
    mt_type = Column(String, nullable=False, index=True)
    reference = Column(String, nullable=False, index=True)  # trimmed :20:
    file_name = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
