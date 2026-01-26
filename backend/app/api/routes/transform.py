from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import json
from pathlib import Path

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message_description import MessageDescription
from app.models.mapping_formula import MappingFormula
from app.services.file_processor import FileProcessor
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

file_processor = FileProcessor()

# Output directory
OUTPUT_DIR = Path(settings.UPLOAD_DIR).parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/apply-mapping/{message_description_id}")
async def apply_mapping(
    message_description_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Applique les mappings sur un fichier et génère l'output transformé
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
        
        # Get all mapping formulas for this message description
        formulas = db.query(MappingFormula).filter(
            MappingFormula.message_description_id == message_description_id
        ).all()
        
        if not formulas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No mapping formulas found. Please create mappings first."
            )
        
        logger.info(f"Applying {len(formulas)} mapping formulas to MessageDescription {message_description_id}")
        
        # Get sample data from message description
        source_data = message_desc.sample_data or []
        
        if not source_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No sample data available in MessageDescription"
            )
        
        # Convert formulas to dict format
        formula_dicts = [
            {
                "target_column": f.target_column,
                "source_column": f.source_column,
                "transformation_type": f.transformation_type,
                "transformation_rule": f.transformation_rule
            }
            for f in formulas
        ]
        
        # Apply transformation
        transformed_data = file_processor.apply_transformation(
            data=source_data,
            mapping_formulas=formula_dicts
        )
        
        # Generate output filename
        output_filename = f"transformed_{message_desc.file_name.replace('.', '_')}_{message_description_id}.json"
        output_path = OUTPUT_DIR / output_filename
        
        # Save transformed data to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transformed_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Transformation complete. Output saved to: {output_path}")
        
        return {
            "message": "Transformation completed successfully",
            "message_description_id": message_description_id,
            "formulas_applied": len(formulas),
            "rows_transformed": len(transformed_data),
            "output_file": output_filename,
            "output_path": str(output_path),
            "preview": transformed_data[:3]  # First 3 rows
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transformation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transformation failed: {str(e)}"
        )


@router.get("/outputs")
async def list_outputs(
    current_user: User = Depends(get_current_user)
):
    """
    Liste tous les fichiers OUTPUT générés
    """
    try:
        output_files = []
        
        if OUTPUT_DIR.exists():
            for file_path in OUTPUT_DIR.glob("*.json"):
                output_files.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "created": file_path.stat().st_mtime
                })
        
        return {
            "total_outputs": len(output_files),
            "files": output_files
        }
        
    except Exception as e:
        logger.error(f"Failed to list outputs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list outputs: {str(e)}"
        )