from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User

# Security scheme
security = HTTPBearer()


def get_db() -> Generator:
    """
    Dependency pour obtenir une session database
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency pour obtenir l'utilisateur courant à partir du JWT token
    
    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur n'existe pas
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[int] = payload.get("sub")
    
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency pour vérifier que l'utilisateur est admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_current_admin_or_compliance(
    current_user: User = Depends(get_current_user)
) -> User:
    """Admin OR compliance officer — for reports/dashboards that are
    compliance's own deliverable (regulatory export, SLA dashboard), not
    an admin-only oversight tool like the raw Audit Log page."""
    if not (current_user.is_admin or current_user.is_compliance_officer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or compliance officer access required"
        )
    return current_user