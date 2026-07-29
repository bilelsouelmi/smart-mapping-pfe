"""
Transport Config API Routes
POST /api/configs/             - Create config IN or OUT
GET  /api/configs/             - List all configs
GET  /api/configs/{id}         - Get config
PUT  /api/configs/{id}         - Update config
DELETE /api/configs/{id}       - Delete config
POST /api/configs/{id}/test    - Test connection
POST /api/configs/{id}/trigger - Manually trigger IN config
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging
import os
import glob
from datetime import datetime

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TransportConfigCreate(BaseModel):
    name: str
    direction: str          # IN or OUT
    transport_type: str     # FILE, REST, RABBITMQ, KAFKA
    mapping_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True

    # FILE
    file_path:        Optional[str] = None
    file_pattern:     Optional[str] = "*.txt,*.xml"
    file_output_path: Optional[str] = None

    # REST
    rest_url:        Optional[str] = None
    rest_method:     Optional[str] = "POST"
    rest_headers:    Optional[dict] = None
    rest_auth_type:  Optional[str] = "NONE"
    rest_auth_value: Optional[str] = None

    # RabbitMQ
    rabbitmq_host:        Optional[str] = "localhost"
    rabbitmq_port:        Optional[int] = 5672
    rabbitmq_vhost:       Optional[str] = "/"
    rabbitmq_username:    Optional[str] = "guest"
    rabbitmq_password:    Optional[str] = "guest"
    rabbitmq_queue:       Optional[str] = None
    rabbitmq_exchange:    Optional[str] = ""
    rabbitmq_routing_key: Optional[str] = None

    # Kafka
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic:             Optional[str] = None
    kafka_group_id:          Optional[str] = "smart-mapping-group"
    kafka_security_protocol: Optional[str] = "PLAINTEXT"
    kafka_sasl_mechanism:    Optional[str] = "PLAIN"
    kafka_sasl_username:     Optional[str] = None
    kafka_sasl_password:     Optional[str] = None


class TransportConfigResponse(BaseModel):
    id:            int
    name:          str
    direction:     str
    transport_type: str
    mapping_id:    Optional[int]
    is_active:     bool
    description:   Optional[str]

    # FILE
    file_path:        Optional[str]
    file_pattern:     Optional[str]
    file_output_path: Optional[str]

    # REST
    rest_url:        Optional[str]
    rest_method:     Optional[str]
    rest_headers:    Optional[dict]
    rest_auth_type:  Optional[str]

    # RabbitMQ
    rabbitmq_host:        Optional[str]
    rabbitmq_port:        Optional[int]
    rabbitmq_vhost:       Optional[str]
    rabbitmq_username:    Optional[str]
    rabbitmq_queue:       Optional[str]
    rabbitmq_exchange:    Optional[str]
    rabbitmq_routing_key: Optional[str]

    # Kafka
    kafka_bootstrap_servers: Optional[str]
    kafka_topic:             Optional[str]
    kafka_group_id:          Optional[str]
    kafka_security_protocol: Optional[str]
    kafka_sasl_mechanism:    Optional[str]
    kafka_sasl_username:     Optional[str]

    created_at:   datetime
    mapping_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Helper ───────────────────────────────────────────────────────────────────

def get_model():
    from app.models.config import TransportConfig
    return TransportConfig


# ─── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=TransportConfigResponse)
async def create_config(
    config: TransportConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    db_config = TransportConfig(**config.dict(), created_by=current_user.id)
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    result = TransportConfigResponse.from_orm(db_config)
    if db_config.mapping:
        result.mapping_name = db_config.mapping.name
    return result


@router.get("/", response_model=List[TransportConfigResponse])
async def list_configs(
    direction: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    query = db.query(TransportConfig)
    if direction:
        query = query.filter(TransportConfig.direction == direction.upper())
    configs = query.order_by(TransportConfig.created_at.desc()).all()
    results = []
    for c in configs:
        r = TransportConfigResponse.from_orm(c)
        if c.mapping:
            r.mapping_name = c.mapping.name
        results.append(r)
    return results


@router.get("/{config_id}", response_model=TransportConfigResponse)
async def get_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    config = db.query(TransportConfig).filter(TransportConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    result = TransportConfigResponse.from_orm(config)
    if config.mapping:
        result.mapping_name = config.mapping.name
    return result


@router.put("/{config_id}", response_model=TransportConfigResponse)
async def update_config(
    config_id: int,
    config: TransportConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    db_config = db.query(TransportConfig).filter(TransportConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    for key, value in config.dict().items():
        setattr(db_config, key, value)
    db.commit()
    db.refresh(db_config)
    return TransportConfigResponse.from_orm(db_config)


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    config = db.query(TransportConfig).filter(TransportConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # Two tables can reference this config by id:
    #   - ConfigConsommation.config_in_id/config_out_id (NOT NULL) — an
    #     active pipeline actually needs this config to run. Can't
    #     silently null or delete that out from under the user, so it
    #     blocks with a clear message instead of a raw 500.
    #   - PendingDeliveryRetry.config_out_id (nullable) — just an
    #     informational "which config this was headed to" link; the
    #     retry record itself must survive, so only the dangling pointer
    #     needs clearing.
    from app.models.config_consommation import ConfigConsommation
    from app.models.pending_delivery_retry import PendingDeliveryRetry

    blocking_pipelines = db.query(ConfigConsommation.name).filter(
        (ConfigConsommation.config_in_id == config_id) |
        (ConfigConsommation.config_out_id == config_id)
    ).all()
    if blocking_pipelines:
        names = ", ".join(f'"{n}"' for (n,) in blocking_pipelines)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete this config: still used by active pipeline configuration(s) {names}. "
                   f"Remove or reassign {'those pipelines' if len(blocking_pipelines) > 1 else 'that pipeline'} first."
        )

    db.query(PendingDeliveryRetry).filter(
        PendingDeliveryRetry.config_out_id == config_id
    ).update({PendingDeliveryRetry.config_out_id: None}, synchronize_session=False)

    db.delete(config)
    db.commit()
    return {"message": "Config deleted"}


# ─── Test Connection ───────────────────────────────────────────────────────────

@router.post("/{config_id}/test")
async def test_connection(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    TransportConfig = get_model()
    config = db.query(TransportConfig).filter(TransportConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    # ── FILE ──────────────────────────────────────────────────────────────────
    if config.transport_type == "FILE":
        path = config.file_path or config.file_output_path or ""
        exists = os.path.exists(path) if path else False
        return {
            "status": "ok" if exists else "warning",
            "message": f"Path {'exists' if exists else 'does not exist'}: {path}"
        }

    # ── REST ──────────────────────────────────────────────────────────────────
    elif config.transport_type == "REST":
        try:
            import httpx
            headers = config.rest_headers or {}
            if config.rest_auth_type == "BEARER" and config.rest_auth_value:
                headers["Authorization"] = f"Bearer {config.rest_auth_value}"
            elif config.rest_auth_type == "BASIC" and config.rest_auth_value:
                headers["Authorization"] = f"Basic {config.rest_auth_value}"
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(config.rest_url, headers=headers)
            return {
                "status": "ok",
                "message": f"REST endpoint reachable — HTTP {r.status_code}"
            }
        except Exception as e:
            return {"status": "error", "message": f"REST endpoint unreachable: {str(e)}"}

    # ── RABBITMQ ──────────────────────────────────────────────────────────────
    elif config.transport_type == "RABBITMQ":
        try:
            import pika
            credentials = pika.PlainCredentials(
                config.rabbitmq_username or "guest",
                config.rabbitmq_password or "guest"
            )
            params = pika.ConnectionParameters(
                host=config.rabbitmq_host or "localhost",
                port=config.rabbitmq_port or 5672,
                virtual_host=config.rabbitmq_vhost or "/",
                credentials=credentials,
                connection_attempts=1,
                socket_timeout=3
            )
            conn = pika.BlockingConnection(params)
            conn.close()
            return {"status": "ok", "message": "RabbitMQ connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"RabbitMQ connection failed: {str(e)}"}

    # ── KAFKA ─────────────────────────────────────────────────────────────────
    elif config.transport_type == "KAFKA":
        try:
            from kafka import KafkaAdminClient
            kafka_config = {
                "bootstrap_servers": config.kafka_bootstrap_servers or "localhost:9092",
                "security_protocol": config.kafka_security_protocol or "PLAINTEXT",
                "request_timeout_ms": 3000,
            }
            if config.kafka_security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
                kafka_config["sasl_mechanism"]       = config.kafka_sasl_mechanism or "PLAIN"
                kafka_config["sasl_plain_username"]  = config.kafka_sasl_username or ""
                kafka_config["sasl_plain_password"]  = config.kafka_sasl_password or ""
            admin = KafkaAdminClient(**kafka_config)
            topics = admin.list_topics()
            admin.close()
            topic_info = f"— topic '{config.kafka_topic}' {'exists' if config.kafka_topic in topics else 'not found'}" \
                         if config.kafka_topic else ""
            return {
                "status": "ok",
                "message": f"Kafka connection successful {topic_info}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Kafka connection failed: {str(e)}"}

    return {"status": "unknown", "message": "Unknown transport type"}


# ─── Trigger IN config ────────────────────────────────────────────────────────

@router.post("/{config_id}/trigger")
async def trigger_config(
    config_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger an IN config to consume one message/file."""
    TransportConfig = get_model()
    config = db.query(TransportConfig).filter(
        TransportConfig.id == config_id,
        TransportConfig.direction == "IN"
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="IN Config not found")

    # ── FILE ──────────────────────────────────────────────────────────────────
    if config.transport_type == "FILE":
        path = config.file_path or ""
        patterns = (config.file_pattern or "*.txt,*.xml").split(",")
        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(path, pattern.strip())))
        if not files:
            return {"status": "no_files", "message": f"No files found in {path}"}
        return {
            "status": "found",
            "message": f"Found {len(files)} file(s)",
            "files": [os.path.basename(f) for f in files[:10]]
        }

    # ── RABBITMQ ──────────────────────────────────────────────────────────────
    elif config.transport_type == "RABBITMQ":
        try:
            import pika
            credentials = pika.PlainCredentials(
                config.rabbitmq_username or "guest",
                config.rabbitmq_password or "guest"
            )
            params = pika.ConnectionParameters(
                host=config.rabbitmq_host or "localhost",
                port=config.rabbitmq_port or 5672,
                virtual_host=config.rabbitmq_vhost or "/",
                credentials=credentials,
                connection_attempts=1,
                socket_timeout=3
            )
            conn = pika.BlockingConnection(params)
            channel = conn.channel()
            method_frame, _, body = channel.basic_get(
                queue=config.rabbitmq_queue,
                auto_ack=False
            )
            if method_frame:
                channel.basic_ack(method_frame.delivery_tag)
                conn.close()
                return {
                    "status": "ok",
                    "message": "Message consumed from RabbitMQ queue",
                    "content_preview": body.decode("utf-8")[:200] if body else ""
                }
            else:
                conn.close()
                return {"status": "empty", "message": "Queue is empty"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── KAFKA ─────────────────────────────────────────────────────────────────
    elif config.transport_type == "KAFKA":
        try:
            from kafka import KafkaConsumer
            kafka_config = {
                "bootstrap_servers": config.kafka_bootstrap_servers or "localhost:9092",
                "group_id":          config.kafka_group_id or "smart-mapping-group",
                "security_protocol": config.kafka_security_protocol or "PLAINTEXT",
                "auto_offset_reset": "earliest",
                "consumer_timeout_ms": 3000,
            }
            if config.kafka_security_protocol in ("SASL_PLAINTEXT", "SASL_SSL"):
                kafka_config["sasl_mechanism"]      = config.kafka_sasl_mechanism or "PLAIN"
                kafka_config["sasl_plain_username"] = config.kafka_sasl_username or ""
                kafka_config["sasl_plain_password"] = config.kafka_sasl_password or ""
            consumer = KafkaConsumer(config.kafka_topic, **kafka_config)
            msg = next(consumer, None)
            consumer.close()
            if msg:
                return {
                    "status": "ok",
                    "message": f"Message consumed from Kafka topic '{config.kafka_topic}'",
                    "content_preview": msg.value.decode("utf-8")[:200] if msg.value else ""
                }
            return {"status": "empty", "message": f"No messages in topic '{config.kafka_topic}'"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── REST (IN) ─────────────────────────────────────────────────────────────
    elif config.transport_type == "REST":
        return {"status": "ok", "message": f"REST IN endpoint: {config.rest_url}"}

    return {"status": "ok", "message": "Trigger executed"}