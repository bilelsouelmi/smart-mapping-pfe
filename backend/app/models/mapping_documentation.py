from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class MappingDocumentation(Base):
    """
    Phase 1 of the Qdrant/RAG redesign: the documentation fields that
    currently live ONLY inside the XML mapping files on disk and get
    baked directly into Qdrant's embedded text at chunk time (see
    xml_chunker.py's _chunk_field_mappings — business_rationale,
    migration_note, etc. account for ~85% of a typical FIELD_MAPPING
    chunk's tokens, most of it irrelevant to the reusable transformation
    pattern itself). This table makes PostgreSQL the actual source of
    truth for that content instead of the XML files, so it can later be
    retrieved by mapping_id/element_id after a lean Qdrant point points
    back here — Qdrant itself is untouched by this migration; it still
    reads straight from the XML files exactly as before until the
    chunker is redesigned in a later phase.

    One row per <Mapping> element inside a mapping XML file: `mapping_id`
    is the file-level id (e.g. "MAP_CAMT053_MT940_REVERSE_001"),
    `element_id` is that specific <Mapping id="MAPPING_04"> block's own
    id — together they're the same (mapping_id, element_id) pair
    xml_chunker.py already uses to build a FIELD_MAPPING chunk_id.
    """
    __tablename__ = "mapping_documentation"
    __table_args__ = (
        UniqueConstraint('mapping_id', 'element_id', name='uq_mapping_documentation_mapping_element'),
    )

    id = Column(Integer, primary_key=True, index=True)

    mapping_id = Column(String, nullable=False, index=True)
    mapping_name = Column(String, nullable=True)
    element_id = Column(String, nullable=False)

    source_field = Column(String, nullable=True)
    target_field = Column(String, nullable=True)

    criticality = Column(String, nullable=True)
    impact_if_fails = Column(Text, nullable=True)
    business_rationale = Column(Text, nullable=True)
    performance_impact = Column(Text, nullable=True)
    audit_requirement = Column(Text, nullable=True)
    compliance_requirement = Column(Text, nullable=True)
    data_privacy = Column(Text, nullable=True)
    migration_note = Column(Text, nullable=True)
    caching_strategy = Column(Text, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
