from fastapi import APIRouter
from app.api.routes import auth, users, files, message_descriptions, mapping_formulas, transform, standard_elements

api_router = APIRouter()

# Auth routes (no prefix, public)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User routes (protected)
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Other routes (protected)
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(message_descriptions.router, prefix="/message-descriptions", tags=["message-descriptions"])
api_router.include_router(mapping_formulas.router, prefix="/mapping-formulas", tags=["mapping-formulas"])
api_router.include_router(transform.router, prefix="/transform", tags=["transform"])
api_router.include_router(standard_elements.router, prefix="/standard-elements", tags=["standard-elements"])
