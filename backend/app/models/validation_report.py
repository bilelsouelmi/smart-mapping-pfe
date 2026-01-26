from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id = Column(Integer, primary_key=True, index=True)
    transformation_job_id = Column(Integer, ForeignKey("transformation_jobs.id"), nullable=False)
    
    accuracy_percentage = Column(Float, nullable=False)  # 0.0 to 100.0
    row_count_match = Column(Boolean, default=False)
    column_count_match = Column(Boolean, default=False)
    
    total_cells = Column(Integer, nullable=False)
    matching_cells = Column(Integer, nullable=False)
    differing_cells = Column(Integer, nullable=False)
    
    # Detailed differences (JSON array of {row, column, expected, actual})
    differences = Column(JSON, nullable=True)
    
    overall_quality = Column(String, nullable=True)  # Excellent, Good, Fair, Poor
    recommendation = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    transformation_job = relationship("TransformationJob", back_populates="validation_reports")