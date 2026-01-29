from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class StandardElementBase(BaseModel):
    element_id: str = Field(..., max_length=50)
    element_name: str = Field(..., max_length=200)
    category: str = Field(..., max_length=100)
    business_domain: str = Field(default="Banking", max_length=100)
    source_path: Optional[str] = Field(None, max_length=500)
    target_path: Optional[str] = Field(None, max_length=500)
    iso20022_path: Optional[str] = Field(None, max_length=500)
    data_type: str = Field(..., max_length=50)
    format_pattern: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    example_value: Optional[str] = Field(None, max_length=500)
    is_required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    validation_regex: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    related_elements: Optional[List[Dict[str, Any]]] = None


class StandardElementCreate(StandardElementBase):
    pass


class StandardElementUpdate(BaseModel):
    element_name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    source_path: Optional[str] = Field(None, max_length=500)
    target_path: Optional[str] = Field(None, max_length=500)
    iso20022_path: Optional[str] = Field(None, max_length=500)
    data_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    example_value: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class StandardElementResponse(StandardElementBase):
    id: int
    usage_count: int
    success_rate: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True