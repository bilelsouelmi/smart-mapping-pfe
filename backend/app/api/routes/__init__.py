from fastapi import APIRouter
from app.api.routes import auth, users, files, message_descriptions, mapping_formulas, transform, mappings
from app.api.routes import transform_mapping
from app.api.routes import config_routes
from app.api.routes import config_consommation_routes
from app.api.routes.validation_routes import router as validation_router
from app.api.routes.ws_receiver_routes import router as ws_receiver_router
from app.api.routes import notifications
from app.api.routes import audit_logs
from app.api.routes import access_requests

api_router = APIRouter()

# Auth routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User routes
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Other routes
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(message_descriptions.router, prefix="/message-descriptions", tags=["message-descriptions"])
api_router.include_router(mapping_formulas.router, prefix="/mapping-formulas", tags=["mapping-formulas"])
api_router.include_router(mappings.router, prefix="/mappings", tags=["mappings"])
api_router.include_router(transform.router, prefix="/transform", tags=["transform"])
api_router.include_router(transform_mapping.router, prefix="/transform", tags=["transform-mapping"])
api_router.include_router(config_routes.router, prefix="/configs", tags=["configs"])
api_router.include_router(config_consommation_routes.router, prefix="/consommation", tags=["config-consommation"])
api_router.include_router(validation_router, prefix="/validation", tags=["validation"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit-logs"])
api_router.include_router(access_requests.router, prefix="/access-requests", tags=["access-requests"])

# Test web service receiver (simulates external system consuming REST pipeline output)
api_router.include_router(ws_receiver_router, prefix="/ws-receiver", tags=["Web Service Receiver"])