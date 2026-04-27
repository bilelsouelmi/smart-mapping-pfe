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
from app.models.file_upload import FileUpload, FileUploadStatus
from app.schemas.message_description import MessageDescriptionResponse
from app.services.element_matcher import ElementMatcher
from app.services import ai_learning_service 

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload un fichier"""
    try:
        file_extension = Path(file.filename).suffix.lower().replace('.', '')
        
        if file_extension not in FileProcessor.SUPPORTED_FORMATS + ["txt"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Supported: {', '.join(FileProcessor.SUPPORTED_FORMATS)}"
            )
        
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
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


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload et analyse un fichier avec l'IA
    Détection automatique de la hiérarchie + Suggestions AI Learning + Enrichissement Qdrant
    """
    try:
        file_extension = Path(file.filename).suffix.lower().replace('.', '')
        
        if file_extension not in FileProcessor.SUPPORTED_FORMATS + ["txt"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Supported: {', '.join(FileProcessor.SUPPORTED_FORMATS)}"
            )
        
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # ── TXT SWIFT → traiter comme XML_MT ──────────────────────────────────
        if file_extension == 'txt':
            file_extension = 'xml'  # force extension pour FileUpload
        # ── FIN ───────────────────────────────────────────────────────────────
        
        logger.info(f"Analyzing file with AI Learning: {unique_filename}")

        # ── Créer FileUpload en base ──────────────────────────────────────────
        file_upload = FileUpload(
            user_id=current_user.id,
            original_filename=file.filename,
            file_path=str(file_path),
            file_type=file_extension.upper(),
            file_size=len(content),
            status=FileUploadStatus.PROCESSING
        )
        db.add(file_upload)
        db.commit()
        db.refresh(file_upload)
        logger.info(f"FileUpload created: ID {file_upload.id}")

        # Process file to extract structure
        file_info = file_processor.process_file(str(file_path))
        
        columns = file_info['columns']
        sample_data = file_info['sample_data']
        file_type = file_info['file_type']

        # ── NOUVEAU : extraire mt_info si XML_MT ──────────────────────────────
        mt_info = file_info.get('mt_info')  # None si pas XML_MT
        mt_type = mt_info.get('mt_type') if mt_info else None
        iso_target = mt_info.get('iso_target') if mt_info else None
        mt_blocks = mt_info.get('mt_blocks') if mt_info else None
        if mt_type:
            logger.info(f"🏦 MT detected: {mt_type} → {iso_target}, {len(mt_blocks)} blocks")
        # ── FIN NOUVEAU ───────────────────────────────────────────────────────
        
        # Détecter la structure hiérarchique
        hierarchical_structure = None
        hierarchy_paths = []
        
        if file_type in ['JSON', 'XML']:
            if sample_data and len(sample_data) > 0:
                try:
                    hierarchy_paths = hierarchy_parser.parse_structure(sample_data[0], max_level=3)
                    hierarchical_structure = {
                        "type": "hierarchical",
                        "paths": hierarchy_paths[:20],
                        "total_paths": len(hierarchy_paths)
                    }
                    logger.info(f"Detected {len(hierarchy_paths)} hierarchical paths in {file_type}")
                except Exception as e:
                    logger.warning(f"Could not parse hierarchical structure: {e}")
        
        elif file_type in ['CSV', 'Excel']:
            hierarchical_columns = []
            for col in columns:
                if '.' in col:
                    levels = col.split('.')
                    if len(levels) <= 4:
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

        # ── XML_MT : hiérarchique depuis mt_blocks ────────────────────────────
        elif file_type == 'XML_MT' and mt_blocks:
            hierarchical_structure = {
                "type": "mt_blocks",
                "mt_type": mt_type,
                "iso_target": iso_target,
                "blocks": mt_blocks,
                "total_paths": len(columns)
            }
        # ── FIN XML_MT ────────────────────────────────────────────────────────
        
        # Analyze with LLM
        logger.info("Sending file structure to LLM for analysis...")
        analysis = llm_service.analyze_file_structure(
            columns=columns,
            sample_data=sample_data[:3],
            file_type=file_type
        )
        
        column_structure = analysis.get('columns_analysis', [])
        
        if hierarchical_structure and hierarchical_structure.get('type') == 'flat_with_notation':
            for col_analysis in column_structure:
                col_name = col_analysis.get('name')
                if col_name and '.' in col_name:
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
            sample_data=sample_data[:10],
            file_upload_id=file_upload.id,
            # ── NOUVEAU : MT fields ───────────────────────────────────────────
            mt_type=mt_type,
            iso_target=iso_target,
            mt_blocks=mt_blocks,
            status='draft'
            # ── FIN NOUVEAU ───────────────────────────────────────────────────
        )
        
        db.add(message_desc)
        db.commit()
        db.refresh(message_desc)
        
        logger.info(f"MessageDescription created: ID {message_desc.id}")

        # Marquer FileUpload comme COMPLETED
        file_upload.status = FileUploadStatus.COMPLETED
        db.commit()
        
        # === Générer suggestions avec AI Learning + Enrichissement Qdrant ===
        from app.services.ai_learning_service import ai_learning_service
        
        suggestions = {}
        try:
            logger.info(f"🤖 Generating AI Learning suggestions for {len(columns)} columns")
            
            for column in columns:
                suggestion = await ai_learning_service.suggest_field_mapping(
                    field_id=column,
                    field_name=column,
                    sample_data=sample_data[:5],
                    message_description_id=message_desc.id,
                    db=db
                )
                
                suggestions[column] = [{
                    "element_id": suggestion.get('element_id', column),
                    "element_name": suggestion.get('element_name', column),
                    "target_path": suggestion.get('target', ''),
                    "confidence": int(suggestion.get('confidence', 0.5) * 100),
                    "category": "AI Suggestion",
                    "reason": f"Suggested by {suggestion.get('suggestion_source', 'AI')}",
                    "suggestion_source": suggestion.get('suggestion_source', 'ai'),
                    "audit_requirement": suggestion.get('audit_requirement'),
                    "compliance_requirement": suggestion.get('compliance_requirement'),
                    "data_privacy": suggestion.get('data_privacy'),
                    "migration_note": suggestion.get('migration_note'),
                    "caching_strategy": suggestion.get('caching_strategy'),
                    "performance_impact": suggestion.get('performance_impact'),
                    "global_variable_refs": suggestion.get('global_variable_refs', []),
                    "has_audit_requirement": suggestion.get('has_audit_requirement', False),
                    "has_compliance_requirement": suggestion.get('has_compliance_requirement', False),
                    "has_migration_note": suggestion.get('has_migration_note', False),
                    "rag_mapping_id": suggestion.get('rag_mapping_id'),
                    "rag_mapping_name": suggestion.get('rag_mapping_name'),
                    "rag_similarity_score": suggestion.get('rag_similarity_score'),
                    "mapping_formula": suggestion.get('mapping_formula'),
                    "web_enrichment": suggestion.get('web_enrichment', []),
                    "web_search_performed": suggestion.get('web_search_performed', False),
                    "full_suggestion": suggestion
                }]
            
            logger.info(f"✅ Generated enriched suggestions for {len(suggestions)} columns")
            
        except Exception as e:
            logger.error(f"Error generating AI Learning suggestions: {e}")
            import traceback
            traceback.print_exc()
            suggestions = {}
        
        # Réponse complète
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
            "hierarchical_structure": hierarchical_structure,
            "suggestions": suggestions,
            "file_upload_id": file_upload.id,
            # ── NOUVEAU : MT info dans la réponse ─────────────────────────────
            "mt_type": mt_type,
            "iso_target": iso_target,
            "mt_blocks": mt_blocks
            # ── FIN NOUVEAU ───────────────────────────────────────────────────
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
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File analysis failed: {str(e)}"
        )


