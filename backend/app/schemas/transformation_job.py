from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TransformationJobBase(BaseModel):
    job_name: str = Field(..., min_length=1, max_length=200)


class TransformationJobCreate(TransformationJobBase):
    user_id: int
    file_upload_id: int


class TransformationJobUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|running|completed|failed)$")
    progress: Optional[float] = Field(None, ge=0.0, le=100.0)
    error_message: Optional[str] = None


class TransformationJobResponse(TransformationJobBase):
    id: int
    user_id: int
    file_upload_id: int
    status: str
    progress: float
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True