from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.deps import get_current_user
from app.models.user import User
from app.models.access_request import AccessRequest
from app.models.message_description import MessageDescription
from app.models.notification import Notification
from app.services.audit_service import log_action
from app.database import get_db

router = APIRouter()


class AccessRequestCreate(BaseModel):
    message_description_id: int
    action_requested: str  # 'update' | 'delete'
    reason: Optional[str] = None


class AccessRequestResponse(BaseModel):
    id: int
    user_id: int
    requester_username: Optional[str] = None
    message_description_id: int
    md_file_name: Optional[str] = None
    action_requested: str
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewer_username: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


def _enrich(r: AccessRequest) -> AccessRequestResponse:
    resp = AccessRequestResponse.model_validate(r)
    resp.requester_username = r.requester.username if r.requester else None
    resp.reviewer_username = r.reviewer.username if r.reviewer else None
    # Snapshot first — survives the MD itself being deleted later (see the
    # model's ondelete='SET NULL'); live relationship is just a fallback
    # for rows that predate the snapshot column.
    resp.md_file_name = r.md_file_name_snapshot or (r.message_description.file_name if r.message_description else None)
    return resp


@router.post("/", response_model=AccessRequestResponse, status_code=status.HTTP_201_CREATED)
def create_access_request(
    payload: AccessRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.action_requested not in ("update", "delete"):
        raise HTTPException(status_code=400, detail="action_requested must be 'update' or 'delete'")

    md = db.query(MessageDescription).filter(MessageDescription.id == payload.message_description_id).first()
    if not md:
        raise HTTPException(status_code=404, detail="Message Description not found")
    if not md.approved:
        raise HTTPException(status_code=400, detail="Only approved Message Descriptions need an access request — this one is still a draft you can edit freely.")

    req = AccessRequest(
        user_id=current_user.id,
        message_description_id=md.id,
        md_file_name_snapshot=md.file_name,
        action_requested=payload.action_requested,
        reason=payload.reason,
        status="pending",
    )
    db.add(req)
    log_action(
        db, current_user, action="request_access", entity_type="MessageDescription",
        entity_id=md.id,
        details=f"Requested {payload.action_requested} access to \"{md.file_name}\""
    )

    admins = db.query(User).filter(User.is_admin.is_(True)).all()
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            message=f"{current_user.username} requested {payload.action_requested} access to \"{md.file_name}\"",
            link="/admin?tab=access"
        ))

    db.commit()
    db.refresh(req)
    return _enrich(req)


@router.get("/", response_model=List[AccessRequestResponse])
def list_access_requests(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admins see every request (review queue); regular users see only
    their own (so they can check on something they asked for)."""
    query = db.query(AccessRequest)
    if not current_user.is_admin:
        query = query.filter(AccessRequest.user_id == current_user.id)
    if status_filter:
        query = query.filter(AccessRequest.status == status_filter)
    requests = query.order_by(AccessRequest.created_at.desc()).all()
    return [_enrich(r) for r in requests]


@router.post("/{request_id}/approve", response_model=AccessRequestResponse)
def approve_access_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only an administrator can grant access requests.")

    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    req.status = "approved"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)

    md_name = req.md_file_name_snapshot or 'a Message Description'
    db.add(Notification(
        user_id=req.user_id,
        message=f"Your request to {req.action_requested} \"{md_name}\" "
                f"was approved by {current_user.username}. You can now {req.action_requested} it — this permission is single-use.",
        link="/message-descriptions"
    ))
    log_action(
        db, current_user, action="grant_access", entity_type="MessageDescription",
        entity_id=req.message_description_id,
        details=f"Granted {req.action_requested} access to {req.requester.username if req.requester else req.user_id} for \"{md_name}\""
    )
    db.commit()
    db.refresh(req)
    return _enrich(req)


@router.post("/{request_id}/deny", response_model=AccessRequestResponse)
def deny_access_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only an administrator can deny access requests.")

    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    req.status = "denied"
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.now(timezone.utc)

    md_name = req.md_file_name_snapshot or 'a Message Description'
    db.add(Notification(
        user_id=req.user_id,
        message=f"Your request to {req.action_requested} \"{md_name}\" "
                f"was denied by {current_user.username}.",
        link="/message-descriptions"
    ))
    log_action(
        db, current_user, action="deny_access", entity_type="MessageDescription",
        entity_id=req.message_description_id,
        details=f"Denied {req.action_requested} access to {req.requester.username if req.requester else req.user_id} for \"{md_name}\""
    )
    db.commit()
    db.refresh(req)
    return _enrich(req)
