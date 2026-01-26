from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base


class FileUploadStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # CSV, XML, JSON, Excel
    file_size = Column(BigInteger, nullable=False)  # in bytes
    
    status = Column(Enum(FileUploadStatus), default=FileUploadStatus.PENDING)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    user = relationship("User", back_populates="file_uploads")
    transformation_jobs = relationship("TransformationJob", back_populates="file_upload", cascade="all, delete-orphan")