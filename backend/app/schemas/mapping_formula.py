from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class MappingFormulaBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_column: str
    target_column: str
    transformation_type: str = Field(
        ..., 
        pattern="^(direct|date_format|name_split|phone_format|concatenate|substring|case_conversion|custom)$"
    )
    transformation_rule: str


class MappingFormulaCreate(MappingFormulaBase):
    message_description_id: int
    example_input: Optional[str] = None
    example_output: Optional[str] = None


class MappingFormulaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    source_column: Optional[str] = None
    target_column: Optional[str] = None
    transformation_type: Optional[str] = Field(
        None,
        pattern="^(direct|date_format|name_split|phone_format|concatenate|substring|case_conversion|custom)$"
    )
    transformation_rule: Optional[str] = None
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    success_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class MappingFormulaResponse(MappingFormulaBase):
    id: int
    message_description_id: int
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    success_rate: float
    usage_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True