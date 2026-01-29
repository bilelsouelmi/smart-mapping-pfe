from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import os
import uuid
from pathlib import Path
import logging
from app.core.deps import get_current_user
from app.models.user import User
from app.services.hierarchy_parser import HierarchyParser
from app.database import get_db
from app.config import settings
from app.services.file_processor import FileProcessor
from app.services.llm_service import LLMService
from app.models.message_description import MessageDescription
from app.schemas.message_description import MessageDescriptionResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
file_processor = FileProcessor()
llm_service = LLMService()
hierarchy_parser = HierarchyParser()

# Ensure upload directory exists
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # ← Ajoutez cette ligne
    db: Session = Depends(get_db)
):
    """
    Upload un fichier
    
    Returns:
        Informations sur le fichier uploadé
    """
    try:
        # Validate file type
        file_extension = Path(file.filename).suffix.lower().replace('.', '')
        
        if file_extension not in FileProcessor.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Supported: {', '.join(FileProcessor.SUPPORTED_FORMATS)}"
            )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File uploaded: {unique_filename} ({len(content)} bytes)")
        
        return {
            "filename": file.filename,
            "unique_filename": unique_filename,
            "file_path": str(file_path),
            "file_size": len(content),
            "file_type": file_extension.upper(),
            "message": "File uploaded successfully"
        }
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.post("/analyze", response_model=MessageDescriptionResponse)
async def analyze_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload et analyse un fichier avec l'IA - Détection automatique de la hiérarchie
    
    Returns:
        MessageDescription avec structure hiérarchique détectée
    """
    try:
        # Upload file first
        file_extension = Path(file.filename).suffix.lower().replace('.', '')
        
        if file_extension not in FileProcessor.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Supported: {', '.join(FileProcessor.SUPPORTED_FORMATS)}"
            )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Analyzing file with hierarchy detection: {unique_filename}")
        
        # Process file to extract structure
        file_info = file_processor.process_file(str(file_path))
        
        columns = file_info['columns']
        sample_data = file_info['sample_data']
        file_type = file_info['file_type']
        
        # Détecter la structure hiérarchique
        hierarchical_structure = None
        hierarchy_paths = []
        
        if file_type in ['JSON', 'XML']:
            # Pour JSON/XML, parser la structure hiérarchique directement
            if sample_data and len(sample_data) > 0:
                try:
                    hierarchy_paths = hierarchy_parser.parse_structure(sample_data[0], max_level=3)
                    hierarchical_structure = {
                        "type": "hierarchical",
                        "paths": hierarchy_paths[:20],  # Limiter à 20 chemins
                        "total_paths": len(hierarchy_paths)
                    }
                    logger.info(f"Detected {len(hierarchy_paths)} hierarchical paths in {file_type}")
                except Exception as e:
                    logger.warning(f"Could not parse hierarchical structure: {e}")
        
        elif file_type in ['CSV', 'Excel']:
            # Pour CSV/Excel, vérifier si les colonnes contiennent des points (nomenclature hiérarchique)
            hierarchical_columns = []
            for col in columns:
                if '.' in col:
                    levels = col.split('.')
                    if len(levels) <= 4:  # Max 3 niveaux (4 parties)
                        hierarchical_columns.append({
                            "path": col,
                            "level": len(levels),
                            "parts": levels,
                            "type": "inferred",
                            "is_leaf": True
                        })
            
            if hierarchical_columns:
                hierarchical_structure = {
                    "type": "flat_with_notation",
                    "paths": hierarchical_columns,
                    "total_paths": len(hierarchical_columns)
                }
                logger.info(f"Detected {len(hierarchical_columns)} hierarchical column names in {file_type}")
        
        # Analyze with LLM
        logger.info("Sending file structure to LLM for analysis...")
        analysis = llm_service.analyze_file_structure(
            columns=columns,
            sample_data=sample_data[:3],  # Limiter à 3 lignes pour l'IA
            file_type=file_type
        )
        
        # Enrichir l'analyse avec la structure hiérarchique
        column_structure = analysis.get('columns_analysis', [])
        
        # Ajouter les infos hiérarchiques aux colonnes
        if hierarchical_structure and hierarchical_structure['type'] == 'flat_with_notation':
            for col_analysis in column_structure:
                col_name = col_analysis.get('name')
                if '.' in col_name:
                    col_analysis['hierarchical'] = True
                    col_analysis['path'] = col_name
                    col_analysis['level'] = len(col_name.split('.'))
        
        # Sauvegarder dans la base
        message_desc = MessageDescription(
            user_id=current_user.id,
            file_name=file.filename,
            file_type=file_type,
            business_domain=analysis.get('business_domain'),
            column_structure=column_structure,
            sample_data=sample_data[:10]  # Sauvegarder 10 lignes
        )
        
        db.add(message_desc)
        db.commit()
        db.refresh(message_desc)
        
        logger.info(f"MessageDescription created: ID {message_desc.id}")
        
        # Ajouter les infos hiérarchiques à la réponse (pour le frontend)
        response_data = {
            "id": message_desc.id,
            "user_id": message_desc.user_id,
            "file_name": message_desc.file_name,
            "file_type": message_desc.file_type,
            "source_system": message_desc.source_system,
            "target_system": message_desc.target_system,
            "business_domain": message_desc.business_domain,
            "column_structure": message_desc.column_structure,
            "sample_data": message_desc.sample_data,
            "created_at": message_desc.created_at,
            "updated_at": message_desc.updated_at,
            # Infos supplémentaires pour le frontend
            "hierarchical_structure": hierarchical_structure
        }
        
        return response_data
        
    except ValueError as e:
        logger.error(f"File processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"File analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File analysis failed: {str(e)}"
        )


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Retourne les formats de fichiers supportés
    """
    return {
        "supported_formats": FileProcessor.SUPPORTED_FORMATS,
        "descriptions": {
            "csv": "Comma-Separated Values",
            "xml": "Extensible Markup Language",
            "json": "JavaScript Object Notation",
            "xlsx": "Microsoft Excel (2007+)",
            "xls": "Microsoft Excel (97-2003)"
        }
    }