from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TransformationJob(Base):
    __tablename__ = "transformation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id"), nullable=False)
    
    job_name = Column(String, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    user = relationship("User", back_populates="transformation_jobs")
    file_upload = relationship("FileUpload", back_populates="transformation_jobs")
    validation_reports = relationship("ValidationReport", back_populates="transformation_job", cascade="all, delete-orphan")