from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.standard_element import StandardElement
from app.schemas.standard_element import (
    StandardElementCreate,
    StandardElementUpdate,
    StandardElementResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[StandardElementResponse])
async def list_standard_elements(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    business_domain: Optional[str] = None,
    is_active: Optional[bool] = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Liste tous les éléments standards avec filtres optionnels
    """
    query = db.query(StandardElement)
    
    if category:
        query = query.filter(StandardElement.category == category)
    
    if business_domain:
        query = query.filter(StandardElement.business_domain == business_domain)
    
    if is_active is not None:
        query = query.filter(StandardElement.is_active == is_active)
    
    elements = query.offset(skip).limit(limit).all()
    return elements


@router.get("/search", response_model=List[StandardElementResponse])
async def search_standard_elements(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recherche d'éléments par nom, ID ou description
    """
    search_pattern = f"%{q}%"
    
    elements = db.query(StandardElement).filter(
        (StandardElement.element_name.ilike(search_pattern)) |
        (StandardElement.element_id.ilike(search_pattern)) |
        (StandardElement.description.ilike(search_pattern)) |
        (StandardElement.source_path.ilike(search_pattern)) |
        (StandardElement.target_path.ilike(search_pattern))
    ).limit(50).all()
    
    return elements


@router.get("/categories", response_model=List[dict])
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Liste toutes les catégories disponibles avec compteurs
    """
    from sqlalchemy import func
    
    categories = db.query(
        StandardElement.category,
        func.count(StandardElement.id).label('count')
    ).group_by(
        StandardElement.category
    ).all()
    
    return [
        {"category": cat, "count": count}
        for cat, count in categories
    ]


@router.get("/{element_id}", response_model=StandardElementResponse)
async def get_standard_element(
    element_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère un élément standard par ID
    """
    element = db.query(StandardElement).filter(
        StandardElement.id == element_id
    ).first()
    
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StandardElement {element_id} not found"
        )
    
    return element


@router.get("/by-code/{element_code}", response_model=StandardElementResponse)
async def get_by_code(
    element_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère un élément par son code (element_id)
    """
    element = db.query(StandardElement).filter(
        StandardElement.element_id == element_code
    ).first()
    
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element code {element_code} not found"
        )
    
    return element


@router.post("/", response_model=StandardElementResponse, status_code=status.HTTP_201_CREATED)
async def create_standard_element(
    element: StandardElementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crée un nouvel élément standard
    """
    # Vérifier si l'element_id existe déjà
    existing = db.query(StandardElement).filter(
        StandardElement.element_id == element.element_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Element ID {element.element_id} already exists"
        )
    
    db_element = StandardElement(**element.dict())
    db.add(db_element)
    db.commit()
    db.refresh(db_element)
    
    logger.info(f"Created StandardElement: {db_element.element_id}")
    return db_element


@router.put("/{element_id}", response_model=StandardElementResponse)
async def update_standard_element(
    element_id: int,
    element_update: StandardElementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Met à jour un élément standard
    """
    db_element = db.query(StandardElement).filter(
        StandardElement.id == element_id
    ).first()
    
    if not db_element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StandardElement {element_id} not found"
        )
    
    # Mettre à jour uniquement les champs fournis
    update_data = element_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_element, field, value)
    
    db.commit()
    db.refresh(db_element)
    
    logger.info(f"Updated StandardElement: {db_element.element_id}")
    return db_element


@router.delete("/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_standard_element(
    element_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprime un élément standard (soft delete - is_active = False)
    """
    db_element = db.query(StandardElement).filter(
        StandardElement.id == element_id
    ).first()
    
    if not db_element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StandardElement {element_id} not found"
        )
    
    # Soft delete
    db_element.is_active = False
    db.commit()
    
    logger.info(f"Deleted (soft) StandardElement: {db_element.element_id}")
    return None


@router.post("/{element_id}/increment-usage", response_model=StandardElementResponse)
async def increment_usage(
    element_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Incrémente le compteur d'utilisation d'un élément
    """
    db_element = db.query(StandardElement).filter(
        StandardElement.id == element_id
    ).first()
    
    if not db_element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StandardElement {element_id} not found"
        )
    
    db_element.usage_count += 1
    db.commit()
    db.refresh(db_element)
    
    return db_element