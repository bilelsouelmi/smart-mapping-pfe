from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
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
from app.models.notification import Notification
from app.schemas.message_description import MessageDescriptionResponse
from app.services.element_matcher import ElementMatcher
from app.services import ai_learning_service
from app.services.audit_service import log_action

router = APIRouter()
logger = logging.getLogger(__name__)

file_processor = FileProcessor()
llm_service = LLMService()
hierarchy_parser = HierarchyParser()

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
    # The Mapping page's "AI Formula Suggestions" panel (MappingWorkspacePage.jsx's
    # handleUpload) also calls this same endpoint, purely to get column
    # suggestions — it has no interest in creating a durable "reference"
    # Message Description at all, so re-analyzing a file that already has
    # an approved/pending MD (the exact scenario the duplicate check below
    # exists for) must NOT be blocked there.
    skip_duplicate_check: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload et analyse un fichier avec l'IA
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

        logger.info(f"Analyzing file with AI Learning: {unique_filename}")

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

        file_info = file_processor.process_file(str(file_path))

        columns = file_info['columns']
        sample_data = file_info['sample_data']
        file_type = file_info['file_type']

        # ── FIX: normalize columns to a flat list of strings ──────────────────
        column_display_names = {}
        if columns and isinstance(columns[0], dict):
            for c in columns:
                col_name = c.get('name', str(c))
                column_display_names[col_name] = c.get('display_name', col_name)
            columns = [c.get('name', str(c)) for c in columns]

        mt_info = file_info.get('mt_info')
        mt_type = mt_info.get('mt_type') if mt_info else None
        iso_target = mt_info.get('iso_target') if mt_info else None
        mt_blocks = mt_info.get('mt_blocks') if mt_info else None
        if mt_type:
            logger.info(f"MT detected: {mt_type} → {iso_target}, {len(mt_blocks)} blocks")

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

        elif file_type == 'XML_MT' and mt_blocks:
            hierarchical_structure = {
                "type": "mt_blocks",
                "mt_type": mt_type,
                "iso_target": iso_target,
                "blocks": mt_blocks,
                "total_paths": len(columns)
            }

        logger.info("Sending file structure to LLM for analysis...")
        try:
            analysis = llm_service.analyze_file_structure(
                columns=columns,
                sample_data=sample_data[:3],
                file_type=file_type
            )
            column_structure = analysis.get('columns_analysis', [])
        except Exception as llm_err:
            logger.warning(f"LLM analysis failed (non-critical): {llm_err}")
            analysis = {"business_domain": "Banking", "columns_analysis": []}
            column_structure = [{"name": col, "type": "STRING", "format": None} for col in columns]

        if hierarchical_structure and hierarchical_structure.get('type') == 'flat_with_notation':
            for col_analysis in column_structure:
                col_name = col_analysis.get('name')
                if col_name and '.' in col_name:
                    col_analysis['hierarchical'] = True
                    col_analysis['path'] = col_name
                    col_analysis['level'] = len(col_name.split('.'))

        # A new draft for a (mt_type, file_type) that already has a pending
        # or approved MD is the exact setup that caused the confusing
        # approve/demote flip-flop between two near-identical uploads
        # (e.g. "test mt103.txt" vs "test_mt103_pep.txt", same MT103
        # structure). Comparing sample_data (same slice as what gets
        # persisted below) catches genuine duplicates without blocking
        # legitimately different samples of the same message type.
        new_sample_data = sample_data[:10]
        new_sample_json = json.dumps(new_sample_data, sort_keys=True)
        existing_candidates = [] if skip_duplicate_check else db.query(MessageDescription).filter(
            MessageDescription.mt_type == mt_type,
            MessageDescription.file_type == file_type
        ).all()
        for existing in existing_candidates:
            if json.dumps(existing.sample_data or [], sort_keys=True) == new_sample_json:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This file's content is identical to the existing Message Description "
                           f"\"{existing.file_name}\" (id={existing.id}, "
                           f"{'approved' if existing.approved else 'pending approval'}). "
                           f"Reject or approve that one first instead of creating a duplicate."
                )

        message_desc = MessageDescription(
            user_id=current_user.id,
            file_name=file.filename,
            file_type=file_type,
            business_domain=analysis.get('business_domain'),
            column_structure=column_structure,
            sample_data=new_sample_data,
            file_upload_id=file_upload.id,
            mt_type=mt_type,
            iso_target=iso_target,
            mt_blocks=mt_blocks,
            status='draft'
        )

        db.add(message_desc)
        db.commit()
        db.refresh(message_desc)
        logger.info(f"MessageDescription created: ID {message_desc.id}")

        log_action(
            db, current_user, action="propose", entity_type="MessageDescription",
            entity_id=message_desc.id,
            details=f"Uploaded \"{message_desc.file_name}\" ({mt_type or file_type})"
        )

        admins = db.query(User).filter(User.is_admin.is_(True), User.id != current_user.id).all()
        for admin in admins:
            db.add(Notification(
                user_id=admin.id,
                message=f"{current_user.username} proposed a new Message Description: \"{message_desc.file_name}\"",
                link="/message-descriptions"
            ))

        db.commit()

        file_upload.status = FileUploadStatus.COMPLETED
        db.commit()

        from app.services.ai_learning_service import ai_learning_service

        # field_id_for_rag maps the raw column name (e.g. "block4.:20", as
        # produced by swift_txt_parser for .txt uploads) to the clean SWIFT
        # tag needed for RAG lookup (e.g. ":20:"). Without this, field_id
        # passed to suggest_field_mapping never starts with ':', so every
        # MT-tag-aware branch in that function (ElementMatcher naming, RAG
        # exact lookup via exact_rag_lookup) is silently skipped and every
        # business field falls through to a generic, wrong ElementMatcher
        # guess. Mirrors the same mapping already used by /regenerate-mt.
        field_id_for_rag = {}
        for column in columns:
            parts = column.split('.', 1)
            if parts[0] == 'block4' and len(parts) == 2 and parts[1].startswith(':'):
                field_id_for_rag[column] = f":{parts[1].strip(':')}:"

        # NOTE: header/technical fields (block1/2/3/5) are SWIFT envelope
        # fields with no real ISO 20022 business mapping — skip the RAG/LLM
        # pipeline entirely for them instead of letting a weak semantic match
        # produce a misleadingly confident (and wrong) suggestion.
        suggestions = {}
        try:
            logger.info(f"Generating AI Learning suggestions for {len(columns)} columns")

            for column in columns:
                is_header_field = column.startswith('block') and not column.split('.')[0] == 'block4'

                if is_header_field:
                    suggestion = {
                        "element_id": column,
                        "element_name": column,
                        "target": "",
                        "confidence": 0.0,
                        "suggestion_source": "not_applicable",
                        "reason": "Technical SWIFT envelope field — no ISO 20022 business mapping",
                    }
                else:
                    suggestion = await ai_learning_service.suggest_field_mapping(
                        field_id=field_id_for_rag.get(column, column),
                        field_name=column_display_names.get(column, column),
                        sample_data=sample_data[:5],
                        message_description_id=message_desc.id,
                        db=db,
                        mt_type=mt_type,
                        iso_target=iso_target
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

            logger.info(f"Generated enriched suggestions for {len(suggestions)} columns")

        except Exception as e:
            logger.error(f"Error generating AI Learning suggestions: {e}")
            import traceback
            traceback.print_exc()
            suggestions = {}

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
            "hierarchical_structure": hierarchical_structure,
            "suggestions": suggestions,
            "file_upload_id": file_upload.id,
            "mt_type": mt_type,
            "iso_target": iso_target,
            "mt_blocks": mt_blocks
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"File processing error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    """Liste les Message Descriptions visibles par l'utilisateur : les siennes
    (y compris ses brouillons non encore approuvés) ET toutes celles qui ont
    été approuvées, quel qu'en soit le proposant.

    Cette seconde condition est indispensable : une MD approuvée est par
    définition la référence de la plateforme pour son type de message — c'est
    tout l'objet de l'étape d'approbation. Les deux écrans qui consomment cet
    endpoint en dépendent (la liste déroulante « standard de référence » de la
    page Validate, et le choix de la Message Description à la création d'un
    mapping). Restreindre au seul propriétaire créait une incohérence avec
    transform_mapping.py, dont les contrôles préalables retiennent une MD
    approuvée SANS filtre de propriétaire : un fichier pouvait donc être
    transformé alors que la référence correspondante n'apparaissait dans
    aucune des deux listes déroulantes."""
    try:
        from app.models import MessageDescriptionElement
        from sqlalchemy import func, or_

        message_descs = db.query(MessageDescription).filter(
            or_(
                MessageDescription.user_id == current_user.id,
                MessageDescription.approved == True,  # noqa: E712
            )
        ).order_by(MessageDescription.created_at.desc()).all()

        # element_count lets callers (e.g. the Validate page's reference-
        # standard dropdown) tell a fully "Generate MD"-processed upload
        # apart from a bare, just-uploaded one with no elements yet — the
        # same distinction generate_mapping_elements already uses via
        # get_block4_elements. Without it, "pick the newest upload of this
        # type" (whether here or client-side) can silently select a
        # duplicate re-upload that was never processed, producing zero
        # validation rules with no visible error until validation itself
        # inexplicably finds nothing.
        counts = dict(
            db.query(
                MessageDescriptionElement.message_description_id,
                func.count(MessageDescriptionElement.id)
            ).group_by(MessageDescriptionElement.message_description_id).all()
        )

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
                    "iso_target": md.iso_target,
                    "element_count": counts.get(md.id, 0),
                    "approved": md.approved
                }
                for md in message_descs
            ],
            "total": len(message_descs)
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/dashboard-stats")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chiffres de la page d'accueil, calculés sur le modele courant
    (message_descriptions / mappings / mapping_elements / audit_logs).

    L'ancien /with-formulas s'appuyait sur la table historique mapping_formulas,
    que le flux SWIFT ne remplit plus : tous les compteurs y restaient a zero.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, or_
    from app.models.mapping import Mapping, MappingElement
    from app.models.audit_log import AuditLog

    try:
        # -- Message Descriptions : visibles = les miennes OU celles approuvees
        mds = db.query(MessageDescription).filter(
            or_(
                MessageDescription.user_id == current_user.id,
                MessageDescription.approved == True,
            )
        ).all()
        # dedoublonnage par nom de fichier, comme les autres listes
        seen_md = {}
        for md in mds:
            if md.file_name not in seen_md:
                seen_md[md.file_name] = md
        md_list = list(seen_md.values())

        # -- Mappings et elements
        mappings = db.query(Mapping).all()
        mapping_ids = [m.id for m in mappings]
        total_elements = 0
        mapped_elements = 0
        if mapping_ids:
            rows = db.query(
                MappingElement.status, func.count(MappingElement.id)
            ).filter(
                MappingElement.mapping_id.in_(mapping_ids)
            ).group_by(MappingElement.status).all()
            for st, cnt in rows:
                total_elements += cnt
                if str(getattr(st, "value", st)).lower() == "mapped":
                    mapped_elements += cnt

        # -- Fichiers de sortie reellement presents sur le disque
        outputs_dir = Path(settings.UPLOAD_DIR).parent / "outputs"
        outputs_total = 0
        if outputs_dir.exists():
            outputs_total = sum(
                1 for p in outputs_dir.iterdir()
                if p.is_file() and p.suffix.lower() in (".xml", ".json", ".txt")
            )

        # -- Activite des 7 derniers jours, depuis la piste d'audit
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=6)
        buckets = {start + timedelta(days=i): 0 for i in range(7)}
        logs = db.query(AuditLog).filter(
            AuditLog.created_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
        ).all()
        for entry in logs:
            if entry.created_at:
                day = entry.created_at.date()
                if day in buckets:
                    buckets[day] += 1
        activity = [
            {"name": d.strftime("%d/%m"), "events": n}
            for d, n in sorted(buckets.items())
        ]

        completion = round(mapped_elements * 100 / total_elements) if total_elements else 0

        return {
            "message_descriptions": len(md_list),
            "mt_files": sum(1 for m in md_list if m.file_type == "XML_MT"),
            "approved_refs": sum(1 for m in md_list if m.approved),
            "mappings_total": len(mappings),
            "mappings_active": sum(1 for m in mappings if str(getattr(m.status, "value", m.status)).lower() == "active"),
            "mapping_elements": total_elements,
            "mapped_elements": mapped_elements,
            "avg_mapping_completion": completion,
            "outputs": outputs_total,
            "activity": activity,
        }

    except Exception as e:
        logger.error(f"Failed to build dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/with-formulas")
async def list_files_with_formulas(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste les fichiers qui ont des MappingFormulas — dédupliqués par file_name."""
    try:
        from app.models.mapping_formula import MappingFormula
        from sqlalchemy import func

        subq = db.query(
            MappingFormula.message_description_id,
            func.count(MappingFormula.id).label('formula_count')
        ).group_by(MappingFormula.message_description_id).subquery()

        results = db.query(MessageDescription, subq.c.formula_count).join(
            subq, MessageDescription.id == subq.c.message_description_id
        ).filter(
            MessageDescription.user_id == current_user.id
        ).order_by(MessageDescription.id.desc()).all()

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

        files.sort(key=lambda x: x['file_name'])
        return {"files": files, "total": len(files)}

    except Exception as e:
        logger.error(f"Error listing files with formulas: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

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
            "mt_type": message_desc.mt_type,
            "iso_target": message_desc.iso_target,
            "mt_blocks": message_desc.mt_blocks
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file")


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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        db.delete(message_desc)
        db.commit()
        logger.info(f"File deleted: {message_desc.file_name} (ID: {file_id})")
        return {"message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete file")


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
    """Met à jour les blocs MT d'une MessageDescription."""
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
    """Re-génère les suggestions AI pour les blocs MT après modification."""
    try:
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == file_id,
            MessageDescription.user_id == current_user.id
        ).first()

        if not message_desc:
            raise HTTPException(status_code=404, detail="File not found")

        if not message_desc.mt_blocks:
            raise HTTPException(status_code=400, detail="No MT blocks found")

        columns = []
        sample_row = {}
        # field_id_for_rag maps the display column name (e.g. "block4.:20")
        # to the clean SWIFT tag to use for RAG lookup (e.g. ":20:"). Header
        # blocks (block1/2/3/5) get no RAG tag at all — they're skipped below.
        field_id_for_rag = {}
        for tag, block in message_desc.mt_blocks.items():
            is_business_block = (tag == 'block4')
            if block.get('type') == 'string':
                columns.append(tag)
                sample_row[tag] = block.get('value')
                field_id_for_rag[tag] = None
            elif block.get('type') == 'map':
                for sub_name, sub_field in block.get('sub_fields', {}).items():
                    col = f"{tag}.{sub_name}"
                    columns.append(col)
                    sample_row[col] = sub_field.get('value')
                    if is_business_block and sub_name.startswith(':'):
                        clean = sub_name.strip(':')
                        field_id_for_rag[col] = f":{clean}:"
                    else:
                        field_id_for_rag[col] = None

        from app.services.ai_learning_service import ai_learning_service
        suggestions = {}
        for column in columns:
            rag_tag = field_id_for_rag.get(column)
            is_header_field = column.split('.')[0] != 'block4'

            if is_header_field:
                suggestion = {
                    "element_id": column,
                    "element_name": column,
                    "target": "",
                    "confidence": 0.0,
                    "suggestion_source": "not_applicable",
                    "reason": "Technical SWIFT envelope field — no ISO 20022 business mapping",
                }
            else:
                suggestion = await ai_learning_service.suggest_field_mapping(
                    field_id=rag_tag or column,
                    field_name=column,
                    sample_data=[sample_row],
                    message_description_id=message_desc.id,
                    db=db,
                    mt_type=message_desc.mt_type,
                    iso_target=message_desc.iso_target
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
        return {"id": file_id, "suggestions": suggestions, "columns": columns}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate MT suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))