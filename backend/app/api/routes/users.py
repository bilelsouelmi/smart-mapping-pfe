from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, Field
from app.database import get_db
from app.core.deps import get_current_user, get_current_active_admin
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


@router.post("/me/change-password")
def change_my_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Self-service password change — requires the CURRENT password, unlike
    the generic PUT /{user_id} (which lets you edit your own profile,
    including password, without re-proving you know the old one). A
    security-sensitive action like this deserves that extra check even
    though the rest of self-editing doesn't need it.
    """
    # current_user comes from get_current_user's OWN Depends(get_db) call,
    # a different Session instance than this route's — mutating it
    # directly and calling db.commit() here silently does nothing, since
    # the object was never attached to db's identity map. Fetch a fresh
    # row through THIS route's own session instead, same as every other
    # write route in this codebase already does.
    user = db.query(User).filter(User.id == current_user.id).first()
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.get("/", response_model=List[UserResponse])
def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Récupère tous les utilisateurs (admin uniquement).
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/pending", response_model=List[UserResponse])
def get_pending_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Récupère les utilisateurs en attente d'approbation (admin uniquement).
    """
    users = db.query(User).filter(User.is_active == False).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère un utilisateur par ID.
    Les utilisateurs peuvent voir leur propre profil,
    les admins peuvent voir tous les profils.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Check permissions
    if user.id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Met à jour un utilisateur.
    Les utilisateurs peuvent modifier leur propre profil,
    les admins peuvent modifier tous les profils.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Check permissions
    if user.id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)

    # Privilege fields — only an admin may set these, even though this
    # same route also lets a user edit their OWN profile (self-service
    # fields like full_name/password). Without this guard, a regular
    # user editing themselves could hand themselves is_admin=True.
    privileged_fields = ("is_active", "is_admin", "is_compliance_officer")
    if not current_user.is_admin:
        for field in privileged_fields:
            update_data.pop(field, None)

    # Hash password if provided
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/approve", response_model=UserResponse)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Approuve un compte utilisateur en attente (admin uniquement).
    Active le compte en mettant is_active=True.
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )

    user.is_active = True
    db.commit()
    db.refresh(user)

    return user


@router.post("/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Rejette et supprime un compte utilisateur en attente (admin uniquement).
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already active user"
        )

    db.delete(user)
    db.commit()
    return None


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Supprime un utilisateur (admin uniquement).
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()
    return None