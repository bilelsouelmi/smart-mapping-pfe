from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class MappingStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class MappingElementStatus(str, Enum):
    PENDING = "pending"
    MAPPED = "mapped"
    SKIPPED = "skipped"


# ── MappingElement Schemas ─────────────────────────────────────────────────────

class MappingElementBase(BaseModel):
    source_field: str = Field(..., max_length=500, description="Source field tag e.g. :20:")
    source_xpath: Optional[str] = Field(None, max_length=500)
    target_field: str = Field(..., max_length=500, description="Target ISO 20022 field e.g. GrpHdr/MsgId")
    target_xpath: Optional[str] = Field(None, max_length=500)
    expression: Optional[str] = None
    is_mandatory: bool = False
    default_value: Optional[str] = Field(None, max_length=500)


class MappingElementCreate(MappingElementBase):
    mapping_id: int
    msg_desc_element_id: Optional[int] = None
    mapping_formula_id: Optional[int] = None
    status: Optional[MappingElementStatus] = MappingElementStatus.PENDING


class MappingElementUpdate(BaseModel):
    source_field: Optional[str] = Field(None, max_length=500)
    source_xpath: Optional[str] = Field(None, max_length=500)
    target_field: Optional[str] = Field(None, max_length=500)
    target_xpath: Optional[str] = Field(None, max_length=500)
    expression: Optional[str] = None
    is_mandatory: Optional[bool] = None
    default_value: Optional[str] = Field(None, max_length=500)
    msg_desc_element_id: Optional[int] = None
    mapping_formula_id: Optional[int] = None
    status: Optional[MappingElementStatus] = None


class MappingElementResponse(MappingElementBase):
    id: int
    mapping_id: int
    msg_desc_element_id: Optional[int] = None
    mapping_formula_id: Optional[int] = None
    status: MappingElementStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Mapping Schemas ────────────────────────────────────────────────────────────

class MappingBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source: str = Field(..., max_length=100, description="MT type e.g. MT103")
    target: str = Field(..., max_length=100, description="ISO 20022 target e.g. pacs.008.001.08")


class MappingCreate(MappingBase):
    message_description_id: int
    status: Optional[MappingStatus] = MappingStatus.DRAFT


class MappingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    source: Optional[str] = Field(None, max_length=100)
    target: Optional[str] = Field(None, max_length=100)
    status: Optional[MappingStatus] = None


class MappingResponse(MappingBase):
    id: int
    message_description_id: int
    status: MappingStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    mapping_elements: List[MappingElementResponse] = []

    class Config:
        from_attributes = True


class MappingListResponse(MappingBase):
    id: int
    message_description_id: int
    status: MappingStatus
    created_at: datetime
    element_count: Optional[int] = 0

    class Config:
        from_attributes = True