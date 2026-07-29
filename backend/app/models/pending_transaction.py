from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PendingTransactionApproval(Base):
    """
    A large-amount MT103 transform held back from release until enough
    admins approve it — multi-level approval by threshold. The XML is
    already generated and sitting in outputs/ by the time this row is
    created (see transform_mapping.py's _check_approval_hold); this row
    just gates whether it's DOWNLOADABLE yet. required_approvals is 1
    above LARGE_AMOUNT_THRESHOLD, 2 above CRITICAL_AMOUNT_THRESHOLD —
    the same tiering the AML flag already uses, just enforced instead of
    only logged.

    Self-approval is blocked the same way as the watchlist: the person
    who submitted the transform (submitted_by) can never be one of the
    approvers, regardless of their role.

    approver_role decides WHO is eligible to vote: 'admin' for the
    large-amount hold, 'compliance_officer' for a PEP hold (see
    transform_mapping.py's PEP branch of the same late hold-creation
    block) — PEP review is a compliance function, not a general admin
    one, the same reasoning that already split watchlist management off
    from plain is_admin.
    """
    __tablename__ = "pending_transaction_approvals"

    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey("mappings.id"), nullable=True)
    mt_type = Column(String, nullable=False)
    reference = Column(String, nullable=True)
    amount = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    output_filename = Column(String, nullable=False)
    required_approvals = Column(Integer, nullable=False, default=1)
    approver_role = Column(String, nullable=False, default="admin")  # admin | compliance_officer
    pending_reason = Column(String, nullable=True)  # human-readable, e.g. "PEP match: JANE DOE"
    status = Column(String, nullable=False, default="pending")  # pending | approved | rejected
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)  # set on approve OR reject — see pending_transactions.py

    submitter = relationship("User", foreign_keys=[submitted_by])
    votes = relationship("PendingTransactionApprovalVote", back_populates="transaction", cascade="all, delete-orphan")


class PendingTransactionApprovalVote(Base):
    """One admin's approval vote — a unique (transaction, approver) pair
    so the same admin can't vote twice to pad the count."""
    __tablename__ = "pending_transaction_approval_votes"
    __table_args__ = (UniqueConstraint('transaction_id', 'approver_id', name='uq_transaction_approver'),)

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("pending_transaction_approvals.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transaction = relationship("PendingTransactionApproval", back_populates="votes")
    approver = relationship("User", foreign_keys=[approver_id])
