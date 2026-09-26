"""
Phase 1 of the Qdrant/RAG redesign: loads the documentation fields
(business_rationale, migration_note, etc.) that xml_mapping_parser.py
already extracts from every dataset/mappings/*.xml file into
MappingDocumentation rows — making PostgreSQL the actual source of
truth for this content instead of the XML files themselves.

Also populates ReferenceMappingFormula (formula_type/expression/
pseudocode) in the same pass — same source data (xml_parser already
extracts both from the same <Mapping> element), same (mapping_id,
element_id) key, so there's no reason to re-parse the XML files a
second time just to keep the two tables' population logic apart. The
tables themselves stay separate per the documentation-vs-executable-
logic distinction (see each model's docstring); only the import pass
that populates them is shared.

Qdrant is untouched by this step; xml_chunker.py keeps reading straight
from the XML files exactly as before until it's redesigned in a later
phase.
"""
import logging
from sqlalchemy.orm import Session

from app.models.mapping_documentation import MappingDocumentation
from app.models.reference_mapping_formula import ReferenceMappingFormula
from app.services.xml_mapping_parser import xml_parser

logger = logging.getLogger(__name__)


def _upsert_documentation(db: Session, mapping_id: str, mapping_name: str, element: dict) -> str:
    element_id = element.get('id')
    if not element_id:
        return "skipped"

    existing = db.query(MappingDocumentation).filter(
        MappingDocumentation.mapping_id == mapping_id,
        MappingDocumentation.element_id == element_id,
    ).first()

    fields = dict(
        mapping_name=mapping_name,
        source_field=element.get('source_field'),
        target_field=element.get('target_field'),
        criticality=element.get('criticality'),
        impact_if_fails=element.get('impact_if_fails'),
        business_rationale=element.get('business_rationale'),
        performance_impact=element.get('performance_impact'),
        audit_requirement=element.get('audit_requirement'),
        compliance_requirement=element.get('compliance_requirement'),
        data_privacy=element.get('data_privacy'),
        migration_note=element.get('migration_note'),
        caching_strategy=element.get('caching_strategy'),
    )

    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        return "updated"

    db.add(MappingDocumentation(mapping_id=mapping_id, element_id=element_id, **fields))
    return "inserted"


def _upsert_formula(db: Session, mapping_id: str, element: dict) -> str:
    element_id = element.get('id')
    if not element_id:
        return "skipped"

    existing = db.query(ReferenceMappingFormula).filter(
        ReferenceMappingFormula.mapping_id == mapping_id,
        ReferenceMappingFormula.element_id == element_id,
    ).first()

    fields = dict(
        formula_type=element.get('formula_type'),
        formula_expression=element.get('formula_expression'),
        formula_pseudocode=element.get('formula_pseudocode'),
    )

    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        return "updated"

    db.add(ReferenceMappingFormula(mapping_id=mapping_id, element_id=element_id, **fields))
    return "inserted"


def import_mapping_documentation(db: Session) -> dict:
    """Re-parses every dataset/mappings/*.xml file (bypassing
    xml_parser's in-memory cache, in case a file changed since the
    process started) and upserts one MappingDocumentation row + one
    ReferenceMappingFormula row per <Mapping> element, both keyed by
    (mapping_id, element_id) — safe to re-run whenever the XML files
    change. Caller is responsible for committing, matching the pattern
    established by reference_data_import.py's import_reference_data_csvs."""
    xml_parser.mappings_cache = {}
    all_mappings = xml_parser.load_all_mappings()

    result = {
        "inserted": 0, "updated": 0, "skipped": 0, "files": 0,
        "formulas_inserted": 0, "formulas_updated": 0, "formulas_skipped": 0,
    }

    for mapping_data in all_mappings.values():
        mapping_id = mapping_data.get('mapping_id')
        mapping_name = mapping_data.get('mapping_name')
        field_mappings = mapping_data.get('field_mappings') or []
        if not mapping_id or not field_mappings:
            continue
        result["files"] += 1
        for element in field_mappings:
            outcome = _upsert_documentation(db, mapping_id, mapping_name, element)
            result[outcome] += 1

            formula_outcome = _upsert_formula(db, mapping_id, element)
            result[f"formulas_{formula_outcome}"] += 1

    return result
