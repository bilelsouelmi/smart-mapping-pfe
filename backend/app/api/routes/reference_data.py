from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.models.reference_data import ReferenceData
from app.services.audit_service import log_action
from app.services.reference_data_import import import_reference_data_csvs
from app.database import get_db

router = APIRouter()

# Free-form on purpose (not an enum) — the same reasoning as Business
# Variables' var_type: new code lists (e.g. a future "PURPOSE_CODE"
# category) shouldn't need a code change to introduce, only a new row.
CATEGORIES = ("ISO_CURRENCY", "COUNTRY", "CHARGE_CODE")


class ReferenceDataCreate(BaseModel):
    category: str
    code: str
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ReferenceDataUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ReferenceDataResponse(BaseModel):
    id: int
    category: str
    code: str
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool
    updated_by_username: Optional[str] = None
    updated_at: Optional[datetime] = None


def _enrich(r: ReferenceData) -> ReferenceDataResponse:
    # Built field-by-field rather than ReferenceDataResponse.model_validate(r,
    # from_attributes=True): a response field named "metadata" would auto-
    # populate from r.metadata, which on any SQLAlchemy model is the
    # inherited Base.metadata (table schema object, not our JSONB column)
    # — Pydantic would then fail validation trying to coerce that into
    # Optional[dict]. Reading r.meta_data explicitly here sidesteps that
    # collision entirely.
    return ReferenceDataResponse(
        id=r.id,
        category=r.category,
        code=r.code,
        name=r.name,
        description=r.description,
        metadata=r.meta_data,
        is_active=r.is_active,
        updated_by_username=r.updater.username if r.updater else None,
        updated_at=r.updated_at,
    )


def _require_admin(current_user: User):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("/categories")
def list_categories(current_user: User = Depends(get_current_user)):
    """Fixed-ish list for the frontend's category selector — see the
    CATEGORIES comment on why this isn't a hard enum."""
    return list(CATEGORIES)


@router.post("/import")
def import_dataset(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin-only bulk load of dataset/lookup_currencies.csv and
    dataset/lookup_country_codes.csv into ReferenceData — insert-or-update
    by (category, code), safe to re-run whenever the CSVs change."""
    _require_admin(current_user)
    result = import_reference_data_csvs(db, updated_by=current_user.id)
    total = sum(sum(v.values()) for v in result.values())
    log_action(
        db, current_user, action="import", entity_type="ReferenceData",
        details=(
            f"Imported reference data: currencies "
            f"({result['currencies']['inserted']} new, {result['currencies']['updated']} updated), "
            f"countries ({result['countries']['inserted']} new, {result['countries']['updated']} updated)"
        )
    )
    db.commit()
    from app.api.routes.transform_mapping import invalidate_reference_data_cache
    invalidate_reference_data_cache()
    return {"message": f"Imported/updated {total} reference data entries", **result}


@router.get("/", response_model=List[ReferenceDataResponse])
def list_reference_data(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Read access for everyone — these are the code lists live
    Validation Rules check field values against (see validation_routes.py's
    reference_category-driven check), so a non-admin proposing a Message
    Description benefits from seeing what's actually valid. Only writes
    are admin-gated."""
    query = db.query(ReferenceData)
    if category:
        query = query.filter(ReferenceData.category == category)
    rows = query.order_by(ReferenceData.category, ReferenceData.code).all()
    return [_enrich(r) for r in rows]


@router.get("/{row_id}", response_model=ReferenceDataResponse)
def get_reference_data(
    row_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    row = db.query(ReferenceData).filter(ReferenceData.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Reference data entry not found")
    return _enrich(row)


@router.post("/", response_model=ReferenceDataResponse, status_code=status.HTTP_201_CREATED)
def create_reference_data(
    payload: ReferenceDataCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)

    existing = db.query(ReferenceData).filter(
        ReferenceData.category == payload.category,
        ReferenceData.code == payload.code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"\"{payload.code}\" already exists under {payload.category}")

    row = ReferenceData(
        category=payload.category,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        meta_data=payload.metadata,
        is_active=payload.is_active,
        updated_by=current_user.id,
    )
    db.add(row)
    log_action(
        db, current_user, action="create", entity_type="ReferenceData",
        details=f"Created {payload.category} \"{payload.code}\" ({payload.name})"
    )
    db.commit()
    db.refresh(row)
    from app.api.routes.transform_mapping import invalidate_reference_data_cache
    invalidate_reference_data_cache()
    return _enrich(row)


@router.put("/{row_id}", response_model=ReferenceDataResponse)
def update_reference_data(
    row_id: int,
    payload: ReferenceDataUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    row = db.query(ReferenceData).filter(ReferenceData.id == row_id).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Reference data entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    # "metadata" is the public API name; the ORM column/attribute is
    # meta_data (see ReferenceData's docstring for why) — everything else
    # maps straight across by name.
    if "metadata" in update_data:
        row.meta_data = update_data.pop("metadata")
    for field, val in update_data.items():
        setattr(row, field, val)
    row.updated_by = current_user.id

    log_action(
        db, current_user, action="update", entity_type="ReferenceData",
        entity_id=row.id,
        details=f"Updated {row.category} \"{row.code}\" ({row.name}, active={row.is_active})"
    )
    db.commit()
    db.refresh(row)
    from app.api.routes.transform_mapping import invalidate_reference_data_cache
    invalidate_reference_data_cache()
    return _enrich(row)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference_data(
    row_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _require_admin(current_user)
    row = db.query(ReferenceData).filter(ReferenceData.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Reference data entry not found")

    log_action(
        db, current_user, action="delete", entity_type="ReferenceData",
        details=f"Deleted {row.category} \"{row.code}\" ({row.name})"
    )
    db.delete(row)
    db.commit()
    from app.api.routes.transform_mapping import invalidate_reference_data_cache
    invalidate_reference_data_cache()
    return None
