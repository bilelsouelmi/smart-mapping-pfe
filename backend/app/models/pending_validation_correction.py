from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PendingValidationCorrection(Base):
    """
    A record of a transform attempt that was blocked by
    _run_transform_prechecks's validation gate (transform_mapping.py) —
    the file still gets rejected immediately, same as before, but instead
    of the errors only ever existing in a toast the user dismisses, they
    land here so the submitter (or an admin) can come back, see exactly
    what failed, and know a correction is still outstanding.

    Unlike PendingTransactionApproval, nobody else needs to approve
    anything here — the only actions are the submitter fixing their file
    (which auto-resolves the matching pending row on the next successful
    transform of the same mt_type/file_type, see transform_mapping.py's
    _resolve_pending_validation_corrections) or dismissing it outright.
    """
    __tablename__ = "pending_validation_corrections"

    id = Column(Integer, primary_key=True, index=True)
    mt_type = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    errors = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=True, default=list)
    failed_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")  # pending | resolved | dismissed
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    submitter = relationship("User", foreign_keys=[submitted_by])
