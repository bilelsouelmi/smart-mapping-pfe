from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional


class MappingFormulaBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_path: str = Field(..., max_length=500, description="Hierarchical path (e.g., Body.Client.Identity.FirstName)")
    target_path: str = Field(..., max_length=500, description="Hierarchical path (e.g., CustomerData.Person.FirstName)")
    transformation_type: str = Field(
        ..., 
        pattern="^(direct|date_format|name_split|phone_format|concatenate|substring|case_conversion|custom)$"
    )
    transformation_rule: str
    
    @validator('source_path', 'target_path')
    def validate_path_levels(cls, v):
        """
        Valider que le chemin ne dépasse pas 7 niveaux
        Supportes les chemins ISO 20022 profonds comme:
        Stmt.Ntry.NtryDtls.TxDtls.RmtInf.Ustrd (5 séparateurs)
        """
        separator_count = v.count('.')
        if separator_count > 7:
            raise ValueError(f'Path cannot have more than 7 separators (8 levels max). Got {separator_count} separators: {v}')
        return v


class MappingFormulaCreate(MappingFormulaBase):
    message_description_id: int
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    source_level: Optional[int] = Field(None, ge=1, le=8)
    target_level: Optional[int] = Field(None, ge=1, le=8)


class MappingFormulaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    source_path: Optional[str] = Field(None, max_length=500)
    target_path: Optional[str] = Field(None, max_length=500)
    transformation_type: Optional[str] = Field(
        None,
        pattern="^(direct|date_format|name_split|phone_format|concatenate|substring|case_conversion|custom)$"
    )
    transformation_rule: Optional[str] = None
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    success_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_level: Optional[int] = Field(None, ge=1, le=8)
    target_level: Optional[int] = Field(None, ge=1, le=8)
    
    @validator('source_path', 'target_path')
    def validate_path_levels(cls, v):
        if v is None:
            return v
        separator_count = v.count('.')
        if separator_count > 7:
            raise ValueError(f'Path cannot have more than 7 separators (8 levels max). Got {separator_count}: {v}')
        return v


class MappingFormulaResponse(MappingFormulaBase):
    id: int
    message_description_id: int
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    success_rate: float
    usage_count: int
    source_level: Optional[int] = None
    target_level: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True