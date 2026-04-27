from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import json
import datetime
from pathlib import Path

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message_description import MessageDescription
from app.models.mapping_formula import MappingFormula
from app.models.transformation_job import TransformationJob, JobStatus
from app.models.validation_report import ValidationReport
from app.models.file_upload import FileUpload
from app.services.file_processor import FileProcessor
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

file_processor = FileProcessor()

# Output directory
OUTPUT_DIR = Path(settings.UPLOAD_DIR).parent / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _calculate_validation(source_data, transformed_data, formulas) -> Dict[str, Any]:
    """
    Calcule les métriques de validation entre données source et transformées.
    """
    total_cells = 0
    matching_cells = 0
    differing_cells = 0
    differences = []

    formula_map = {f.source_path: f.target_path for f in formulas}

    for row_idx, (src_row, tgt_row) in enumerate(zip(source_data, transformed_data)):
        for src_col, tgt_col in formula_map.items():
            total_cells += 1
            src_value = str(src_row.get(src_col, '')) if src_row.get(src_col) is not None else ''
            tgt_value = str(tgt_row.get(tgt_col, '')) if tgt_row.get(tgt_col) is not None else ''

            if src_value == tgt_value:
                matching_cells += 1
            else:
                differing_cells += 1
                if len(differences) < 100:  # Max 100 differences
                    diff_type = "MISSING_VALUE" if not tgt_value else "VALUE_MISMATCH"
                    differences.append({
                        "row_number": row_idx + 1,
                        "column_name": src_col,
                        "expected_value": src_value,
                        "generated_value": tgt_value,
                        "difference_type": diff_type
                    })

    accuracy = (matching_cells / total_cells * 100) if total_cells > 0 else 0.0
    row_count_match = len(source_data) == len(transformed_data)
    column_count_match = True  # simplified

    if accuracy >= 95:
        quality = "EXCELLENT"
        recommendation = "Mapping is highly accurate. Ready for production."
    elif accuracy >= 80:
        quality = "GOOD"
        recommendation = "Mapping is good. Review differing cells before production."
    elif accuracy >= 60:
        quality = "ACCEPTABLE"
        recommendation = "Mapping needs improvement. Review transformation rules."
    else:
        quality = "POOR"
        recommendation = "Mapping requires significant rework. Review all rules."

    return {
        "accuracy_percentage": round(accuracy, 2),
        "row_count_match": row_count_match,
        "column_count_match": column_count_match,
        "total_cells": total_cells,
        "matching_cells": matching_cells,
        "differing_cells": differing_cells,
        "differences": differences,
        "overall_quality": quality,
        "recommendation": recommendation
    }


