from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ReferenceMappingFormula(Base):
    """
    Canonical formula/expression storage for the XML reference mapping
    library (dataset/mappings/*.xml) — deliberately separate from
    MappingDocumentation (business_rationale/migration_note/... — see
    that model's docstring) and from MappingFormula (an unrelated table:
    real formulas a user has accepted for their own uploaded
    MessageDescription, not the reference library). Documentation and
    executable transformation logic have different responsibilities and
    different lifecycles, so they get different tables even though both
    are keyed the same way.

    One row per <Mapping> element, same (mapping_id, element_id) compound
    key as MappingDocumentation — mapping_id is the file-level id (e.g.
    "MAP_CAMT053_MT940_REVERSE_001"), element_id is that specific
    <Mapping id="MAPPING_04">'s own id.
    """
    __tablename__ = "reference_mapping_formulas"
    __table_args__ = (
        UniqueConstraint('mapping_id', 'element_id', name='uq_reference_mapping_formulas_mapping_element'),
    )

    id = Column(Integer, primary_key=True, index=True)

    mapping_id = Column(String, nullable=False, index=True)
    element_id = Column(String, nullable=False)

    formula_type = Column(String, nullable=True)
    formula_expression = Column(Text, nullable=True)
    formula_pseudocode = Column(Text, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
