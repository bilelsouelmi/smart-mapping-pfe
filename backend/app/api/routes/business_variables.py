from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.models.business_variable import BusinessVariable
from app.services.audit_service import log_action
from app.database import get_db

router = APIRouter()

VALID_TYPES = ("STRING", "INTEGER", "DECIMAL", "BOOLEAN")


class BusinessVariableCreate(BaseModel):
    name: str
    value: str
    var_type: str = "STRING"
    description: Optional[str] = None
    currency: Optional[str] = None


class BusinessVariableUpdate(BaseModel):
    value: Optional[str] = None
    var_type: Optional[str] = None
    description: Optional[str] = None
    currency: Optional[str] = None


class BusinessVariableResponse(BaseModel):
    id: int
    name: str
    value: str
    var_type: str
    description: Optional[str] = None
    currency: Optional[str] = None
    updated_by_username: Optional[str] = None

    class Config:
        from_attributes = True


def _enrich(v: BusinessVariable) -> BusinessVariableResponse:
    resp = BusinessVariableResponse.model_validate(v)
    resp.updated_by_username = v.updater.username if v.updater else None
    return resp


def _require_admin(current_user: User):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("/", response_model=List[BusinessVariableResponse])
def list_business_variables(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Read access for everyone — these are the constants that drive live
    transformations (thresholds, retention periods, feature flags), and
    a non-admin proposing a Message Description benefits from seeing
    what SANCTIONS_SCREENING_ENABLED or LARGE_AMOUNT_THRESHOLD actually
    is. Only writes are admin-gated.
    """
    variables = db.query(BusinessVariable).order_by(BusinessVariable.name).all()
    return [_enrich(v) for v in variables]


@router.post("/", response_model=BusinessVariableResponse, status_code=status.HTTP_201_CREATED)
def create_business_variable(
    payload: BusinessVariableCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    if payload.var_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"var_type must be one of {VALID_TYPES}")

    existing = db.query(BusinessVariable).filter(BusinessVariable.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A variable named \"{payload.name}\" already exists")

    var = BusinessVariable(
        name=payload.name,
        value=payload.value,
        var_type=payload.var_type,
        description=payload.description,
        currency=payload.currency,
        updated_by=current_user.id,
    )
    db.add(var)
    log_action(
        db, current_user, action="create", entity_type="BusinessVariable",
        details=f"Created \"{payload.name}\" = {payload.value}"
    )
    db.commit()
    db.refresh(var)
    return _enrich(var)


@router.put("/{variable_id}", response_model=BusinessVariableResponse)
def update_business_variable(
    variable_id: int,
    payload: BusinessVariableUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    var = db.query(BusinessVariable).filter(BusinessVariable.id == variable_id).with_for_update().first()
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")

    if payload.var_type is not None and payload.var_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"var_type must be one of {VALID_TYPES}")

    old_value = var.value
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(var, field, val)
    var.updated_by = current_user.id

    log_action(
        db, current_user, action="update", entity_type="BusinessVariable",
        entity_id=var.id,
        details=f"Updated \"{var.name}\": {old_value} -> {var.value}" if "value" in update_data else f"Updated \"{var.name}\""
    )
    db.commit()
    db.refresh(var)

    from app.api.routes.transform_mapping import invalidate_global_variables_cache
    invalidate_global_variables_cache()

    return _enrich(var)


@router.delete("/{variable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_variable(
    variable_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    var = db.query(BusinessVariable).filter(BusinessVariable.id == variable_id).first()
    if not var:
        raise HTTPException(status_code=404, detail="Variable not found")

    log_action(
        db, current_user, action="delete", entity_type="BusinessVariable",
        details=f"Deleted \"{var.name}\" (was {var.value})"
    )
    db.delete(var)
    db.commit()

    from app.api.routes.transform_mapping import invalidate_global_variables_cache
    invalidate_global_variables_cache()
