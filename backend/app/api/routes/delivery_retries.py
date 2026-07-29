from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.config_consommation_routes import _deliver_to_config_out, get_config_model
from app.core.deps import get_current_user, get_db
from app.config import settings
from app.models.pending_delivery_retry import PendingDeliveryRetry
from app.models.user import User

router = APIRouter()

OUTPUT_DIR = Path(settings.UPLOAD_DIR).parent / "outputs"


class DeliveryRetryResponse(BaseModel):
    id: int
    pipeline_id: Optional[int] = None
    pipeline_name: str
    config_out_id: Optional[int] = None
    transport_type: str
    output_filename: str
    error_message: Optional[str] = None
    attempt_count: int
    status: str
    created_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[DeliveryRetryResponse])
def list_delivery_retries(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Same visibility as the Pipeline/Config routes this feeds off of —
    open to any authenticated user, not admin-gated, since pipeline
    management itself isn't restricted either."""
    query = db.query(PendingDeliveryRetry)
    if status_filter:
        query = query.filter(PendingDeliveryRetry.status == status_filter)
    return query.order_by(PendingDeliveryRetry.created_at.desc()).all()


@router.post("/{retry_id}/retry", response_model=DeliveryRetryResponse)
async def retry_delivery(
    retry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Redeliver the SAME already-transformed output — never re-consumes or
    re-transforms anything, just resends the audit-copy file through
    _deliver_to_config_out (the exact same delivery code a normal pipeline
    run uses). Looks the Config OUT up FRESH from the database rather than
    trusting anything cached on this row, since the whole point of a retry
    is usually that someone just fixed the destination's URL/credentials.
    """
    row = db.query(PendingDeliveryRetry).filter(PendingDeliveryRetry.id == retry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Delivery retry record not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"Already {row.status}")

    output_path = OUTPUT_DIR / row.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Output file \"{row.output_filename}\" no longer exists on disk — cannot redeliver.")

    TransportConfig = get_config_model()
    config_out = db.query(TransportConfig).filter(TransportConfig.id == row.config_out_id).first() if row.config_out_id else None
    if not config_out:
        raise HTTPException(status_code=400, detail="The original Config OUT for this delivery no longer exists.")

    output_body = output_path.read_bytes()
    input_filename_base = output_path.stem
    iso_target_name = "xml" if output_body.strip().startswith(b"<?xml") else "mt"

    new_status, message = await _deliver_to_config_out(config_out, output_body, input_filename_base, iso_target_name)

    row.attempt_count += 1
    row.last_attempt_at = datetime.utcnow()
    row.error_message = message
    if new_status == "ok":
        row.status = "delivered"
        row.resolved_at = datetime.utcnow()
    # else: stays "pending" — the row's updated error_message/attempt_count
    # already reflect this latest failed try, ready for another retry.

    db.commit()
    db.refresh(row)
    return row


@router.post("/{retry_id}/abandon", response_model=DeliveryRetryResponse)
def abandon_delivery_retry(
    retry_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Give up on redelivering this one — e.g. the destination is
    permanently gone. Doesn't delete the audit-copy file; only stops it
    from cluttering the pending queue."""
    row = db.query(PendingDeliveryRetry).filter(PendingDeliveryRetry.id == retry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Delivery retry record not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail=f"Already {row.status}")

    row.status = "abandoned"
    row.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
