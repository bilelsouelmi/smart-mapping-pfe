from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.deps import get_current_user
from app.models.user import User

from app.database import get_db
from app.models.message_description import MessageDescription
from app.schemas.message_description import (
    MessageDescriptionCreate,
    MessageDescriptionUpdate,
    MessageDescriptionResponse
)

router = APIRouter()


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
    for field, value in update_data.items():
        setattr(db_message_desc, field, value)
    
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
    
    db.delete(db_message_desc)
    db.commit()
    
    return None