from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class WatchlistEntity(Base):
    """
    A sanctions or PEP (Politically Exposed Person) watchlist entry —
    the actual data the SANCTIONS_SCREENING_ENABLED / PEP_SCREENING_ENABLED
    business variables gate (see transform_mapping.py's
    _check_sanctions_and_pep).

    Maker-checker on both add AND remove, same reasoning as the
    Message Description workflow: a single compliance officer
    unilaterally deleting a sanctions entry (letting a previously-blocked
    party through) is exactly the kind of action that needs a second,
    DIFFERENT compliance officer's sign-off — self-approval is blocked
    the same way it is for Message Descriptions.

    status:
      pending_add    - proposed, not yet screened against (inactive)
      active         - approved, enforced by the screening check
      pending_remove - removal requested but NOT YET confirmed — still
                       enforced (see the screening query's status filter)
                       so a single officer can't silently disable a hit
                       just by requesting its removal
      rejected       - an add proposal was rejected; inactive, kept for
                       the audit trail rather than hard-deleted
    """
    __tablename__ = "watchlist_entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    list_type = Column(String, nullable=False)  # SANCTIONS | PEP
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending_add")
    proposed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    proposer = relationship("User", foreign_keys=[proposed_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
