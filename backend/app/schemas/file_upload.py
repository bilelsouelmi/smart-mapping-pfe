from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class FileUploadBase(BaseModel):
    original_filename: str
    file_type: str = Field(..., pattern="^(CSV|XML|JSON|Excel)$")


class FileUploadCreate(FileUploadBase):
    file_path: str
    file_size: int = Field(..., gt=0)
    user_id: int


class FileUploadResponse(FileUploadBase):
    id: int
    user_id: int
    file_path: str
    file_size: int
    status: str
    upload_date: datetime

    class Config:
        from_attributes = True