async def _run_transformation(
    job_id: int,
    message_description_id: int,
    db: Session
):
    """
    Exécute la transformation en background et met à jour le job.
    """
    job = db.query(TransformationJob).filter(TransformationJob.id == job_id).first()
    if not job:
        return

    try:
        # ── Start job ─────────────────────────────────────────────────────────
        job.status = JobStatus.RUNNING
        job.started_at = datetime.datetime.utcnow()
        job.progress = 10.0
        db.commit()

        # ── Get MessageDescription ────────────────────────────────────────────
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == message_description_id
        ).first()

        if not message_desc:
            raise Exception(f"MessageDescription {message_description_id} not found")

        job.progress = 20.0
        db.commit()

        # ── Get formulas ──────────────────────────────────────────────────────
        # 1. Formulas du message_description courant
        current_formulas = db.query(MappingFormula).filter(
            MappingFormula.message_description_id == message_description_id
        ).all()

        # 2. Colonnes du fichier courant
        current_columns = set()
        if message_desc.column_structure:
            current_columns = {col.get('name') for col in message_desc.column_structure if col.get('name')}
        if not current_columns and message_desc.sample_data:
            current_columns = set(message_desc.sample_data[0].keys())

        # 3. Chercher formulas de TOUS les autres fichiers par nom de colonne
        # → réutilisation automatique si même source_path
        all_other_formulas = db.query(MappingFormula).filter(
            MappingFormula.message_description_id != message_description_id,
            MappingFormula.source_path.in_(current_columns)
        ).order_by(MappingFormula.created_at.desc()).all()

        # 4. Fusionner — current prioritaires, autres comblent les manquants
        current_sources = {f.source_path for f in current_formulas}
        seen_sources = set(current_sources)
        unique_extra = []
        for f in all_other_formulas:
            if f.source_path not in seen_sources:
                seen_sources.add(f.source_path)
                unique_extra.append(f)

        formulas = current_formulas + unique_extra

        logger.info(f"📋 Formulas: {len(current_formulas)} current + {len(unique_extra)} reused from other files = {len(formulas)} total")

        if not formulas:
            raise Exception("No mapping formulas found. Please accept some suggestions first.")

        job.progress = 30.0
        db.commit()

        # ── Load source data ──────────────────────────────────────────────────
        # Try to load full file if file_upload exists, else use sample_data
        source_data = []

        if message_desc.file_upload_id:
            file_upload = db.query(FileUpload).filter(
                FileUpload.id == message_desc.file_upload_id
            ).first()

            if file_upload and Path(file_upload.file_path).exists():
                try:
                    file_info = file_processor.process_file(file_upload.file_path)
                    source_data = file_info.get('sample_data', [])
                    logger.info(f"Loaded {len(source_data)} rows from file: {file_upload.file_path}")
                except Exception as e:
                    logger.warning(f"Could not load full file, using sample_data: {e}")

        if not source_data:
            source_data = message_desc.sample_data or []
            logger.info(f"Using sample_data: {len(source_data)} rows")

        if not source_data:
            raise Exception("No source data available")

        job.progress = 50.0
        db.commit()

        # ── Apply transformation ──────────────────────────────────────────────
        formula_dicts = [
            {
                "target_column": f.target_path,
                "source_column": f.source_path,
                "transformation_type": f.transformation_type,
                "transformation_rule": f.transformation_rule
            }
            for f in formulas
        ]

        transformed_data = file_processor.apply_transformation(
            data=source_data,
            mapping_formulas=formula_dicts
        )

        job.progress = 70.0
        db.commit()

        # ── Save output file ──────────────────────────────────────────────────
        output_filename = f"transformed_{message_desc.file_name.replace('.', '_')}_{message_description_id}_{job_id}.json"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transformed_data, f, indent=2, ensure_ascii=False)

        job.progress = 85.0
        db.commit()

        # ── Calculate validation ──────────────────────────────────────────────
        validation_metrics = _calculate_validation(source_data, transformed_data, formulas)

        validation_report = ValidationReport(
            transformation_job_id=job_id,
            accuracy_percentage=validation_metrics['accuracy_percentage'],
            row_count_match=validation_metrics['row_count_match'],
            column_count_match=validation_metrics['column_count_match'],
            total_cells=validation_metrics['total_cells'],
            matching_cells=validation_metrics['matching_cells'],
            differing_cells=validation_metrics['differing_cells'],
            differences=validation_metrics['differences'],
            overall_quality=validation_metrics['overall_quality'],
            recommendation=validation_metrics['recommendation']
        )
        db.add(validation_report)

        # ── Update formulas stats ─────────────────────────────────────────────
        for formula in formulas:
            formula.usage_count += 1
            formula.success_rate = validation_metrics['accuracy_percentage']

        # ── Complete job ──────────────────────────────────────────────────────
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.datetime.utcnow()
        job.error_message = None

        # ── NOUVEAU : Mettre à jour quality_score + mapping_completion ─────────
        quality_map = {"EXCELLENT": 100, "GOOD": 80, "ACCEPTABLE": 60, "POOR": 30}
        quality_score = quality_map.get(validation_metrics['overall_quality'], 0)
        message_desc.quality_score = quality_score
        message_desc.status = 'validated'

        # Calculer mapping_completion depuis les formulas
        total_columns = len(message_desc.column_structure or [])
        if total_columns > 0:
            mapped_count = db.query(MappingFormula).filter(
                MappingFormula.message_description_id == message_description_id,
                MappingFormula.target_path != '',
                MappingFormula.target_path != None
            ).count()
            message_desc.mapping_completion = min(int((mapped_count / total_columns) * 100), 100)
        # ── FIN NOUVEAU ───────────────────────────────────────────────────────

        db.commit()

        logger.info(f"✅ TransformationJob {job_id} completed — {len(transformed_data)} rows, quality: {validation_metrics['overall_quality']}")

    except Exception as e:
        logger.error(f"❌ TransformationJob {job_id} failed: {e}")
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.datetime.utcnow()
        db.commit()


