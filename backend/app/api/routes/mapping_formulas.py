from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging
from app.core.deps import get_current_user
from app.models.user import User

from app.database import get_db
from app.models.mapping_formula import MappingFormula
from app.models.message_description import MessageDescription
from app.schemas.mapping_formula import (
    MappingFormulaCreate,
    MappingFormulaUpdate,
    MappingFormulaResponse
)
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
llm_service = LLMService()
rag_service = RAGService()


@router.get("/", response_model=List[MappingFormulaResponse])
def get_mapping_formulas(
    message_description_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère toutes les MappingFormulas (optionnellement filtrées par MessageDescription)
    """
    query = db.query(MappingFormula)
    
    if message_description_id:
        query = query.filter(MappingFormula.message_description_id == message_description_id)
    
    formulas = query.offset(skip).limit(limit).all()
    return formulas


@router.get("/{formula_id}", response_model=MappingFormulaResponse)
def get_mapping_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère une MappingFormula par ID
    """
    formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    
    if not formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found"
        )
    
    return formula


@router.post("/", response_model=MappingFormulaResponse, status_code=status.HTTP_201_CREATED)
def create_mapping_formula(
    formula: MappingFormulaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crée une nouvelle MappingFormula
    """
    # Verify MessageDescription exists
    message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == formula.message_description_id
    ).first()
    
    if not message_desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {formula.message_description_id} not found"
        )
    
    db_formula = MappingFormula(**formula.model_dump())
    
    db.add(db_formula)
    db.commit()
    db.refresh(db_formula)
    
    # Add to RAG knowledge base
    try:
        rag_service.add_mapping(
            mapping_id=f"mapping_{db_formula.id}",
            source_column=db_formula.source_column,
            target_column=db_formula.target_column,
            transformation_type=db_formula.transformation_type,
            transformation_rule=db_formula.transformation_rule,
            business_domain=message_desc.business_domain,
            success_rate=db_formula.success_rate
        )
        logger.info(f"Added MappingFormula {db_formula.id} to RAG knowledge base")
    except Exception as e:
        logger.warning(f"Failed to add to RAG: {e}")
    
    return db_formula


@router.post("/suggest", response_model=Dict[str, Any])
def suggest_mappings(
    message_description_id: int = Body(...),
    target_columns: List[str] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Suggère des mappings pour une MessageDescription vers des colonnes cibles
    
    Utilise l'IA (Ollama) + RAG (ChromaDB) pour des suggestions intelligentes
    """
    try:
        # Get MessageDescription
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == message_description_id
        ).first()
        
        if not message_desc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MessageDescription {message_description_id} not found"
            )
        
        # Extract source columns from column_structure
        source_columns = [col['name'] for col in message_desc.column_structure] if message_desc.column_structure else []
        
        if not source_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MessageDescription has no column structure"
            )
        
        logger.info(f"Suggesting mappings from {len(source_columns)} source columns to {len(target_columns)} target columns")
        
        # Search for similar mappings in RAG
        similar_mappings = []
        for target_col in target_columns:
            # Search for each target column
            similar = rag_service.search_similar_mappings(
                source_column="",  # Search broadly
                target_column=target_col,
                business_domain=message_desc.business_domain,
                n_results=3
            )
            similar_mappings.extend(similar)
        
        logger.info(f"Found {len(similar_mappings)} similar mappings in knowledge base")
        
        # Get suggestions from LLM
        suggestions = llm_service.suggest_mapping(
            source_columns=source_columns,
            target_columns=target_columns,
            sample_data=message_desc.sample_data or [],
            business_domain=message_desc.business_domain,
            similar_mappings=similar_mappings
        )
        
        return {
            "message_description_id": message_description_id,
            "source_columns": source_columns,
            "target_columns": target_columns,
            "suggestions": suggestions.get('mappings', []),
            "similar_mappings_found": len(similar_mappings)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mapping suggestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate mapping suggestions: {str(e)}"
        )


@router.put("/{formula_id}", response_model=MappingFormulaResponse)
def update_mapping_formula(
    formula_id: int,
    formula: MappingFormulaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Met à jour une MappingFormula
    """
    db_formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    
    if not db_formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found"
        )
    
    # Update fields
    update_data = formula.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_formula, field, value)
    
    db.commit()
    db.refresh(db_formula)
    
    # Update RAG if success_rate changed
    if 'success_rate' in update_data:
        try:
            rag_service.update_mapping_success_rate(
                mapping_id=f"mapping_{db_formula.id}",
                new_success_rate=db_formula.success_rate
            )
        except Exception as e:
            logger.warning(f"Failed to update RAG: {e}")
    
    return db_formula


@router.delete("/{formula_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprime une MappingFormula
    """
    db_formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    
    if not db_formula:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found"
        )
    
    db.delete(db_formula)
    db.commit()
    
    return None