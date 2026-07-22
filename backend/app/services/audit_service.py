from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User


def log_action(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
) -> None:
    """
    Records one audit trail entry. Does NOT call db.commit() — callers
    already commit as part of their own transaction (the action being
    logged and its audit record should land together, not as a separate
    round-trip that could succeed/fail independently).
    """
    db.add(AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    ))
