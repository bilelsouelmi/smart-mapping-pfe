"""
Pipeline (Consommation) Routes
Supports Config OUT: FILE, REST (web service), RABBITMQ, KAFKA
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import os
import glob
from pathlib import Path

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def get_pipeline_model():
    from app.models.config_consommation import ConfigConsommation
    return ConfigConsommation


def get_config_model():
    from app.models.config import TransportConfig
    return TransportConfig


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    name: str
    config_in_id: int
    mapping_id: int
    config_out_id: int
    description: Optional[str] = None
    is_active: bool = True


class PipelineUpdate(BaseModel):
    """
    Full update schema for a pipeline — mirrors PipelineCreate but every
    field is optional so the client can send only what changed (PATCH-like
    semantics on a PUT endpoint, consistent with MappingUpdate elsewhere
    in this project).
    """
    name: Optional[str] = None
    config_in_id: Optional[int] = None
    mapping_id: Optional[int] = None
    config_out_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PipelineResponse(BaseModel):
    id: int
    name: str
    config_in_id: int
    mapping_id: int
    config_out_id: int
    is_active: bool
    description: Optional[str]
    created_at: datetime
    config_in_name:  Optional[str] = None
    config_in_type:  Optional[str] = None
    mapping_name:    Optional[str] = None
    config_out_name: Optional[str] = None
    config_out_type: Optional[str] = None

    class Config:
        from_attributes = True


# ─── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=PipelineResponse)
async def create_pipeline(
    pipeline: PipelineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    Pipeline = get_pipeline_model()
    db_pipeline = Pipeline(**pipeline.dict(), created_by=current_user.id)
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    return _enrich(db_pipeline)


@router.get("/", response_model=List[PipelineResponse])
async def list_pipelines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    Pipeline = get_pipeline_model()
    pipelines = db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()
    return [_enrich(p) for p in pipelines]


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    Pipeline = get_pipeline_model()
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return _enrich(p)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: int,
    pipeline: PipelineUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a pipeline. All fields are optional — only provided fields are
    changed. Validates that config_in_id / config_out_id / mapping_id, if
    provided, reference existing records before applying the update.
    """
    Pipeline = get_pipeline_model()
    TransportConfig = get_config_model()
    from app.models.mapping import Mapping

    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    update_data = pipeline.dict(exclude_unset=True)

    if "config_in_id" in update_data:
        if not db.query(TransportConfig).filter(TransportConfig.id == update_data["config_in_id"]).first():
            raise HTTPException(status_code=404, detail=f"Config IN {update_data['config_in_id']} not found")

    if "config_out_id" in update_data:
        if not db.query(TransportConfig).filter(TransportConfig.id == update_data["config_out_id"]).first():
            raise HTTPException(status_code=404, detail=f"Config OUT {update_data['config_out_id']} not found")

    if "mapping_id" in update_data:
        if not db.query(Mapping).filter(Mapping.id == update_data["mapping_id"]).first():
            raise HTTPException(status_code=404, detail=f"Mapping {update_data['mapping_id']} not found")

    for field, value in update_data.items():
        setattr(p, field, value)

    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    logger.info(f"Pipeline {pipeline_id} updated by user {current_user.id}: {list(update_data.keys())}")
    return _enrich(p)