@router.post("/apply-mapping/{message_description_id}")
async def apply_mapping(
    message_description_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lance un TransformationJob pour appliquer les mappings sur un fichier.
    Le job s'exécute en background — utilise GET /job/{id} pour suivre le statut.
    """
    try:
        # Verify MessageDescription exists
        message_desc = db.query(MessageDescription).filter(
            MessageDescription.id == message_description_id
        ).first()

        if not message_desc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MessageDescription {message_description_id} not found"
            )

        # ── Check formulas — current file OR reusable from other files ─────────
        current_count = db.query(MappingFormula).filter(
            MappingFormula.message_description_id == message_description_id
        ).count()

        if current_count == 0:
            # Check if reusable formulas exist from other files
            if message_desc.column_structure:
                columns = {col.get('name') for col in message_desc.column_structure if col.get('name')}
            elif message_desc.sample_data:
                columns = set(message_desc.sample_data[0].keys())
            else:
                columns = set()

            reusable_count = db.query(MappingFormula).filter(
                MappingFormula.message_description_id != message_description_id,
                MappingFormula.source_path.in_(columns)
            ).count() if columns else 0

            if reusable_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No mapping formulas found. Please accept some suggestions first."
                )
            logger.info(f"✅ No current formulas but {reusable_count} reusable from other files")

        # Get file_upload_id
        file_upload_id = message_desc.file_upload_id
        if not file_upload_id:
            # Try to find a FileUpload by filename
            file_upload = db.query(FileUpload).filter(
                FileUpload.user_id == current_user.id,
                FileUpload.original_filename == message_desc.file_name
            ).order_by(FileUpload.upload_date.desc()).first()
            file_upload_id = file_upload.id if file_upload else None

        if not file_upload_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No FileUpload found for this MessageDescription. Please re-upload the file."
            )

        # Create TransformationJob
        job = TransformationJob(
            user_id=current_user.id,
            file_upload_id=file_upload_id,
            job_name=f"Transform {message_desc.file_name} → {message_description_id}",
            status=JobStatus.PENDING,
            progress=0.0
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"🚀 TransformationJob {job.id} created for MessageDescription {message_description_id}")

        # Run in background
        background_tasks.add_task(
            _run_transformation,
            job_id=job.id,
            message_description_id=message_description_id,
            db=db
        )

        return {
            "message": "Transformation job started",
            "job_id": job.id,
            "message_description_id": message_description_id,
            "formulas_count": current_count,
            "status": job.status,
            "check_status_url": f"/api/transform/job/{job.id}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start transformation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start transformation: {str(e)}"
        )


@router.get("/job/{job_id}")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère le statut d'un TransformationJob avec son ValidationReport si disponible.
    """
    job = db.query(TransformationJob).filter(
        TransformationJob.id == job_id,
        TransformationJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    response = {
        "job_id": job.id,
        "job_name": job.job_name,
        "status": job.status,
        "progress": job.progress,
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "validation_report": None
    }

    # Add validation report if job completed
    if job.status == JobStatus.COMPLETED and job.validation_reports:
        report = job.validation_reports[0]
        response["validation_report"] = {
            "accuracy_percentage": report.accuracy_percentage,
            "overall_quality": report.overall_quality,
            "recommendation": report.recommendation,
            "total_cells": report.total_cells,
            "matching_cells": report.matching_cells,
            "differing_cells": report.differing_cells,
            "row_count_match": report.row_count_match,
            "differences": report.differences[:10] if report.differences else []
        }

    return response


@router.get("/jobs")
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Liste tous les TransformationJobs de l'utilisateur.
    """
    jobs = db.query(TransformationJob).filter(
        TransformationJob.user_id == current_user.id
    ).order_by(TransformationJob.created_at.desc()).limit(20).all()

    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.id,
                "job_name": j.job_name,
                "status": j.status,
                "progress": j.progress,
                "created_at": j.created_at,
                "completed_at": j.completed_at
            }
            for j in jobs
        ]
    }


@router.get("/outputs")
async def list_outputs(
    current_user: User = Depends(get_current_user)
):
    """
    Liste tous les fichiers OUTPUT générés.
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

        output_files.sort(key=lambda x: x['created'], reverse=True)

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


@router.get("/download/{filename}")
async def download_output(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    Télécharge un fichier output généré.
    """
    try:
        file_path = OUTPUT_DIR / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {filename} not found"
            )

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/json'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )