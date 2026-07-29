from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.deps import get_current_user
from app.models.user import User
from app.models.pending_validation_correction import PendingValidationCorrection
from app.database import get_db

router = APIRouter()


class PendingValidationResponse(BaseModel):
    id: int
    mt_type: str
    file_type: str
    original_filename: str
    errors: list = []
    warnings: list = []
    failed_count: int = 0
    status: str
    submitted_by_username: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _enrich(c: PendingValidationCorrection) -> PendingValidationResponse:
    resp = PendingValidationResponse.model_validate(c)
    resp.submitted_by_username = c.submitter.username if c.submitter else None
    return resp


@router.get("/", response_model=List[PendingValidationResponse])
def list_pending_validations(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admins see every failed-validation record (oversight of who still
    has an outstanding correction); regular users see only their own —
    same visibility pattern as pending_transactions.py."""
    query = db.query(PendingValidationCorrection)
    if not current_user.is_admin:
        query = query.filter(PendingValidationCorrection.submitted_by == current_user.id)
    if status_filter:
        query = query.filter(PendingValidationCorrection.status == status_filter)
    rows = query.order_by(PendingValidationCorrection.created_at.desc()).all()
    return [_enrich(r) for r in rows]


@router.post("/{correction_id}/dismiss", response_model=PendingValidationResponse)
def dismiss_pending_validation(
    correction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Acknowledge a failed validation without fixing it — e.g. the file
    turned out to be a one-off mistake that won't be resubmitted. Only the
    submitter or an admin can dismiss; unlike the approval queues, there's
    no separate approver role here since nobody but the submitter (or an
    admin doing cleanup) has a stake in this record."""
    row = db.query(PendingValidationCorrection).filter(PendingValidationCorrection.id == correction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Validation correction record not found")
    if row.submitted_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your record")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"Already {row.status}")

    row.status = "dismissed"
    row.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _enrich(row)
