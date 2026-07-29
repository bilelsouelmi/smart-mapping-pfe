from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
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
    query = db.query(MappingFormula)
    if message_description_id:
        query = query.filter(MappingFormula.message_description_id == message_description_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{formula_id}", response_model=MappingFormulaResponse)
def get_mapping_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found")
    return formula


@router.post("/", response_model=MappingFormulaResponse, status_code=status.HTTP_201_CREATED)
def create_mapping_formula(
    formula: MappingFormulaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify MessageDescription exists
    message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == formula.message_description_id
    ).first()

    if not message_desc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {formula.message_description_id} not found")

    # ── Auto-populate source and target from MessageDescription ──────────────
    # source = mt_type (e.g. MT103)  — the source message type
    # target = iso_target (e.g. pacs.008.001.08) — the ISO 20022 target
    formula_data = formula.model_dump()
    # Only use mt_type/iso_target if source_path/target_path are not already set
    # to preserve field-level paths sent from the frontend (e.g. block4.:20 -> Ntry/NtryRef)
    if not formula_data.get('source_path') or formula_data.get('source_path') == message_desc.mt_type:
        formula_data['source_path'] = formula_data.get('source_path') or message_desc.mt_type
    if not formula_data.get('target_path') or formula_data.get('target_path') == message_desc.iso_target:
        formula_data['target_path'] = formula_data.get('target_path') or message_desc.iso_target
    # ─────────────────────────────────────────────────────────────────────────

    db_formula = MappingFormula(**formula_data)
    db.add(db_formula)
    db.commit()
    db.refresh(db_formula)

    logger.info(
        f"MappingFormula created: id={db_formula.id} "
        f"source={formula_data['source_path']} "
        f"target={formula_data['target_path']}"
    )

    return db_formula


@router.post("/suggest", response_model=Dict[str, Any])
def suggest_mappings(
    message_description_id: int = Body(...),
    target_columns: List[str] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == message_description_id
        ).first()
        if not message_desc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MessageDescription {message_description_id} not found")

        source_columns = [col['name'] for col in message_desc.column_structure] \
            if message_desc.column_structure else []
        if not source_columns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail="MessageDescription has no column structure")

        # One Qdrant search per target column, but each search is its own
        # blocking round-trip (embed the query via Ollama, then query
        # Qdrant) — these are fully independent, so running them one at a
        # time serially was pure wasted wall-clock time. Measured ~0.14s
        # per call, so 15 target columns cost ~2s sequentially vs
        # ~0.2-0.3s in parallel.
        similar_mappings = []
        with ThreadPoolExecutor(max_workers=min(len(target_columns), 8)) as executor:
            results = executor.map(
                lambda target_col: rag_service.search_similar_mappings(
                    source_column="",
                    target_column=target_col,
                    business_domain=message_desc.business_domain,
                    n_results=3
                ),
                target_columns
            )
            for similar in results:
                similar_mappings.extend(similar)

        suggestions = llm_service.suggest_mapping(
            source_columns=source_columns,
            target_columns=target_columns,
            sample_data=message_desc.sample_data or [],
            business_domain=message_desc.business_domain,
            similar_mappings=similar_mappings
        )

        # The LLM is asked for {"mappings": [...]} but occasionally ignores
        # the wrapper and returns a bare JSON array instead — accept both
        # shapes rather than crashing on suggestions.get(...).
        if isinstance(suggestions, list):
            mappings = suggestions
        else:
            mappings = suggestions.get('mappings', [])

        return {
            "message_description_id": message_description_id,
            "source_columns": source_columns,
            "target_columns": target_columns,
            "suggestions": mappings,
            "similar_mappings_found": len(similar_mappings)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mapping suggestion failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate mapping suggestions: {str(e)}")


@router.put("/{formula_id}", response_model=MappingFormulaResponse)
def update_mapping_formula(
    formula_id: int,
    formula: MappingFormulaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    if not db_formula:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found")

    update_data = formula.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_formula, field, value)

    db.commit()
    db.refresh(db_formula)

    return db_formula


@router.delete("/{formula_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping_formula(
    formula_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_formula = db.query(MappingFormula).filter(MappingFormula.id == formula_id).first()
    if not db_formula:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingFormula {formula_id} not found")
    db.delete(db_formula)
    db.commit()
    return None