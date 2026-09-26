"""
Extracts structured, retrieval-useful metadata (recognized function
calls, Reference Data categories, Business Variable references) from a
mapping formula's free-text expression — used by xml_chunker.py to
populate the lean FIELD_MAPPING payload's functions/reference_data/
global_variables lists (Phase 2 of the Qdrant redesign) instead of just
embedding the raw expression string.

Deliberately validates against real, live vocabularies rather than
guessing from regex shape alone:
  - functions: intersected with _XML_DIALECT_FUNCTIONS' keys (the same
    dict transform_mapping.py's formula evaluator actually dispatches
    on at runtime), so Qdrant's notion of "a known function" can never
    drift from what the engine actually supports.
  - global_variables: intersected with the real merged Business
    Variable names from _get_global_variables() (XML defaults + Postgres
    overrides), not a naive ALL_CAPS regex — an expression can contain
    other all-caps tokens (XML, OPBD, CRDT/DBIT literals) that are not
    variable references, so shape alone isn't a safe enough filter.
"""
import re
from typing import List, Tuple

_CALL_RE = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
_REF_LOOKUP_RE = re.compile(r'ReferenceLookup\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']')
_TOKEN_RE = re.compile(r'\b[A-Z][A-Z0-9_]{2,}\b')


def extract_functions(expression: str) -> List[str]:
    if not expression:
        return []
    from app.api.routes.transform_mapping import _XML_DIALECT_FUNCTIONS
    called = {m.group(1) for m in _CALL_RE.finditer(expression)}
    return sorted(called & set(_XML_DIALECT_FUNCTIONS.keys()))


def extract_reference_data(expression: str) -> List[str]:
    if not expression:
        return []
    return sorted({m.group(1) for m in _REF_LOOKUP_RE.finditer(expression)})


def extract_global_variables(expression: str) -> List[str]:
    if not expression:
        return []
    from app.api.routes.transform_mapping import _get_global_variables
    known = set(_get_global_variables().keys())
    candidates = {m.group(0) for m in _TOKEN_RE.finditer(expression)}
    return sorted(candidates & known)


def extract_all(expression: str) -> Tuple[List[str], List[str], List[str]]:
    """Returns (functions, reference_data, global_variables)."""
    return (
        extract_functions(expression),
        extract_reference_data(expression),
        extract_global_variables(expression),
    )


def extract_unrecognized_functions(expression: str) -> List[str]:
    """Function-call-shaped tokens that are NOT in the real vocabulary —
    the concrete hallucination signal (e.g. a generated/hand-typed
    "formatAmount(...)" when the real function is toSwiftAmount)."""
    if not expression:
        return []
    all_calls = {m.group(1) for m in _CALL_RE.finditer(expression)}
    return sorted(all_calls - set(extract_functions(expression)))


def analyze_expression(db, mt_type: str, source_field: str, expression: str) -> dict:
    """
    Deterministic (no LLM) review of a formula expression — the
    "Validation Assistant" piece of the AI Mapping Assistant: syntax
    sanity, real-vs-hallucinated function names, and whether a Reference
    Data category this source field is already known to require (via
    ValidationRule.reference_category — set from a Message Description
    element's own tag, see element_routes.py / import_rules_from_md)
    actually gets used in the expression. Field name AND field tag are
    both checked since a MappingElement's source_field is sometimes the
    raw SWIFT tag (":32A:") and sometimes a decomposed sub-field name
    (e.g. "Currency").
    """
    recognized = extract_functions(expression)
    unrecognized = extract_unrecognized_functions(expression)
    used_categories = set(extract_reference_data(expression))

    reference_checks = []
    if mt_type and source_field:
        from app.models.validation_rule import ValidationRule
        rules = db.query(ValidationRule).filter(
            ValidationRule.mt_type == mt_type,
            ValidationRule.reference_category.isnot(None),
            (ValidationRule.field_name == source_field) | (ValidationRule.field_tag == source_field)
        ).all()
        seen_categories = set()
        for rule in rules:
            if rule.reference_category in seen_categories:
                continue
            seen_categories.add(rule.reference_category)
            reference_checks.append({
                "category": rule.reference_category,
                "expected": True,
                "used": rule.reference_category in used_categories,
            })

    return {
        "syntax_valid": bool(expression and "=" in expression),
        "recognized_functions": recognized,
        "unrecognized_functions": unrecognized,
        "reference_checks": reference_checks,
    }
