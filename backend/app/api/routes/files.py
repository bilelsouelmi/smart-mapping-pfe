from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import os
import uuid
from pathlib import Path
import logging
from app.core.deps import get_current_user
from app.models.user import User

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
    current_user: User = Depends(get_current_user),  # ← Ajoutez cette ligne
    db: Session = Depends(get_db)
):
    """
    Upload et analyse un fichier avec l'IA
    
    Returns:
        MessageDescription générée par l'IA
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
        
        logger.info(f"Analyzing file: {unique_filename}")
        
        # Process file to extract structure
        file_info = file_processor.process_file(str(file_path))
        
        columns = file_info['columns']
        sample_data = file_info['sample_data']
        file_type = file_info['file_type']
        
        # Analyze with LLM
        logger.info("Sending file structure to LLM for analysis...")
        analysis = llm_service.analyze_file_structure(
            columns=columns,
            sample_data=sample_data,
            file_type=file_type
        )
        
        # Create MessageDescription in database
        message_desc = MessageDescription(
            user_id=current_user.id,  # ← Utilisez l'utilisateur connecté
            file_name=file.filename,
            file_type=file_type,
            business_domain=analysis.get('business_domain'),
            column_structure=analysis.get('columns_analysis'),
            sample_data=sample_data
        )
        
        db.add(message_desc)
        db.commit()
        db.refresh(message_desc)
        
        logger.info(f"MessageDescription created: ID {message_desc.id}")
        
        return message_desc
        
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