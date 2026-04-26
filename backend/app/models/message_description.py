from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MessageDescription(Base):
    __tablename__ = "message_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # ── Lien vers le fichier uploadé ──────────────────────────────────────────
    file_upload_id = Column(Integer, ForeignKey("file_uploads.id"), nullable=True)

    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # CSV, XML, JSON, Excel, XML_MT
    source_system = Column(String, nullable=True)
    target_system = Column(String, nullable=True)
    business_domain = Column(String, nullable=True)  # Banking, Insurance, etc.

    # JSON fields
    column_structure = Column(JSON, nullable=True)  # [{name, type, format}, ...]
    sample_data = Column(JSON, nullable=True)  # Sample rows (10 first rows)

    # ── NOUVEAU : MT Message fields ───────────────────────────────────────────
    mt_type = Column(String, nullable=True)      # MT103, MT202, MT940...
    iso_target = Column(String, nullable=True)   # pacs.008.001.08, camt.053...
    mt_blocks = Column(JSON, nullable=True)      # { ":20": {...}, ":32A": {...sub_fields} }
    # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

    # ── NOUVEAU : Status & Quality ────────────────────────────────────────────
    status = Column(String, default='draft')          # draft, in_progress, validated, approved
    mapping_completion = Column(Integer, default=0)   # % colonnes mappées
    quality_score = Column(Integer, nullable=True)    # depuis ValidationReport
    # ── FIN NOUVEAU ───────────────────────────────────────────────────────────

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    user = relationship("User", back_populates="message_descriptions")
    mapping_formulas = relationship("MappingFormula", back_populates="message_description", cascade="all, delete-orphan")
    file_upload = relationship("FileUpload", back_populates="message_descriptions")