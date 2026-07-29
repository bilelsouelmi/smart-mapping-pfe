from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.deps import get_current_user
from app.models.user import User
from app.models.watchlist_entity import WatchlistEntity
from app.models.notification import Notification
from app.services.audit_service import log_action
from app.database import get_db

router = APIRouter()

VALID_LIST_TYPES = ("SANCTIONS", "PEP")


class WatchlistEntityCreate(BaseModel):
    name: str
    list_type: str
    notes: Optional[str] = None


class WatchlistEntityResponse(BaseModel):
    id: int
    name: str
    list_type: str
    notes: Optional[str] = None
    status: str
    proposed_by_username: Optional[str] = None
    reviewed_by_username: Optional[str] = None

    class Config:
        from_attributes = True


def _enrich(e: WatchlistEntity) -> WatchlistEntityResponse:
    resp = WatchlistEntityResponse.model_validate(e)
    resp.proposed_by_username = e.proposer.username if e.proposer else None
    resp.reviewed_by_username = e.reviewer.username if e.reviewer else None
    return resp


def _require_compliance_officer(current_user: User):
    if not current_user.is_compliance_officer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compliance Officer access required")


def _notify_other_compliance_officers(db: Session, current_user: User, message: str):
    officers = db.query(User).filter(
        User.is_compliance_officer.is_(True),
        User.id != current_user.id
    ).all()
    for officer in officers:
        db.add(Notification(user_id=officer.id, message=message, link="/watchlist"))


