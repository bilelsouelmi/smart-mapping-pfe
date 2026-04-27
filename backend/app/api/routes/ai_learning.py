from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message_description import MessageDescription
from app.models.mapping_formula import MappingFormula
from app.services.ai_learning_service import ai_learning_service
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


def _update_mapping_completion(message_description_id: int, db: Session):
    """
    Calcule et met à jour le % de colonnes mappées pour une MessageDescription.
    """
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == message_description_id
        ).first()

        if not message_desc:
            return

        # Total colonnes
        total_columns = len(message_desc.column_structure or [])
        if total_columns == 0:
            return

        # Colonnes mappées (formulas créées avec target non vide)
        mapped_count = db.query(MappingFormula).filter(
            MappingFormula.message_description_id == message_description_id,
            MappingFormula.target_path != '',
            MappingFormula.target_path != None
        ).count()

        completion = int((mapped_count / total_columns) * 100)
        message_desc.mapping_completion = min(completion, 100)

        # Mettre à jour status
        if completion == 0:
            message_desc.status = 'draft'
        elif completion < 100:
            message_desc.status = 'in_progress'
        else:
            message_desc.status = 'validated'

        db.commit()
        logger.info(f"✅ Mapping completion updated: {completion}% for MD {message_description_id}")

    except Exception as e:
        logger.error(f"Failed to update mapping completion: {e}")


@router.post("/ai-learning/record-decision")
async def record_decision(
    request: RecordDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enregistre la décision de l'utilisateur pour apprentissage
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

        # ── Indexer dans Qdrant si edit ou accept avec mapping_formula ────────
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

            except Exception as e:
                logger.error(f"Qdrant indexing failed for {request.field_id}: {e}")

        # ── NOUVEAU : Mettre à jour mapping_completion ────────────────────────
        if request.message_description_id and request.user_action in ['accept', 'edit']:
            _update_mapping_completion(request.message_description_id, db)
        # ── FIN NOUVEAU ───────────────────────────────────────────────────────

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