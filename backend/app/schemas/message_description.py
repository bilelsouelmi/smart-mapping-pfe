from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class ColumnStructure(BaseModel):
    name: str
    type: str  # string, integer, date, etc.
    format: Optional[str] = None  # e.g., "DD/MM/YYYY" for dates


class MessageDescriptionBase(BaseModel):
    file_name: str
    file_type: str = Field(..., pattern="^(CSV|XML|XML_MT|JSON|Excel)$")
    source_system: Optional[str] = None
    target_system: Optional[str] = None
    business_domain: Optional[str] = None


class MessageDescriptionCreate(MessageDescriptionBase):
    column_structure: Optional[List[ColumnStructure]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None


class MessageDescriptionUpdate(BaseModel):
    file_name: Optional[str] = None
    file_type: Optional[str] = Field(None, pattern="^(CSV|XML|XML_MT|JSON|Excel)$")
    source_system: Optional[str] = None
    target_system: Optional[str] = None
    business_domain: Optional[str] = None
    column_structure: Optional[List[ColumnStructure]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None


class MessageDescriptionResponse(MessageDescriptionBase):
    id: int
    user_id: int
    column_structure: Optional[List[Dict[str, Any]]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # ── NOUVEAU : MT fields ───────────────────────────────────────────────────
    mt_type: Optional[str] = None
    iso_target: Optional[str] = None
    mt_blocks: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    mapping_completion: Optional[int] = None
    quality_score: Optional[int] = None
    # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

    class Config:
        from_attributes = True