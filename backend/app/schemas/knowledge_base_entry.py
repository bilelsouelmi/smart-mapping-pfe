from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class KnowledgeBaseEntryBase(BaseModel):
    entry_type: str = Field(..., pattern="^(mapping|transformation|validation)$")
    content: Dict[str, Any]


class KnowledgeBaseEntryCreate(KnowledgeBaseEntryBase):
    meta_data: Optional[Dict[str, Any]] = None
    embedding_id: Optional[str] = None


class KnowledgeBaseEntryResponse(KnowledgeBaseEntryBase):
    id: int
    meta_data: Optional[Dict[str, Any]] = None
    embedding_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True