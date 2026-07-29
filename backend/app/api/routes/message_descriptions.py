from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.deps import get_current_user
from app.models.user import User

from app.database import get_db
from app.models.message_description import MessageDescription
from app.models.mapping import Mapping
from app.models.pending_transaction import PendingTransactionApproval
from app.models.config import TransportConfig
from app.models.config_consommation import ConfigConsommation
from app.models.notification import Notification
from app.models.access_request import AccessRequest
from app.services.audit_service import log_action
from app.schemas.message_description import (
    MessageDescriptionCreate,
    MessageDescriptionUpdate,
    MessageDescriptionResponse
)

router = APIRouter()


def _detach_mapping_dependents(
    db: Session, md: MessageDescription, action_verb: str, demote_on_conflict: bool = False
) -> bool:
    """Before deleting `md` (which cascades to its Mappings, see the
    model's cascade="all, delete-orphan"), clears dangling references
    from other tables that point at those Mapping rows by id but aren't
    part of that ORM cascade:
      - PendingTransactionApproval.mapping_id (nullable) — informational
        only ("which mapping produced this hold"); the compliance record
        itself must survive, so just the pointer is cleared.
      - TransportConfig.mapping_id (nullable) — unused convenience
        metadata (nothing in the codebase reads it), safe to clear.
      - ConfigConsommation.mapping_id (NOT NULL) — an active pipeline
        that actually needs the mapping to run. Can't silently clear or
        delete that out from under the user: either raises 409 (default,
        for an explicit Reject/Delete action) or, if demote_on_conflict
        (used when a newer MD is superseding this one on approval),
        leaves `md` demoted to a pending draft instead and returns False
        so the new approval never fails over an unrelated old pipeline.
    Returns True if it's safe for the caller to proceed with db.delete(md).
    """
    mapping_ids = [
        m.id for m in db.query(Mapping.id).filter(
            Mapping.message_description_id == md.id
        ).all()
    ]
    if not mapping_ids:
        return True

    blocking_pipelines = db.query(ConfigConsommation.name).filter(
        ConfigConsommation.mapping_id.in_(mapping_ids)
    ).all()
    if blocking_pipelines:
        if demote_on_conflict:
            md.approved = None
            md.approved_by = None
            return False
        names = ", ".join(f'"{n}"' for (n,) in blocking_pipelines)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot {action_verb} this Message Description: its mapping is still used by "
                   f"active pipeline configuration(s) {names}. Remove or reassign "
                   f"{'those pipelines' if len(blocking_pipelines) > 1 else 'that pipeline'} "
                   f"first (Pipeline & Transport page)."
        )

    db.query(PendingTransactionApproval).filter(
        PendingTransactionApproval.mapping_id.in_(mapping_ids)
    ).update({PendingTransactionApproval.mapping_id: None}, synchronize_session=False)
    db.query(TransportConfig).filter(
        TransportConfig.mapping_id.in_(mapping_ids)
    ).update({TransportConfig.mapping_id: None}, synchronize_session=False)
    return True


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
    ).with_for_update().first()

    if not db_message_desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {message_description_id} not found"
        )

    # Update fields
    update_data = message_desc.model_dump(exclude_unset=True)

    # Maker-checker: User = Maker (proposes), Admin = Checker (approves).
    # A non-admin's proposal always needs an admin's review. An admin's
    # OWN proposal can be self-approved, though — unlike the watchlist's
    # dual-control requirement (which has a dedicated Compliance Officer
    # role precisely so two DIFFERENT people can always be found), MD
    # approval is a quality gate on documentation, not a segregation-of-
    # duties control, and admins are already the platform's ultimate
    # trusted authority. Requiring a second admin here just deadlocks a
    # single-admin deployment for no real security benefit.
    if update_data.get("approved") is True:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can approve a Message Description."
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
    # Retiring means DELETING the old one outright, not demoting it back to
    # "pending" — a demoted MD just reappears as a confusing duplicate
    # pending-approval item (this is exactly what caused two near-identical
    # MT103 samples to keep flip-flopping between approved/pending as each
    # was alternately approved).
    if update_data.get("approved") is True:
        superseded = db.query(MessageDescription).filter(
            MessageDescription.id != db_message_desc.id,
            MessageDescription.mt_type == db_message_desc.mt_type,
            MessageDescription.file_type == db_message_desc.file_type,
            MessageDescription.approved == True  # noqa: E712
        ).all()
        for old_md in superseded:
            if _detach_mapping_dependents(db, old_md, "delete", demote_on_conflict=True):
                db.delete(old_md)

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
    ).with_for_update().first()

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
    # unreviewed work, no permission needed. But it IS still their own —
    # without this check, any authenticated user could reject/delete
    # anyone else's still-pending draft.
    if was_approved and not current_user.is_admin:
        _consume_access_grant(db, current_user, db_message_desc, "delete")
    elif not was_approved and not current_user.is_admin and db_message_desc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the proposer or an administrator can reject this Message Description."
        )

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

    action_verb = "reject" if verb == "rejected" else "delete"
    if _detach_mapping_dependents(db, db_message_desc, action_verb):
        db.delete(db_message_desc)
    db.commit()

    return None