@router.get("/", response_model=List[WatchlistEntityResponse])
def list_watchlist(
    list_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compliance-officer-only, not just admin — a list of sanctioned/PEP
    names (and who's proposed changes to it) is sensitive compliance
    data, scoped to the dedicated role rather than general admin."""
    _require_compliance_officer(current_user)
    query = db.query(WatchlistEntity)
    if list_type:
        query = query.filter(WatchlistEntity.list_type == list_type)
    entities = query.order_by(WatchlistEntity.name).all()
    return [_enrich(e) for e in entities]


@router.post("/", response_model=WatchlistEntityResponse, status_code=status.HTTP_201_CREATED)
def propose_watchlist_entity(
    payload: WatchlistEntityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Proposes adding an entry — inactive (not enforced by screening)
    until a DIFFERENT compliance officer approves it."""
    _require_compliance_officer(current_user)
    if payload.list_type not in VALID_LIST_TYPES:
        raise HTTPException(status_code=400, detail=f"list_type must be one of {VALID_LIST_TYPES}")

    entity = WatchlistEntity(
        name=payload.name.strip().upper(),
        list_type=payload.list_type,
        notes=payload.notes,
        status="pending_add",
        proposed_by=current_user.id,
    )
    db.add(entity)
    log_action(
        db, current_user, action="propose_add", entity_type="WatchlistEntity",
        details=f"Proposed adding \"{entity.name}\" to the {entity.list_type} list"
    )
    _notify_other_compliance_officers(
        db, current_user,
        f"{current_user.username} proposed adding \"{entity.name}\" to the {entity.list_type} watchlist — needs your approval."
    )
    db.commit()
    db.refresh(entity)
    return _enrich(entity)


@router.post("/{entity_id}/request-removal", response_model=WatchlistEntityResponse)
def request_removal(
    entity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Requests removing an ACTIVE entry. Deliberately does NOT take it
    out of enforcement immediately — see the model docstring — a second,
    different compliance officer must confirm before screening actually
    stops using it."""
    _require_compliance_officer(current_user)
    entity = db.query(WatchlistEntity).filter(WatchlistEntity.id == entity_id).with_for_update().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.status != "active":
        raise HTTPException(status_code=400, detail=f"Only an active entry can have removal requested (this one is {entity.status})")

    entity.status = "pending_remove"
    entity.proposed_by = current_user.id
    entity.reviewed_by = None
    entity.reviewed_at = None

    log_action(
        db, current_user, action="propose_remove", entity_type="WatchlistEntity",
        entity_id=entity.id, details=f"Requested removing \"{entity.name}\" from the {entity.list_type} list"
    )
    _notify_other_compliance_officers(
        db, current_user,
        f"{current_user.username} requested removing \"{entity.name}\" from the {entity.list_type} watchlist — needs your confirmation."
    )
    db.commit()
    db.refresh(entity)
    return _enrich(entity)


@router.post("/{entity_id}/approve", response_model=WatchlistEntityResponse)
def approve_watchlist_change(
    entity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approves whichever change is pending (add or remove) — must be a
    DIFFERENT compliance officer than the one who proposed it, same
    self-approval block as Message Descriptions."""
    _require_compliance_officer(current_user)
    entity = db.query(WatchlistEntity).filter(WatchlistEntity.id == entity_id).with_for_update().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.status not in ("pending_add", "pending_remove"):
        raise HTTPException(status_code=400, detail=f"Nothing pending to approve (status is {entity.status})")
    if entity.proposed_by == current_user.id:
        raise HTTPException(status_code=403, detail="You can't approve your own proposal — a different compliance officer must review it")

    if entity.status == "pending_add":
        entity.status = "active"
        entity.reviewed_by = current_user.id
        entity.reviewed_at = datetime.now(timezone.utc)
        log_action(
            db, current_user, action="approve_add", entity_type="WatchlistEntity",
            entity_id=entity.id, details=f"Approved adding \"{entity.name}\" to the {entity.list_type} list"
        )
        if entity.proposed_by:
            db.add(Notification(
                user_id=entity.proposed_by,
                message=f"Your proposal to add \"{entity.name}\" to the {entity.list_type} watchlist was approved by {current_user.username}.",
                link="/watchlist"
            ))
        db.commit()
        db.refresh(entity)
        return _enrich(entity)

    # pending_remove -> confirmed, actually delete
    name, list_type, proposed_by = entity.name, entity.list_type, entity.proposed_by
    log_action(
        db, current_user, action="approve_remove", entity_type="WatchlistEntity",
        entity_id=entity.id, details=f"Confirmed removing \"{name}\" from the {list_type} list"
    )
    if proposed_by:
        db.add(Notification(
            user_id=proposed_by,
            message=f"Your request to remove \"{name}\" from the {list_type} watchlist was confirmed by {current_user.username}.",
            link="/watchlist"
        ))
    db.delete(entity)
    db.commit()
    return WatchlistEntityResponse(id=entity_id, name=name, list_type=list_type, status="removed")


@router.post("/{entity_id}/reject", response_model=WatchlistEntityResponse)
def reject_watchlist_change(
    entity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rejects whichever change is pending. An add proposal becomes
    'rejected' (kept for audit, not enforced); a remove request reverts
    to 'active' (stays enforced) — same self-review block as approve."""
    _require_compliance_officer(current_user)
    entity = db.query(WatchlistEntity).filter(WatchlistEntity.id == entity_id).with_for_update().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.status not in ("pending_add", "pending_remove"):
        raise HTTPException(status_code=400, detail=f"Nothing pending to reject (status is {entity.status})")
    if entity.proposed_by == current_user.id:
        raise HTTPException(status_code=403, detail="You can't review your own proposal — a different compliance officer must review it")

    was_add = entity.status == "pending_add"
    entity.status = "rejected" if was_add else "active"
    entity.reviewed_by = current_user.id
    entity.reviewed_at = datetime.now(timezone.utc)

    action = "reject_add" if was_add else "reject_remove"
    verb = "Rejected adding" if was_add else "Rejected removing"
    log_action(
        db, current_user, action=action, entity_type="WatchlistEntity",
        entity_id=entity.id, details=f"{verb} \"{entity.name}\" ({entity.list_type})"
    )
    if entity.proposed_by:
        outcome = "rejected" if was_add else "denied — the entry stays active"
        db.add(Notification(
            user_id=entity.proposed_by,
            message=f"Your {'proposal to add' if was_add else 'request to remove'} \"{entity.name}\" ({entity.list_type}) was {outcome} by {current_user.username}.",
            link="/watchlist"
        ))
    db.commit()
    db.refresh(entity)
    return _enrich(entity)
