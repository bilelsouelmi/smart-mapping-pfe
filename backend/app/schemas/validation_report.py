from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any


class DifferenceDetail(BaseModel):
    row: int
    column: str
    expected: Any
    actual: Any


class ValidationReportBase(BaseModel):
    accuracy_percentage: float = Field(..., ge=0.0, le=100.0)
    row_count_match: bool
    column_count_match: bool
    total_cells: int = Field(..., ge=0)
    matching_cells: int = Field(..., ge=0)
    differing_cells: int = Field(..., ge=0)


class ValidationReportCreate(ValidationReportBase):
    transformation_job_id: int
    differences: Optional[List[DifferenceDetail]] = None
    overall_quality: Optional[str] = Field(None, pattern="^(Excellent|Good|Fair|Poor)$")
    recommendation: Optional[str] = None


class ValidationReportResponse(ValidationReportBase):
    id: int
    transformation_job_id: int
    differences: Optional[List[Dict[str, Any]]] = None
    overall_quality: Optional[str] = None
    recommendation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True