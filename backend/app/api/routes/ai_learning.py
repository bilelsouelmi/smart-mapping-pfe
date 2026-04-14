from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.ai_learning_service import ai_learning_service  # ✅ CORRECT!
from pydantic import BaseModel
from typing import Optional, Dict
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class RecordDecisionRequest(BaseModel):
    field_id: str
    field_tag: Optional[str] = None
    suggestion: Dict
    user_action: str  # 'accept', 'edit', 'reject'
    final_values: Optional[Dict] = None
    message_description_id: Optional[int] = None
    mapping_formula_id: Optional[int] = None


@router.post("/ai-learning/record-decision")
async def record_decision(
    request: RecordDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enregistre la décision de l'utilisateur pour apprentissage
    
    Body:
        {
            "field_id": "FIELD_03",
            "field_tag": ":32A",
            "suggestion": {...},
            "user_action": "accept",  // or "edit" or "reject"
            "final_values": {...},  // si edit
            "message_description_id": 123,
            "mapping_formula_id": 456
        }
    """
    try:
        ai_learning_service.record_user_decision(
            field_id=request.field_id,
            field_tag=request.field_tag,
            suggestion=request.suggestion,
            user_action=request.user_action,
            final_values=request.final_values,
            message_description_id=request.message_description_id,
            mapping_formula_id=request.mapping_formula_id,
            user_id=current_user.id,
            db=db
        )

        # ── NOUVEAU : Indexer dans Qdrant si edit ou accept avec mapping_formula ──
        if request.user_action in ['edit', 'accept']:
            try:
                from app.services.qdrant_manager import qdrant_manager

                if request.user_action == 'edit' and request.final_values:
                    mapping_formula = request.final_values.get('mapping_formula')
                    suggestion_data = request.final_values
                else:
                    mapping_formula = request.suggestion.get('mapping_formula')
                    suggestion_data = request.suggestion

                if mapping_formula:
                    field_name = (
                        request.final_values.get('element_name')
                        if request.final_values
                        else request.suggestion.get('element_name', request.field_id)
                    )
                    success = qdrant_manager.add_user_chunk(
                        field_id=request.field_id,
                        field_name=field_name,
                        mapping_formula=mapping_formula,
                        suggestion=suggestion_data,
                        user_id=current_user.id
                    )
                    if success:
                        logger.info(f"✅ User chunk indexed in Qdrant for {request.field_id}")
                    else:
                        logger.warning(f"⚠️ Failed to index user chunk for {request.field_id}")

            except Exception as e:
                logger.error(f"Qdrant indexing failed for {request.field_id}: {e}")
        # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

        return {
            "message": "Decision recorded successfully",
            "action": request.user_action,
            "field_id": request.field_id
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))