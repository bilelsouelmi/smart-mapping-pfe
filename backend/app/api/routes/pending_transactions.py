from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

from app.core.deps import get_current_user
from app.models.user import User
from app.models.pending_transaction import PendingTransactionApproval, PendingTransactionApprovalVote
from app.models.notification import Notification
from app.services.audit_service import log_action
from app.config import settings
from app.database import get_db

router = APIRouter()

OUTPUT_DIR = Path(settings.UPLOAD_DIR).parent / "outputs"


class PendingTransactionResponse(BaseModel):
    id: int
    mt_type: str
    reference: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    output_filename: str
    required_approvals: int
    approvals_received: int = 0
    approver_role: str = "admin"
    pending_reason: Optional[str] = None
    status: str
    submitted_by_username: Optional[str] = None
    approver_usernames: List[str] = []
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _enrich(t: PendingTransactionApproval) -> PendingTransactionResponse:
    resp = PendingTransactionResponse.model_validate(t)
    resp.submitted_by_username = t.submitter.username if t.submitter else None
    resp.approvals_received = len(t.votes)
    resp.approver_usernames = [v.approver.username for v in t.votes if v.approver]
    return resp


def _is_eligible_approver(txn: PendingTransactionApproval, user: User) -> bool:
    """Whether user's role matches what this hold requires — large-amount
    holds need is_admin, PEP holds need is_compliance_officer. Self-approval
    is checked separately by the callers."""
    if txn.approver_role == "compliance_officer":
        return bool(user.is_compliance_officer)
    return bool(user.is_admin)


@router.get("/", response_model=List[PendingTransactionResponse])
def list_pending_transactions(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admins see every admin-role hold, compliance officers see every
    compliance-role hold (each is that queue's approval authority); everyone
    also sees their own submissions regardless of role — same visibility
    pattern as access requests, so a submitter can check on something
    they're waiting on."""
    query = db.query(PendingTransactionApproval)
    if not (current_user.is_admin or current_user.is_compliance_officer):
        query = query.filter(PendingTransactionApproval.submitted_by == current_user.id)
    elif current_user.is_admin and not current_user.is_compliance_officer:
        query = query.filter(
            (PendingTransactionApproval.approver_role == "admin") |
            (PendingTransactionApproval.submitted_by == current_user.id)
        )
    elif current_user.is_compliance_officer and not current_user.is_admin:
        query = query.filter(
            (PendingTransactionApproval.approver_role == "compliance_officer") |
            (PendingTransactionApproval.submitted_by == current_user.id)
        )
    if status_filter:
        query = query.filter(PendingTransactionApproval.status == status_filter)
    transactions = query.order_by(PendingTransactionApproval.created_at.desc()).all()
    return [_enrich(t) for t in transactions]


@router.post("/{transaction_id}/approve", response_model=PendingTransactionResponse)
def approve_pending_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    txn = db.query(PendingTransactionApproval).filter(PendingTransactionApproval.id == transaction_id).with_for_update().first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not _is_eligible_approver(txn, current_user):
        required = "Compliance officer" if txn.approver_role == "compliance_officer" else "Admin"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{required} access required")
    if txn.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transaction is already {txn.status}")
    if txn.submitted_by == current_user.id:
        raise HTTPException(status_code=403, detail="You submitted this transaction — a different approver must review it")

    vote = PendingTransactionApprovalVote(transaction_id=txn.id, approver_id=current_user.id)
    db.add(vote)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="You already approved this transaction")

    votes_count = db.query(PendingTransactionApprovalVote).filter(
        PendingTransactionApprovalVote.transaction_id == txn.id
    ).count()

    log_action(
        db, current_user, action="approve_transaction", entity_type="PendingTransactionApproval",
        entity_id=txn.id,
        details=f"Approved \"{txn.output_filename}\" ({votes_count}/{txn.required_approvals} approvals)"
    )

    if votes_count >= txn.required_approvals:
        txn.status = "approved"
        txn.resolved_at = datetime.utcnow()
        if txn.submitted_by:
            db.add(Notification(
                user_id=txn.submitted_by,
                message=f"Your held transaction \"{txn.output_filename}\" ({txn.amount} {txn.currency}) is now fully approved and ready to download.",
                link="/pending-transactions"
            ))

    db.commit()
    db.refresh(txn)
    return _enrich(txn)


@router.post("/{transaction_id}/reject", response_model=PendingTransactionResponse)
def reject_pending_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    txn = db.query(PendingTransactionApproval).filter(PendingTransactionApproval.id == transaction_id).with_for_update().first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not _is_eligible_approver(txn, current_user):
        required = "Compliance officer" if txn.approver_role == "compliance_officer" else "Admin"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{required} access required")
    if txn.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transaction is already {txn.status}")
    if txn.submitted_by == current_user.id:
        raise HTTPException(status_code=403, detail="You submitted this transaction — a different approver must review it")

    txn.status = "rejected"
    txn.resolved_at = datetime.utcnow()
    log_action(
        db, current_user, action="reject_transaction", entity_type="PendingTransactionApproval",
        entity_id=txn.id, details=f"Rejected \"{txn.output_filename}\""
    )
    if txn.submitted_by:
        db.add(Notification(
            user_id=txn.submitted_by,
            message=f"Your held transaction \"{txn.output_filename}\" ({txn.amount} {txn.currency}) was rejected by {current_user.username}.",
            link="/pending-transactions"
        ))

    output_path = OUTPUT_DIR / txn.output_filename
    if output_path.exists():
        output_path.unlink()

    db.commit()
    db.refresh(txn)
    return _enrich(txn)


@router.get("/{transaction_id}/download")
def download_pending_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    txn = db.query(PendingTransactionApproval).filter(PendingTransactionApproval.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not _is_eligible_approver(txn, current_user) and txn.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not your transaction")
    if txn.status != "approved":
        raise HTTPException(status_code=400, detail=f"Not yet approved (status: {txn.status})")

    output_path = OUTPUT_DIR / txn.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file no longer exists")

    # Held transactions come from both directions — MT->XML output is
    # .xml, the XML->MT reverse direction produces flat .txt MT text.
    media_type = "text/plain" if txn.output_filename.endswith(".txt") else "application/xml"
    return FileResponse(path=str(output_path), filename=txn.output_filename, media_type=media_type)
