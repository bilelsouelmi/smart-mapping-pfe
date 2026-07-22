from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.deps import get_current_user
from app.models.user import User

from app.database import get_db
from app.models.message_description import MessageDescription
from app.models.notification import Notification
from app.models.access_request import AccessRequest
from app.services.audit_service import log_action
from app.schemas.message_description import (
    MessageDescriptionCreate,
    MessageDescriptionUpdate,
    MessageDescriptionResponse
)

router = APIRouter()


def _consume_access_grant(db: Session, current_user: User, db_message_desc: MessageDescription, action: str) -> None:
    """Looks up an approved, not-yet-used AccessRequest for this exact
    (user, Message Description, action) and consumes it — one grant, one
    use, then it's gone, same reasoning as the model's own docstring.
    Raises 403 if none exists. Callers are responsible for having already
    checked current_user.is_admin first (admins never need a grant)."""
    req = db.query(AccessRequest).filter(
        AccessRequest.user_id == current_user.id,
        AccessRequest.message_description_id == db_message_desc.id,
        AccessRequest.action_requested == action,
        AccessRequest.status == "approved"
    ).order_by(AccessRequest.reviewed_at.desc()).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You need admin-granted access to {action} this approved Message Description — request access first."
        )
    req.status = "used"


@router.get("/", response_model=List[MessageDescriptionResponse])
def get_message_descriptions(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère toutes les MessageDescriptions
    """
    message_descriptions = db.query(MessageDescription).offset(skip).limit(limit).all()
    return message_descriptions


@router.get("/pending-approval-count")
def get_pending_approval_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    How many Message Descriptions are waiting for approval — only
    meaningful for admins (they're the only ones who can act on it, see
    the maker-checker gate in update_message_description). Registered
    before /{message_description_id} so FastAPI doesn't try to parse
    "pending-approval-count" as an int path param.
    """
    if not current_user.is_admin:
        return {"count": 0}
    count = db.query(MessageDescription).filter(
        MessageDescription.approved.is_(None),
        MessageDescription.column_structure.isnot(None)
    ).count()
    return {"count": count}


@router.get("/{message_description_id}", response_model=MessageDescriptionResponse)
def get_message_description(
    message_description_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère une MessageDescription par ID
    """
    message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == message_description_id
    ).first()
    
    if not message_desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {message_description_id} not found"
        )
    
    return message_desc


@router.post("/", response_model=MessageDescriptionResponse, status_code=status.HTTP_201_CREATED)
def create_message_description(
    message_desc: MessageDescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crée une nouvelle MessageDescription
    """
    db_message_desc = MessageDescription(
        user_id=current_user.id,
        **message_desc.model_dump()
    )
    
    db.add(db_message_desc)
    db.commit()
    db.refresh(db_message_desc)
    
    return db_message_desc


@router.put("/{message_description_id}", response_model=MessageDescriptionResponse)
def update_message_description(
    message_description_id: int,
    message_desc: MessageDescriptionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Met à jour une MessageDescription
    """
    db_message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == message_description_id
    ).first()
    
    if not db_message_desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {message_description_id} not found"
        )

    # Update fields
    update_data = message_desc.model_dump(exclude_unset=True)

    # Maker-checker: User = Maker (proposes), Admin = Checker (approves).
    # Even an Admin cannot approve their own proposal — segregation of
    # duties is a standard banking control, and self-approval defeats the
    # entire point of a human review gate (see the whole
    # _run_transform_prechecks / validate_file_at_path chain this
    # "approved" flag ultimately guards).
    if update_data.get("approved") is True:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can approve a Message Description."
            )
        if db_message_desc.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You proposed this Message Description — a different admin must approve it (maker-checker)."
            )
        update_data["approved_by"] = current_user.id

    # Editing fields on an ALREADY-approved reference (as opposed to the
    # approve/reject decision itself, handled above) is a change to
    # something other users' Transforms/Validations already rely on —
    # admins can do this directly, anyone else needs an admin to have
    # explicitly granted it via an AccessRequest first (see
    # access_requests.py). Not gated for a still-pending draft (approved
    # is None) — editing your own unreviewed proposal needs no permission.
    if db_message_desc.approved is True and "approved" not in update_data and not current_user.is_admin:
        _consume_access_grant(db, current_user, db_message_desc, "update")

    for field, value in update_data.items():
        setattr(db_message_desc, field, value)

    # Only one MD can be the approved reference per (mt_type, file_type) —
    # approving a new one must retire the previous reference, or Transform's
    # gate and Validate's rule-lookup can silently pick either one.
    if update_data.get("approved") is True:
        db.query(MessageDescription).filter(
            MessageDescription.id != db_message_desc.id,
            MessageDescription.mt_type == db_message_desc.mt_type,
            MessageDescription.file_type == db_message_desc.file_type,
            MessageDescription.approved == True  # noqa: E712
        ).update({"approved": None, "approved_by": None})

        # Close the maker-checker feedback loop: the proposer otherwise
        # never finds out their submission was reviewed, since the
        # decision happens on a different user's screen entirely.
        db.add(Notification(
            user_id=db_message_desc.user_id,
            message=f"Your Message Description \"{db_message_desc.file_name}\" "
                    f"({db_message_desc.mt_type or db_message_desc.file_type}) was approved by {current_user.username}.",
            link="/message-descriptions"
        ))
        log_action(
            db, current_user, action="approve", entity_type="MessageDescription",
            entity_id=db_message_desc.id,
            details=f"Approved \"{db_message_desc.file_name}\" ({db_message_desc.mt_type or db_message_desc.file_type}), proposed by user_id={db_message_desc.user_id}"
        )

    db.commit()
    db.refresh(db_message_desc)

    return db_message_desc


@router.delete("/{message_description_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_description(
    message_description_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprime une MessageDescription
    """
    db_message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == message_description_id
    ).first()
    
    if not db_message_desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {message_description_id} not found"
        )

    # was_approved distinguishes "rejected" (was still pending review)
    # from "deleted" (an approved reference being pulled) for both the
    # notification and the audit entry below — different events even
    # though both currently go through this same DELETE.
    was_approved = db_message_desc.approved is True
    verb = "deleted" if was_approved else "rejected"

    # Deleting an APPROVED reference needs the same admin-or-granted-access
    # gate as editing one (see update_message_description) — a pending
    # draft's own proposer can still freely reject/discard their own
    # unreviewed work, no permission needed.
    if was_approved and not current_user.is_admin:
        _consume_access_grant(db, current_user, db_message_desc, "delete")

    # Notification is only meaningful when someone OTHER than the
    # proposer is the one discarding it — deleting your own draft doesn't
    # need a notification telling you what you just did yourself. The
    # audit entry below logs it either way, since a compliance trail
    # cares about every deletion, self-initiated or not.
    if db_message_desc.user_id != current_user.id:
        db.add(Notification(
            user_id=db_message_desc.user_id,
            message=f"Your Message Description \"{db_message_desc.file_name}\" "
                    f"({db_message_desc.mt_type or db_message_desc.file_type}) was {verb} by {current_user.username}.",
            link="/message-descriptions"
        ))

    log_action(
        db, current_user, action=verb, entity_type="MessageDescription",
        entity_id=db_message_desc.id,
        details=f"{verb.capitalize()} \"{db_message_desc.file_name}\" ({db_message_desc.mt_type or db_message_desc.file_type})"
    )

    db.delete(db_message_desc)
    db.commit()
    
    return None