from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class ColumnStructure(BaseModel):
    name: str
    type: str  # string, integer, date, etc.
    format: Optional[str] = None  # e.g., "DD/MM/YYYY" for dates


class MessageDescriptionBase(BaseModel):
    file_name: str
    file_type: str = Field(..., pattern="^(CSV|XML|JSON|Excel)$")
    source_system: Optional[str] = None
    target_system: Optional[str] = None
    business_domain: Optional[str] = None


class MessageDescriptionCreate(MessageDescriptionBase):
    column_structure: Optional[List[ColumnStructure]] = None
    sample_data: Optional[List[Dict[str, Any]]] = None


class MessageDescriptionUpdate(BaseModel):
    file_name: Optional[str] = None
    file_type: Optional[str] = Field(None, pattern="^(CSV|XML|JSON|Excel)$")
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

    class Config:
        from_attributes = True