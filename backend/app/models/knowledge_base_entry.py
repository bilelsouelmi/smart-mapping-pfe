from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"

    id = Column(Integer, primary_key=True, index=True)
    
    entry_type = Column(String, nullable=False)  # mapping, transformation, validation
    
    # Store the actual content (mapping details, transformation logic, etc.)
    content = Column(JSON, nullable=False)
    
    # Metadata for search and filtering
    meta_data = Column(JSON, nullable=True)  # domain, source_system, target_system, etc.
    
    # Reference to ChromaDB embedding ID
    embedding_id = Column(String, nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())