@router.delete("/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    Pipeline = get_pipeline_model()
    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # A failed-delivery run (PendingDeliveryRetry) can still point at this
    # pipeline via a nullable pipeline_id — informational only
    # (pipeline_name is stored on the row itself for exactly this reason),
    # so the retry record survives; only the dangling pointer needs
    # clearing. Left as-is, that FK blocks the delete with an unhandled
    # 500 instead of this clean response.
    from app.models.pending_delivery_retry import PendingDeliveryRetry
    db.query(PendingDeliveryRetry).filter(
        PendingDeliveryRetry.pipeline_id == pipeline_id
    ).update({PendingDeliveryRetry.pipeline_id: None}, synchronize_session=False)

    db.delete(p)
    db.commit()
    return {"message": "Pipeline deleted"}


def _apply_mapping_to_mt_text(mt_text: str, mapping_id: int, db: Session):
    """
    Parses raw SWIFT MT text and applies a Mapping's accepted
    MappingElements to build the target ISO 20022 XML — the one real
    transformation implementation for this pipeline engine, shared by
    every Config IN transport (FILE reads it from disk, RabbitMQ/Kafka
    hand over the message body directly) so a queue-sourced pipeline goes
    through the exact same conversion as a file-sourced one instead of
    a separate, unmaintained code path.

    Returns (transformed_xml, iso_target).
    """
    import tempfile, os as _os
    from app.services.swift_txt_parser import SWIFTTextParser
    from app.api.routes.transform_mapping import (
        evaluate_expression, set_xpath_value, build_xml_from_dict,
        ISO_NAMESPACES, ISO_ROOT_ELEMENTS
    )
    from app.models.mapping import Mapping, MappingElement
    from datetime import datetime as dt

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
        tmp.write(mt_text)
        tmp_path = tmp.name
    try:
        parser = SWIFTTextParser()
        parsed = parser.parse(tmp_path)
    finally:
        _os.unlink(tmp_path)

    mt_blocks = parsed.get("mt_blocks", {})
    block4    = mt_blocks.get("block4", {}).get("sub_fields", {})
    source_fields = {}
    for k, v in block4.items():
        val       = v.get("value", "") if isinstance(v, dict) else str(v)
        clean_key = k.lstrip(":")
        source_fields[f"field_{clean_key.replace(':', '')}"] = val
        source_fields[k]             = val
        source_fields[f":{clean_key}:"] = val

    mapping_obj = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    elements    = db.query(MappingElement).filter(
        MappingElement.mapping_id == mapping_id,
        MappingElement.status == "MAPPED"
    ).all()

    target_data = {}
    iso_target  = mapping_obj.target if mapping_obj else "pacs.008.001.08"
    for el in elements:
        value = evaluate_expression(el.expression or "", source_fields, el.target_field or "")
        if not value and el.default_value:
            value = el.default_value
        if value and el.target_field:
            set_xpath_value(target_data, el.target_field, value)

    root_tag  = ISO_ROOT_ELEMENTS.get(iso_target, "Document")
    namespace = ISO_NAMESPACES.get(iso_target, f"urn:iso:std:iso:20022:tech:xsd:{iso_target}")
    grp_hdr   = target_data.get("GrpHdr", {})
    if isinstance(grp_hdr, dict) and "CreDtTm" not in grp_hdr:
        grp_hdr["CreDtTm"] = dt.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        target_data["GrpHdr"] = grp_hdr

    return build_xml_from_dict(target_data, namespace, root_tag, iso_target), iso_target


# ─── Run Pipeline ─────────────────────────────────────────────────────────────

@router.post("/{pipeline_id}/run")
async def run_pipeline(
    pipeline_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manual, on-demand run — thin wrapper around the same core used by
    the background scheduler (see _pipeline_scheduler_loop), so a manual
    click and an automatic tick behave identically."""
    return await _execute_pipeline(pipeline_id, db)


async def _deliver_to_config_out(config_out, output_body: bytes, input_filename_base: str, iso_target_name: str) -> tuple:
    """
    The actual Config OUT delivery for one transport type — extracted out
    of _execute_pipeline so PendingDeliveryRetry's retry endpoint can
    redeliver the SAME already-transformed content through the SAME
    per-transport logic, instead of a second copy that could silently
    drift from what a normal pipeline run does. Returns (status, message),
    exactly what used to be written straight into step3.
    """
    if config_out.transport_type == "FILE":
        try:
            is_xml_output = output_body.strip().startswith(b"<?xml")
            if config_out.file_output_path:
                out_path = config_out.file_output_path
            elif is_xml_output:
                out_path = str(Path(settings.UPLOAD_DIR) / "out" / "xml")
            else:
                out_path = str(Path(settings.UPLOAD_DIR) / "out" / "mt")

            os.makedirs(out_path, exist_ok=True)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            ext = ".xml" if is_xml_output else ".txt"
            if is_xml_output:
                out_filename = f"{input_filename_base}_{iso_target_name}_{timestamp}{ext}"
            else:
                out_filename = f"{input_filename_base}_MT_{timestamp}{ext}"
            out_file = os.path.join(out_path, out_filename)
            with open(out_file, "wb") as f:
                f.write(output_body)
            return "ok", f"{'XML' if is_xml_output else 'MT'} saved to {out_file}"
        except Exception as e:
            return "error", str(e)

    elif config_out.transport_type == "REST":
        try:
            import httpx
            headers = dict(config_out.rest_headers or {})
            headers["Content-Type"] = "application/xml"
            if config_out.rest_auth_type == "BEARER" and config_out.rest_auth_value:
                headers["Authorization"] = f"Bearer {config_out.rest_auth_value}"
            elif config_out.rest_auth_type == "BASIC" and config_out.rest_auth_value:
                headers["Authorization"] = f"Basic {config_out.rest_auth_value}"
            method = (config_out.rest_method or "POST").upper()
            async with httpx.AsyncClient(timeout=10) as client:
                response = await getattr(client, method.lower())(
                    config_out.rest_url,
                    content=output_body,
                    headers=headers
                )
            status = "ok" if response.status_code < 400 else "error"
            message = (
                f"XML sent via {method} to '{config_out.rest_url}' "
                f"— HTTP {response.status_code} ({len(output_body)} bytes)"
            )
            return status, message
        except Exception as e:
            return "error", f"REST web service error: {str(e)}"

    elif config_out.transport_type == "RABBITMQ":
        try:
            import pika
            credentials = pika.PlainCredentials(
                config_out.rabbitmq_username or "guest",
                config_out.rabbitmq_password or "guest"
            )
            params = pika.ConnectionParameters(
                host=config_out.rabbitmq_host or "localhost",
                port=config_out.rabbitmq_port or 5672,
                virtual_host=config_out.rabbitmq_vhost or "/",
                credentials=credentials,
                connection_attempts=1, socket_timeout=3
            )
            conn    = pika.BlockingConnection(params)
            channel = conn.channel()
            channel.queue_declare(
                queue=config_out.rabbitmq_queue or "swift.out",
                durable=True
            )
            channel.basic_publish(
                exchange=config_out.rabbitmq_exchange or "",
                routing_key=config_out.rabbitmq_queue or "swift.out",
                body=output_body
            )
            conn.close()
            message = (
                f"XML published to RabbitMQ queue "
                f"'{config_out.rabbitmq_queue}' ({len(output_body)} bytes)"
            )
            return "ok", message
        except Exception as e:
            return "error", str(e)

    elif config_out.transport_type == "KAFKA":
        try:
            from kafka import KafkaProducer
            kafka_config = {
                "bootstrap_servers": config_out.kafka_bootstrap_servers or "localhost:9092",
                "security_protocol": config_out.kafka_security_protocol or "PLAINTEXT",
            }
            if config_out.kafka_security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
                kafka_config["sasl_mechanism"]      = config_out.kafka_sasl_mechanism or "PLAIN"
                kafka_config["sasl_plain_username"] = config_out.kafka_sasl_username or ""
                kafka_config["sasl_plain_password"] = config_out.kafka_sasl_password or ""
            producer = KafkaProducer(**kafka_config)
            future = producer.send(
                config_out.kafka_topic or "swift.out",
                value=output_body
            )
            future.get(timeout=5)
            producer.flush()
            producer.close()
            message = (
                f"XML published to Kafka topic "
                f"'{config_out.kafka_topic}' ({len(output_body)} bytes)"
            )
            return "ok", message
        except Exception as e:
            return "error", f"Kafka error: {str(e)}"

    return "skipped", "Unknown or unconfigured Config OUT transport type"


async def _execute_pipeline(pipeline_id: int, db: Session) -> dict:
    Pipeline = get_pipeline_model()
    TransportConfig = get_config_model()

    p = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    config_in  = db.query(TransportConfig).filter(TransportConfig.id == p.config_in_id).first()
    config_out = db.query(TransportConfig).filter(TransportConfig.id == p.config_out_id).first()

    results = {"pipeline": p.name, "steps": []}

    # ── STEP 1: Consume from Config IN ────────────────────────────────────────
    step1 = {"step": "Config IN", "type": config_in.transport_type if config_in else "N/A"}
    input_files   = []
    input_content = None

    if config_in:
        if config_in.transport_type == "FILE":
            path     = config_in.file_path or ""
            patterns = (config_in.file_pattern or "*.txt,*.xml").split(",")
            files    = []
            for pattern in patterns:
                files.extend(glob.glob(os.path.join(path, pattern.strip())))
            input_files = files
            step1["status"]  = "ok" if files else "warning"
            step1["message"] = f"Found {len(files)} file(s)" if files else f"No files in {path}"
            step1["files"]   = [os.path.basename(f) for f in files[:5]]

        elif config_in.transport_type == "RABBITMQ":
            try:
                import pika
                credentials = pika.PlainCredentials(
                    config_in.rabbitmq_username or "guest",
                    config_in.rabbitmq_password or "guest"
                )
                params = pika.ConnectionParameters(
                    host=config_in.rabbitmq_host or "localhost",
                    port=config_in.rabbitmq_port or 5672,
                    virtual_host=config_in.rabbitmq_vhost or "/",
                    credentials=credentials,
                    connection_attempts=1, socket_timeout=3
                )
                conn    = pika.BlockingConnection(params)
                channel = conn.channel()
                method, _, body = channel.basic_get(
                    queue=config_in.rabbitmq_queue, auto_ack=True
                )
                conn.close()
                input_content    = body.decode("utf-8") if body else None
                step1["status"]  = "ok" if method else "warning"
                step1["message"] = "Message consumed from RabbitMQ queue" if method else "Queue is empty"
            except Exception as e:
                step1["status"]  = "error"
                step1["message"] = str(e)

        elif config_in.transport_type == "KAFKA":
            try:
                from kafka import KafkaConsumer
                kafka_config = {
                    "bootstrap_servers": config_in.kafka_bootstrap_servers or "localhost:9092",
                    "group_id":          config_in.kafka_group_id or "smart-mapping-group",
                    "security_protocol": config_in.kafka_security_protocol or "PLAINTEXT",
                    "auto_offset_reset": "earliest",
                    "consumer_timeout_ms": 3000,
                }
                if config_in.kafka_security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
                    kafka_config["sasl_mechanism"]      = config_in.kafka_sasl_mechanism or "PLAIN"
                    kafka_config["sasl_plain_username"] = config_in.kafka_sasl_username or ""
                    kafka_config["sasl_plain_password"] = config_in.kafka_sasl_password or ""
                consumer = KafkaConsumer(config_in.kafka_topic, **kafka_config)
                msg = next(consumer, None)
                consumer.close()
                input_content    = msg.value.decode("utf-8") if msg and msg.value else None
                step1["status"]  = "ok" if msg else "warning"
                step1["message"] = f"Message consumed from Kafka topic '{config_in.kafka_topic}'" \
                                   if msg else f"No messages in topic '{config_in.kafka_topic}'"
            except Exception as e:
                step1["status"]  = "error"
                step1["message"] = str(e)

        elif config_in.transport_type == "REST":
            step1["status"]  = "ok"
            step1["message"] = f"REST IN endpoint: {config_in.rest_url}"

    results["steps"].append(step1)

    # ── STEP 2: Apply Mapping ─────────────────────────────────────────────────
    step2 = {"step": "Mapping", "type": "TRANSFORM"}
    transformed_content = None
    input_filename_base = "output"
    iso_target_name = "xml"
    try:
        if input_files:
            file_path = input_files[0]
            input_filename_base = os.path.splitext(os.path.basename(file_path))[0]
            transformed_content, iso_target = _apply_mapping_to_mt_text(
                Path(file_path).read_text(encoding='utf-8'), p.mapping_id, db
            )
            iso_target_name = iso_target.replace(".", "").replace("-", "")
            step2["status"]  = "ok"
            step2["message"] = f"Transformed '{os.path.basename(file_path)}' → {iso_target}"

        elif input_content:
            # Same real transformation as the FILE branch above — a
            # RabbitMQ/Kafka message is raw MT text just like an uploaded
            # file, not something already in the target format. This used
            # to just do `transformed_content = input_content` (a literal
            # passthrough reporting "Mapping applied" while doing nothing),
            # so a queue-sourced pipeline silently delivered the untouched
            # SWIFT message instead of the converted XML.
            input_filename_base = "queue_message"
            transformed_content, iso_target = _apply_mapping_to_mt_text(
                input_content, p.mapping_id, db
            )
            iso_target_name = iso_target.replace(".", "").replace("-", "")
            step2["status"]  = "ok"
            step2["message"] = f"Mapping '{p.mapping.name if p.mapping else 'N/A'}' applied → {iso_target}"
        else:
            step2["status"]  = "warning"
            step2["message"] = "No input data to transform"

        if transformed_content:
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            is_xml = transformed_content.strip().startswith("<?xml")
            ext = ".xml" if is_xml else ".txt"
            audit_dir = Path(settings.UPLOAD_DIR).parent / "outputs"
            audit_dir.mkdir(parents=True, exist_ok=True)
            if is_xml:
                audit_filename = f"{input_filename_base}_{iso_target_name}_{timestamp}{ext}"
            else:
                audit_filename = f"{input_filename_base}_MT_{timestamp}{ext}"
            audit_path = audit_dir / audit_filename
            with open(audit_path, "w", encoding="utf-8") as f:
                f.write(transformed_content)
            step2["audit_copy"] = str(audit_path)
            step2["output_filename"] = audit_filename

    except Exception as e:
        logger.error(f"Mapping error: {e}")
        step2["status"]  = "warning"
        step2["message"] = f"Mapping warning: {str(e)[:150]}"

    results["steps"].append(step2)

    # ── STEP 3: Send to Config OUT ────────────────────────────────────────────
    step3 = {"step": "Config OUT", "type": config_out.transport_type if config_out else "N/A"}

    # Nothing was actually produced (empty Config IN, a parse/mapping
    # error, etc. — see step2's status above) — there is nothing to
    # deliver. Skip Config OUT entirely rather than writing a "NO_DATA"
    # placeholder: on an idle Pipeline the background scheduler (see
    # _pipeline_scheduler_loop) calls this every poll interval forever, so
    # without this guard every empty tick would silently write another
    # garbage file/message to the destination.
    if not transformed_content:
        step3["status"]  = "skipped"
        step3["message"] = "No data to deliver — nothing produced by the Mapping step"
        results["steps"].append(step3)
        statuses = [s.get("status") for s in results["steps"]]
        results["status"] = (
            "error"   if "error"   in statuses else
            "warning" if "warning" in statuses else
            "success"
        )
        results["message"] = (
            "Pipeline completed with warnings" if results["status"] == "warning" else "Pipeline failed"
        )
        return results

    output_body = transformed_content.encode("utf-8")

    if config_out:
        status, message = await _deliver_to_config_out(
            config_out, output_body, input_filename_base, iso_target_name
        )
        step3["status"] = status
        step3["message"] = message

        # Delivery failed but the transform itself (step2) succeeded — the
        # audit copy on disk is the only surviving record of this output
        # for a Kafka/RabbitMQ-sourced run (that message is already gone
        # from the source queue by now). Persist a retry row so this isn't
        # silently lost; see PendingDeliveryRetry's docstring.
        if status == "error" and step2.get("output_filename"):
            from app.models.pending_delivery_retry import PendingDeliveryRetry
            # The source file is deliberately left in place on failure (see
            # the "Only move on a clean success" comment below), so the
            # background scheduler picks the SAME still-stuck delivery back
            # up every ~30s. Without this lookup, each poll tick inserted a
            # brand new row instead of updating the existing one — a wrong
            # Config OUT URL left running would silently pile up dozens of
            # duplicate "pending" entries for what is really just one
            # unresolved delivery, exactly like a manual Retry click already
            # updates attempt_count on the same row instead of duplicating it.
            existing_retry = db.query(PendingDeliveryRetry).filter(
                PendingDeliveryRetry.pipeline_id == p.id,
                PendingDeliveryRetry.status == "pending"
            ).first()
            if existing_retry:
                existing_retry.attempt_count += 1
                existing_retry.output_filename = step2["output_filename"]
                existing_retry.error_message = message
                existing_retry.last_attempt_at = datetime.utcnow()
            else:
                db.add(PendingDeliveryRetry(
                    pipeline_id=p.id,
                    pipeline_name=p.name,
                    config_out_id=config_out.id,
                    transport_type=config_out.transport_type,
                    output_filename=step2["output_filename"],
                    error_message=message,
                    status="pending",
                ))
            db.commit()

    results["steps"].append(step3)

    statuses = [s.get("status") for s in results["steps"]]
    results["status"] = (
        "error"   if "error"   in statuses else
        "warning" if "warning" in statuses else
        "success"
    )
    results["message"] = (
        "Pipeline executed successfully" if results["status"] == "success" else
        "Pipeline completed with warnings" if results["status"] == "warning" else
        "Pipeline failed"
    )

    # A FILE-sourced Config IN doesn't consume anything by itself — every
    # run just globs the same folder. Without moving the file once it's
    # fully delivered, the background scheduler (see
    # _pipeline_scheduler_loop) would reprocess the same file forever on
    # every poll tick, and a manual re-click of Run would silently
    # reprocess it too. Only move on a clean "success" — leave the file in
    # place on error/warning so the next attempt (manual or scheduled)
    # retries delivery instead of losing it into processed/ unsent.
    if (config_in and config_in.transport_type == "FILE"
            and input_files and results["status"] == "success"):
        try:
            consumed_path = input_files[0]
            processed_dir = os.path.join(config_in.file_path or "", "processed")
            os.makedirs(processed_dir, exist_ok=True)
            import shutil
            shutil.move(consumed_path, os.path.join(processed_dir, os.path.basename(consumed_path)))
        except Exception as e:
            logger.warning(f"Could not move consumed file to processed/: {e}")

    return results


# ─── Background scheduler ──────────────────────────────────────────────────────

async def _pipeline_scheduler_loop():
    """Started once at app startup (see main.py). Polls every active
    Pipeline on a fixed interval and runs it exactly like a manual click
    of Start would — same _execute_pipeline, so a FILE Config IN with a
    new file, or a RabbitMQ/Kafka queue with a new message, gets consumed
    and delivered without anyone touching the UI. Each pipeline gets its
    own try/except so one failing pipeline (bad credentials, unreachable
    host) never stops the others from being polled."""
    import asyncio
    from app.database import SessionLocal

    interval = settings.PIPELINE_POLL_INTERVAL_SECONDS
    logger.info(f"🔁 Pipeline auto-consumption scheduler started (every {interval}s)")

    while True:
        await asyncio.sleep(interval)
        db = SessionLocal()
        try:
            Pipeline = get_pipeline_model()
            active_pipelines = db.query(Pipeline).filter(Pipeline.is_active == True).all()  # noqa: E712
            for p in active_pipelines:
                try:
                    result = await _execute_pipeline(p.id, db)
                    if result.get("status") != "warning" or (result.get("steps") and result["steps"][0].get("status") != "warning"):
                        logger.info(f"🔁 Auto-run pipeline '{p.name}' (id={p.id}): {result.get('status')}")
                except Exception as e:
                    logger.error(f"🔁 Auto-run pipeline id={p.id} failed: {e}")
        except Exception as e:
            logger.error(f"🔁 Pipeline scheduler tick failed: {e}")
        finally:
            db.close()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _enrich(p) -> PipelineResponse:
    r = PipelineResponse.from_orm(p)
    if p.config_in:
        r.config_in_name = p.config_in.name
        r.config_in_type = p.config_in.transport_type
    if p.mapping:
        r.mapping_name = p.mapping.name
    if p.config_out:
        r.config_out_name = p.config_out.name
        r.config_out_type = p.config_out.transport_type
    return r