@router.get("/")
async def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste tous les fichiers uploadés par l'utilisateur"""
    try:
        message_descs = db.query(MessageDescription).filter(
            MessageDescription.user_id == current_user.id
        ).order_by(MessageDescription.created_at.desc()).all()
        
        return {
            "files": [
                {
                    "id": md.id,
                    "file_name": md.file_name,
                    "file_type": md.file_type,
                    "business_domain": md.business_domain,
                    "created_at": md.created_at,
                    "status": md.status,
                    "mapping_completion": md.mapping_completion,
                    "quality_score": md.quality_score,
                    "mt_type": md.mt_type,
                    "iso_target": md.iso_target
                }
                for md in message_descs
            ],
            "total": len(message_descs)
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )


@router.get("/with-formulas")
async def list_files_with_formulas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Liste les fichiers qui ont des MappingFormulas — dédupliqués par file_name.
    Utilisé dans la page Outputs pour la dropdown de transformation.
    """
    try:
        from app.models.mapping_formula import MappingFormula
        from sqlalchemy import func

        # Sous-requête : IDs des MessageDescriptions qui ont des formulas
        subq = db.query(
            MappingFormula.message_description_id,
            func.count(MappingFormula.id).label('formula_count')
        ).group_by(MappingFormula.message_description_id).subquery()

        # Jointure avec MessageDescription
        results = db.query(MessageDescription, subq.c.formula_count).join(
            subq, MessageDescription.id == subq.c.message_description_id
        ).filter(
            MessageDescription.user_id == current_user.id
        ).order_by(MessageDescription.id.desc()).all()

        # Dédupliquer par file_name — garder le plus récent avec le plus de formulas
        seen = {}
        for md, formula_count in results:
            if md.file_name not in seen:
                seen[md.file_name] = (md, formula_count)

        files = []
        for file_name, (md, formula_count) in seen.items():
            files.append({
                "id": md.id,
                "file_name": md.file_name,
                "file_type": md.file_type,
                "business_domain": md.business_domain,
                "created_at": md.created_at,
                "status": md.status,
                "mapping_completion": md.mapping_completion,
                "quality_score": md.quality_score,
                "mt_type": md.mt_type,
                "iso_target": md.iso_target,
                "formula_count": formula_count
            })

        # Trier par file_name
        files.sort(key=lambda x: x['file_name'])

        return {
            "files": files,
            "total": len(files)
        }
    except Exception as e:
        logger.error(f"Error listing files with formulas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )


@router.get("/{file_id}")
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère les détails d'un fichier"""
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == file_id,
            MessageDescription.user_id == current_user.id
        ).first()
        
        if not message_desc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        return {
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
            # ── NOUVEAU : MT fields ───────────────────────────────────────────
            "mt_type": message_desc.mt_type,
            "iso_target": message_desc.iso_target,
            "mt_blocks": message_desc.mt_blocks
            # ── FIN NOUVEAU ───────────────────────────────────────────────────
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime un fichier"""
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == file_id,
            MessageDescription.user_id == current_user.id
        ).first()
        
        if not message_desc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        db.delete(message_desc)
        db.commit()
        
        logger.info(f"File deleted: {message_desc.file_name} (ID: {file_id})")
        
        return {"message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )


@router.get("/supported-formats")
async def get_supported_formats():
    """Retourne les formats de fichiers supportés"""
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


@router.put("/{file_id}/mt-blocks")
async def update_mt_blocks(
    file_id: int,
    mt_blocks: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Met à jour les blocs MT d'une MessageDescription.
    Appelé quand l'utilisateur accepte/édite/supprime des blocs.
    """
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == file_id,
            MessageDescription.user_id == current_user.id
        ).first()

        if not message_desc:
            raise HTTPException(status_code=404, detail="File not found")

        message_desc.mt_blocks = mt_blocks
        message_desc.status = 'in_progress'
        db.commit()
        db.refresh(message_desc)

        logger.info(f"MT blocks updated for MessageDescription {file_id}")
        return {
            "message": "MT blocks updated successfully",
            "id": file_id,
            "mt_blocks": mt_blocks,
            "blocks_count": len(mt_blocks)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MT blocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/regenerate-mt")
async def regenerate_mt_suggestions(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Re-génère les suggestions AI pour les blocs MT après modification.
    """
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == file_id,
            MessageDescription.user_id == current_user.id
        ).first()

        if not message_desc:
            raise HTTPException(status_code=404, detail="File not found")

        if not message_desc.mt_blocks:
            raise HTTPException(status_code=400, detail="No MT blocks found")

        # Rebuild columns from current mt_blocks
        columns = []
        sample_row = {}
        for tag, block in message_desc.mt_blocks.items():
            if block.get('type') == 'string':
                columns.append(tag)
                sample_row[tag] = block.get('value')
            elif block.get('type') == 'map':
                for sub_name, sub_field in block.get('sub_fields', {}).items():
                    col = f"{tag}.{sub_name}"
                    columns.append(col)
                    sample_row[col] = sub_field.get('value')

        # Re-generate AI suggestions
        from app.services.ai_learning_service import ai_learning_service
        suggestions = {}
        for column in columns:
            suggestion = await ai_learning_service.suggest_field_mapping(
                field_id=column,
                field_name=column,
                sample_data=[sample_row],
                message_description_id=message_desc.id,
                db=db
            )
            suggestions[column] = [{
                "element_id": suggestion.get('element_id', column),
                "element_name": suggestion.get('element_name', column),
                "target_path": suggestion.get('target', ''),
                "confidence": int(suggestion.get('confidence', 0.5) * 100),
                "category": "AI Suggestion",
                "reason": f"Suggested by {suggestion.get('suggestion_source', 'AI')}",
                "suggestion_source": suggestion.get('suggestion_source', 'ai'),
                "audit_requirement": suggestion.get('audit_requirement'),
                "compliance_requirement": suggestion.get('compliance_requirement'),
                "data_privacy": suggestion.get('data_privacy'),
                "migration_note": suggestion.get('migration_note'),
                "caching_strategy": suggestion.get('caching_strategy'),
                "performance_impact": suggestion.get('performance_impact'),
                "global_variable_refs": suggestion.get('global_variable_refs', []),
                "has_audit_requirement": suggestion.get('has_audit_requirement', False),
                "has_compliance_requirement": suggestion.get('has_compliance_requirement', False),
                "has_migration_note": suggestion.get('has_migration_note', False),
                "rag_mapping_id": suggestion.get('rag_mapping_id'),
                "rag_mapping_name": suggestion.get('rag_mapping_name'),
                "rag_similarity_score": suggestion.get('rag_similarity_score'),
                "mapping_formula": suggestion.get('mapping_formula'),
                "web_enrichment": suggestion.get('web_enrichment', []),
                "web_search_performed": suggestion.get('web_search_performed', False),
                "full_suggestion": suggestion
            }]

        logger.info(f"Re-generated {len(suggestions)} suggestions for MessageDescription {file_id}")
        return {
            "id": file_id,
            "suggestions": suggestions,
            "columns": columns
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate MT suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))