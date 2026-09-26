"""
Context Builder — the CAG (Context-Augmented Generation) half of the AI
knowledge layer, complementary to Qdrant's RAG retrieval
(qdrant_manager.py / exact_rag_lookup.py). Qdrant answers "what similar
mapping has been authored before"; this answers "what does THIS
platform's live configuration actually allow or require right now" —
active Business Variables, which Reference Data categories exist, and
which fields of this mt_type are validated against a live code list.

Deliberately selective, not exhaustive: dumping every Business Variable
row and all ~400 Reference Data entries into every prompt would bloat
token cost and dilute the one line the LLM actually needs to reason
about (see the FIELD_MAPPING chunk measurement — ~85% of a typical
Qdrant chunk's tokens are documentation prose, not the reusable
pattern). Each section below intentionally summarizes rather than
dumps full rows.
"""
from typing import Optional
from sqlalchemy.orm import Session


def _gather_context_data(db: Session, mt_type: Optional[str] = None) -> dict:
    """Shared data-gathering for build_mapping_context() (prose, for LLM
    prompt injection) and build_mapping_context_structured() (lists, for
    UI display) — same underlying queries, two different presentations."""
    from app.models.business_variable import BusinessVariable
    variables = db.query(BusinessVariable).all()
    business_variables = [f"{v.name} = {v.value}" for v in variables]

    from app.models.reference_data import ReferenceData
    reference_categories = sorted(r[0] for r in db.query(ReferenceData.category).distinct().all())

    reference_validated_fields = []
    if mt_type:
        from app.models.validation_rule import ValidationRule
        tagged = (
            db.query(ValidationRule.field_name, ValidationRule.reference_category)
            .filter(ValidationRule.mt_type == mt_type, ValidationRule.reference_category.isnot(None))
            .distinct()
            .all()
        )
        reference_validated_fields = [f"{name} -> {category}" for name, category in tagged]

    return {
        "business_variables": business_variables,
        "reference_categories": reference_categories,
        "reference_validated_fields": reference_validated_fields,
    }


def build_mapping_context(db: Session, mt_type: Optional[str] = None) -> str:
    """
    Returns a compact "PLATFORM CONTEXT" text block for injection into
    an LLM mapping-suggestion prompt, or "" if there's nothing relevant
    to add (e.g. no Business Variables configured yet, no Reference
    Data imported yet — a fresh install shouldn't get an empty/noisy
    section).
    """
    data = _gather_context_data(db, mt_type)
    sections = []

    if data["business_variables"]:
        var_lines = "\n".join(f"- {v}" for v in data["business_variables"])
        sections.append(
            "BUSINESS VARIABLES (admin-editable constants — reference by "
            f"name in a formula instead of hardcoding the value):\n{var_lines}"
        )

    if data["reference_categories"]:
        sections.append(
            "REFERENCE DATA CATEGORIES (live, admin-editable code lists — use "
            'ReferenceLookup("CATEGORY", code) in a formula to validate or '
            f"resolve a code against one of these instead of a hardcoded enum): {', '.join(data['reference_categories'])}"
        )

    if mt_type and data["reference_validated_fields"]:
        lines = "\n".join(f"- {f}" for f in data["reference_validated_fields"])
        sections.append(
            f"FIELDS OF {mt_type} ALREADY VALIDATED AGAINST LIVE REFERENCE DATA:\n{lines}"
        )

    if not sections:
        return ""
    return "\n\n".join(sections)


def build_mapping_context_structured(db: Session, mt_type: Optional[str] = None) -> dict:
    """
    Structured counterpart to build_mapping_context() — same underlying
    data (business variables, reference categories, reference-validated
    fields), returned as lists instead of formatted prose. For display
    (e.g. the AI Mapping Assistant's "Business Context" panel) rather
    than LLM prompt injection.
    """
    return _gather_context_data(db, mt_type)
