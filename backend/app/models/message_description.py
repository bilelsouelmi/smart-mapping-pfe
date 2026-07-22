from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MessageDescription(Base):
    __tablename__ = "message_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id"), nullable=True)

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    source_system = Column(String, nullable=True)
    target_system = Column(String, nullable=True)
    business_domain = Column(String, nullable=True)

    column_structure = Column(JSON, nullable=True)
    sample_data = Column(JSON, nullable=True)

    mt_type = Column(String, nullable=True)
    iso_target = Column(String, nullable=True)
    mt_blocks = Column(JSON, nullable=True)

    status = Column(String, default='draft')
    mapping_completion = Column(Integer, default=0)
    quality_score = Column(Integer, nullable=True)

    # Separate from `status` above, which auto-tracks mapping-formula
    # completion percentage (draft/in_progress/validated — see
    # ai_learning.py's update_mapping_completion, which overwrites it on
    # every formula change). `approved` is a distinct, purely user-driven
    # gate on the generated structure itself: None = pending review,
    # True = approved, False = explicitly rejected.
    approved = Column(Boolean, nullable=True, default=None)

    # Maker-checker: who actually clicked Approve — always a different
    # user than user_id (the proposer), enforced in the update route.
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    user = relationship("User", back_populates="message_descriptions", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
    mapping_formulas = relationship("MappingFormula", back_populates="message_description", cascade="all, delete-orphan")
    file_upload = relationship("FileUpload", back_populates="message_descriptions")
    elements = relationship("MessageDescriptionElement", cascade="all, delete-orphan")
    mappings = relationship("Mapping", back_populates="message_description", cascade="all, delete-orphan")

    @property
    def proposed_by_username(self):
        return self.user.username if self.user else None

    @property
    def approved_by_username(self):
        return self.approver.username if self.approver else None