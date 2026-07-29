"""
New Transform endpoint using Mapping + MappingElement
POST /api/transform/mapping/{mapping_id}
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
import logging
import re
import json
from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as ET

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.mapping import Mapping, MappingElement, MappingStatus
from app.models.message_description import MessageDescription
from app.services.swift_txt_parser import SWIFTTextParser as SwiftTxtParser

logger = logging.getLogger(__name__)

router = APIRouter()

# ISO 20022 namespaces
ISO_NAMESPACES = {
    "pacs.008.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    "pacs.009.001.08": "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "camt.053.001.08": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
    "camt.054.001.08": "urn:iso:std:iso:20022:tech:xsd:camt.054.001.08",
}

ISO_ROOT_ELEMENTS = {
    "pacs.008.001.08": "FIToFICstmrCdtTrf",
    "pacs.009.001.08": "FICdtTrf",
    "camt.053.001.08": "BkToCstmrStmt",
    "camt.054.001.08": "BkToCstmrDbtCdtNtfctn",
}


def extract_source_fields(mt_blocks: dict) -> dict:
    """Extract flat field map from mt_blocks: {':20': 'value', ':32A': 'value', ...}"""
    fields = {}
    if not mt_blocks:
        return fields
    block4 = mt_blocks.get('block4', {})
    sub_fields = block4.get('sub_fields', {})
    for tag, field_data in sub_fields.items():
        clean_tag = tag.lstrip(':').rstrip(':')
        value = field_data.get('value', '') if isinstance(field_data, dict) else str(field_data)
        # Store with all tag variants
        fields[clean_tag] = value                          # 50K
        fields[clean_tag.upper()] = value                  # 50K
        fields[clean_tag.lower()] = value                  # 50k
        fields[f':{clean_tag}:'] = value                   # :50K:
        fields[f':{clean_tag.upper()}:'] = value           # :50K:
        fields[f':{clean_tag.lower()}:'] = value           # :50k:
        fields[f'field_{clean_tag.lower()}'] = value       # field_50k
        fields[f'field_{clean_tag.upper()}'] = value       # field_50K

    # Envelope data needed by the XML-pseudocode dialect's "MT.Block1.SenderBIC"
    # fallback (used e.g. when :52A: Ordering Institution is absent) — the
    # sender's BIC is embedded in block1's LogicalTerminalAddress (first 8
    # chars), which extract_source_fields otherwise never surfaces since it
    # only reads block4.
    block1_sub = mt_blocks.get('block1', {}).get('sub_fields', {})
    lt_addr = block1_sub.get('LogicalTerminalAddress', {})
    fields['__block1_lt_address__'] = lt_addr.get('value', '') if isinstance(lt_addr, dict) else str(lt_addr or '')

    return fields


def extract_xml_source_fields(xml_path: str) -> dict:
    """Flat {dotted.path: leaf_text} map from an ISO 20022 XML file — the
    XML-direction counterpart to extract_source_fields() above. Generic
    tree walk (no per-message-family hardcoding, unlike iso20022_parser.py):
    every leaf element becomes one dotted path relative to the root
    (namespace stripped, and the Document/<MessageRoot> wrapper skipped
    since it's identical across every file of a given type and would only
    add noise to every path). Attribute values are exposed as
    "path.@AttrName" so e.g. Amt's Ccy="EUR" is reachable as
    "CdtTrfTxInf.Amt.@Ccy" the same way MT.F32A.currency works for the
    other direction.

    Repeated sibling elements (same local tag under the same parent — e.g.
    camt.053's multiple <Bal> entries, one per balance type, or multiple
    <Ntry> statement lines) collide on a plain dotted path: only the FIRST
    occurrence is kept there (unchanged, so every existing formula written
    against the unindexed path keeps working). Every occurrence is ALSO
    exposed under a disambiguated path so formulas can reach the others:
      - If the element has a Tp/CdOrPrtry/Cd-shaped child (the standard
        ISO 20022 "type code" idiom — camt.053 balances use exactly this
        to distinguish OPBD/CLBD/CLAV/FWAV), that code becomes the suffix:
        "Stmt.Bal_OPBD.Amt", "Stmt.Bal_CLBD.Amt", etc. This reuses the same
        Bal_OPBD/Bal_CLBD naming convention build_xml_from_dict already
        uses on the MT->XML direction, so it needs no new pseudocode
        syntax — XML.Stmt.Bal_OPBD.Amt is a plain dotted path.
      - Otherwise a 1-based numeric suffix is used: "Stmt.Ntry_1.Amt",
        "Stmt.Ntry_2.Amt", ...
    """
    import xml.etree.ElementTree as _ET

    fields: dict = {}
    try:
        tree = _ET.parse(xml_path)
    except Exception:
        return fields
    root = tree.getroot()

    def _local(tag):
        return tag.split('}')[-1] if '}' in tag else tag

    def _find_code(el):
        """Walk a Tp/CdOrPrtry/Cd child chain (if present) and return its
        text — the ISO 20022 idiom used to type-distinguish otherwise-
        identical repeated siblings (e.g. camt.053's <Bal> entries)."""
        cur = el
        for step in ('Tp', 'CdOrPrtry', 'Cd'):
            found = next((c for c in cur if _local(c.tag) == step), None)
            if found is None:
                return None
            cur = found
        text = (cur.text or '').strip()
        return text or None

    def _walk_at(el, path):
        for attr_name, attr_val in el.attrib.items():
            fields[f"{path}.@{_local(attr_name)}"] = attr_val
        children = list(el)
        if children:
            by_tag: dict = {}
            for child in children:
                by_tag.setdefault(_local(child.tag), []).append(child)
            for tag, group in by_tag.items():
                child_path = f"{path}.{tag}" if path else tag
                # Unindexed path — first occurrence only, unchanged from
                # before this function supported disambiguation at all.
                _walk_at(group[0], child_path)
                if len(group) > 1:
                    for idx, child in enumerate(group):
                        suffix = _find_code(child) or str(idx + 1)
                        indexed_path = f"{path}.{tag}_{suffix}" if path else f"{tag}_{suffix}"
                        _walk_at(child, indexed_path)
        else:
            text = (el.text or '').strip()
            if text:
                # Don't overwrite an already-seen path — see docstring.
                fields.setdefault(path, text)

    def _walk(el, prefix):
        local = _local(el.tag)
        path = f"{prefix}.{local}" if prefix else local
        _walk_at(el, path)

    # Skip the Document + message-root wrapper (e.g.
    # "Document.FIToFICstmrCdtTrf") — every field's real path already starts
    # from GrpHdr/CdtTrfTxInf/etc, and keeping the wrapper would just mean
    # every dataset formula has to repeat it for no benefit.
    root_children = list(root)
    if _local(root.tag) == 'Document' and len(root_children) == 1:
        for child in list(root_children[0]):
            _walk(child, '')
    else:
        for child in root_children:
            _walk(child, '')

    return fields


def get_field_value(ref: str, source_fields: dict) -> str:
    """Get actual field value from source fields by tag reference."""
    ref_upper = ref.upper()
    ref_lower = ref.lower()
    val = (
        source_fields.get(f':{ref_upper}:') or
        source_fields.get(f':{ref_upper}') or
        source_fields.get(ref_upper) or
        source_fields.get(f':{ref_lower}:') or
        source_fields.get(f':{ref_lower}') or
        source_fields.get(ref_lower) or
        source_fields.get(ref) or
        source_fields.get(f':{ref}:') or
        source_fields.get(f':{ref}') or
        ''
    )
    return val.strip() if val else ''

def get_field_value_raw(ref: str, source_fields: dict) -> str:
    """Get raw (unstripped) field value — preserves newlines for multiline fields."""
    ref_upper = ref.upper()
    ref_lower = ref.lower()
    val = (
        source_fields.get(f':{ref_upper}:') or
        source_fields.get(f':{ref_upper}') or
        source_fields.get(ref_upper) or
        source_fields.get(f':{ref_lower}:') or
        source_fields.get(f':{ref_lower}') or
        source_fields.get(ref_lower) or
        source_fields.get(ref) or
        ''
    )
    return val or ''


def extract_iban_from_field(value: str) -> str:
    """Extract IBAN or account number from SWIFT field value (first line after /)."""
    if not value:
        return ''
    lines = value.strip().split("\n")
    first = lines[0].strip()
    if first.startswith('/'):
        return first[1:].strip()
    return first


def extract_amount_from_32a(value: str) -> str:
    """Extract amount from :32A: field (format: YYMMDDCCCAMOUNT)."""
    if not value or len(value) < 10:
        return value
    amount_str = value[9:]  # Skip YYMMDDCCC (6+3 chars)
    return amount_str.replace(',', '.').strip()


def extract_currency_from_32a(value: str) -> str:
    """Extract currency from :32A: field."""
    if not value or len(value) < 9:
        return 'EUR'
    return value[6:9]


# ── Control-flow helpers for if/else if/else/endif blocks ──────────────────
#
# WHY THESE EXIST: the original evaluator processed every line sequentially
# with no real branching — an unrecognized "if (...) then" condition fell
# through silently, and BOTH the "then" and "else" branch bodies still got
# executed unconditionally (whichever assignment came last in the text just
# overwrote the earlier one). This produced wrong results for any formula
# using if/then/else with assignments in both branches (e.g. SWIFT :50K:
# name-extraction, which checks whether the first line starts with "/" to
# decide whether to skip the account line before reading the name).
#
# These helpers add real branch evaluation: find the matching endif/else for
# an if-chain, evaluate the condition, and only execute the matching
# branch's lines — skipping the rest of the chain entirely.
#
# IMPORTANT SCOPE NOTE: the pre-existing "if/else if (var == \"value\") then"
# nested-lookahead mechanism (used by formulas like :23B:'s purpose-code
# derivation, which has compound "contains(...) OR contains(...)" conditions
# this new generic evaluator does not parse) is left completely untouched.
# The new generic chain handler below only activates for condition shapes
# that mechanism does NOT already handle (starts_with, bare contains/
# is_valid_bic as the outer condition, source.field == null) — see the
# old_style_match check in the main scan loop.

def _find_block_end(lines, start_idx):
    """
    Find the index of the 'endif' that closes the if-block starting at
    start_idx. A fresh 'if (...) then' increases nesting depth; 'else'/
    'else if (...) then' do NOT (they're part of the same chain).
    """
    depth = 1
    j = start_idx + 1
    while j < len(lines):
        line = lines[j]
        if re.match(r'^if\s*\(.+\)\s*then\s*$', line):
            depth += 1
        elif line == 'endif':
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return len(lines) - 1


def _find_next_branch(lines, start_idx, block_end_idx):
    """
    Starting at start_idx, scan forward (not descending into nested
    sub-blocks) for the next 'else if (...) then' or bare 'else' belonging
    to the SAME if-chain. Returns block_end_idx if none found (i.e. we've
    reached the matching endif with no further branches).
    """
    depth = 0
    j = start_idx
    while j < block_end_idx:
        line = lines[j]
        if re.match(r'^if\s*\(.+\)\s*then\s*$', line):
            depth += 1
        elif line == 'endif':
            depth -= 1
        elif depth == 0 and (re.match(r'^else\s+if\s*\(.+\)\s*then\s*$', line) or line == 'else'):
            return j
        j += 1
    return block_end_idx


def _resolve_condition_token(token, variables, source_fields):
    """Resolve a token used inside a condition: a variable, var[N] array
    access, a source.field_XX reference, or a quoted string literal."""
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    m = re.match(r'^(\w+)\[(\d+)\]$', token)
    if m:
        list_var, idx = m.group(1), int(m.group(2))
        lst = variables.get(list_var, [])
        if isinstance(lst, list) and len(lst) > idx:
            return lst[idx]
        return ''
    if token.startswith('source.field_'):
        return get_field_value(token.replace('source.field_', ''), source_fields)
    if token in variables:
        return variables[token]
    return token


def _eval_condition(cond_text, variables, source_fields):
    """
    Evaluate a single boolean condition from an 'if (COND) then' /
    'else if (COND) then' line. Supports the condition shapes actually
    produced by our reference formulas:
      starts_with(var_or_index, "prefix")
      contains(var, "keyword")
      is_valid_bic(var)
      source.field_XX == null
      var == "literal"
    Anything unrecognized evaluates to False — the safe default, since most
    unsupported conditions in practice are validation/error-throwing guard
    clauses (e.g. "if (NOT matches(...)) then throw error ... endif") where
    skipping the branch (not throwing) is exactly the desired behavior for
    a best-effort transform.
    """
    cond_text = cond_text.strip()

    m = re.match(r'starts_with\(\s*([^,]+?)\s*,\s*"([^"]*)"\s*\)', cond_text)
    if m:
        val = _resolve_condition_token(m.group(1), variables, source_fields)
        return isinstance(val, str) and val.startswith(m.group(2))

    m = re.match(r'contains\(\s*(\w+)\s*,\s*"([^"]*)"\s*\)', cond_text)
    if m:
        val = _resolve_condition_token(m.group(1), variables, source_fields)
        return isinstance(val, str) and m.group(2).lower() in val.lower()

    m = re.match(r'is_valid_bic\(\s*(\w+)\s*\)', cond_text)
    if m:
        val = _resolve_condition_token(m.group(1), variables, source_fields)
        return isinstance(val, str) and len(val) in (8, 11)

    m = re.match(r'source\.field_(\w+)\s*==\s*null', cond_text)
    if m:
        return not get_field_value(m.group(1), source_fields)

    m = re.match(r'(\w+)\s*==\s*"([^"]*)"', cond_text)
    if m:
        val = _resolve_condition_token(m.group(1), variables, source_fields)
        return val == m.group(2)

    return False


class _ReturnSignal(Exception):
    """
    Internal control-flow signal used by evaluate_expression() so that a
    'return X' statement — whether at the top level or inside an if/else
    branch — unwinds cleanly to ONE shared place that decides the final
    result, exactly like the original (pre-branch-rewrite) evaluator's
    behavior: a 'return' sets a shared result_value and stops processing,
    but if that value turns out to be empty/falsy, the function STILL falls
    back to "use the first variable that got assigned" before giving up.

    WHY THIS MATTERS: several real reference formulas (:32A:'s amount
    parsing, :59:'s IBAN extraction) use helper functions this evaluator
    doesn't implement (parse_decimal, replace(), nested if/else inside a
    branch body) for some of their middle steps, so their named "return"
    variable ends up never actually assigned — the formula's `return X`
    resolves to empty. The ORIGINAL evaluator happened to recover a usable
    value anyway via this fallback (it grabbed the field's raw value, which
    a later post-processing step then cleaned up). An earlier version of
    this fix made 'return' immediately return from the Python function,
    which silently dropped that safety net and turned previously-correct
    (if accidental) results into empty ones. Using an exception to unwind
    instead of a hard Python return restores the original safety net while
    still keeping the real if/else branch-skipping this rewrite adds.
    """
    def __init__(self, value):
        self.value = value


def _evaluate_legacy_dialect(expression: str, source_fields: dict, target_xpath: str = "") -> str:
    """
    Expression evaluator for the "var = source.field_XX" pseudocode dialect —
    the one used by manually-authored MappingElement.expression values typed
    through the Mapping page's Edit form (see its placeholder text). Handles
    common patterns: trim, return { Key: val }, direct field access,
    and real if/else if/else/endif branching (see control-flow helpers above).
    """
    if not expression:
        return ''

    lines = [l.strip() for l in expression.split("\n") if l.strip()]

    variables = {}

    def process_line(line, line_idx, all_lines):
        """
        Executes ONE non-control-flow statement line (assignment, return,
        the existing old-style if/else-if(var=="value") nested lookahead,
        etc.), mutating `variables` via closure and returning the new
        result_value if a 'return' was hit, else None. Shared between the
        normal top-level scan and the new generic if/else branch execution.
        """
        # Skip comments
        if line.startswith('//') or line.startswith('#'):
            return None

        # Assignment: var = trim(source.field_XX)
        m = re.match(r'(\w+)\s*=\s*trim\(source\.field_(\w+)\)', line)
        if m:
            var_name, field_ref = m.group(1), m.group(2)
            variables[var_name] = get_field_value(field_ref, source_fields)
            return None

        # Assignment: var = source.field_XX
        m = re.match(r'(\w+)\s*=\s*source\.field_(\w+)', line)
        if m:
            var_name, field_ref = m.group(1), m.group(2)
            val = get_field_value(field_ref, source_fields)
            # If a LATER line explicitly splits this variable by newline,
            # this formula clearly intends to do its own multi-line parsing
            # — preserve the raw (multiline) value instead of auto-shortening
            # it to "first line minus leading slash". Only apply the legacy
            # shortcut when nothing downstream will split it itself.
            will_be_split = any(
                re.search(rf'split_(?:by_)?newline\(\s*{re.escape(var_name)}\s*\)', later)
                for later in all_lines[line_idx + 1:]
            )
            if will_be_split:
                variables[var_name] = val
            elif val and "\n" in val:
                first_line = val.split("\n")[0].strip()
                if first_line.startswith('/'):
                    first_line = first_line[1:]
                variables[var_name] = first_line or val.split("\n")[0].strip()
            else:
                variables[var_name] = val
            return None

        # Assignment: var = trim(var2) or trim(source.field_XX)
        m = re.match(r'(\w+)\s*=\s*trim\((\w+)\)', line)
        if m:
            var_name, src_var = m.group(1), m.group(2)
            val = variables.get(src_var, '')
            if not val:
                val = get_field_value(src_var, source_fields)
            variables[var_name] = val.strip() if isinstance(val, str) else val
            return None

        # NEW: var = split_by_newline(var2) — bare variable form, the idiom
        # actually used by our reference formulas (vs. the older literal-only
        # "split_newline(trim(source.field_XX))" pattern below).
        m = re.match(r'(\w+)\s*=\s*split_(?:by_)?newline\((\w+)\)', line)
        if m:
            var_name, src_var = m.group(1), m.group(2)
            val = variables.get(src_var, '')
            if not val:
                val = get_field_value_raw(src_var, source_fields)
            variables[var_name] = [l.strip() for l in val.split('\n') if l.strip()] if isinstance(val, str) else []
            return None

        # NEW: var = list_var[N:]  — slice from index N to end
        m = re.match(r'(\w+)\s*=\s*(\w+)\[(\d+):\]$', line)
        if m:
            var_name, list_var, idx = m.group(1), m.group(2), int(m.group(3))
            lst = variables.get(list_var, [])
            variables[var_name] = lst[idx:] if isinstance(lst, list) else []
            return None

        # Assignment: var = other_var (simple variable copy)
        m = re.match(r'^(\w+)\s*=\s*(\w+)$', line)
        if m:
            var_name, src_var = m.group(1), m.group(2)
            if src_var in variables:
                variables[var_name] = variables[src_var]
            return None

        # Assignment: var = substring(source.field_XX, start, len)
        m = re.match(r'(\w+)\s*=\s*substring\(source\.field_(\w+),\s*(\d+),\s*(\d+)\)', line)
        if m:
            var_name, field_ref = m.group(1), m.group(2)
            start, length = int(m.group(3)) - 1, int(m.group(4))
            val = get_field_value(field_ref, source_fields)
            variables[var_name] = val[start:start+length] if val else ''
            return None

        # Assignment: var = substring(var2, start, len)
        m = re.match(r'(\w+)\s*=\s*substring\((\w+),\s*(\d+),\s*(\d+)\)', line)
        if m:
            var_name, src_var = m.group(1), m.group(2)
            start, length = int(m.group(3)) - 1, int(m.group(4))
            val = variables.get(src_var, '')
            variables[var_name] = val[start:start+length] if val else ''
            return None

        # Assignment: var = to_lowercase(source.field_XX)
        m = re.match(r'(\w+)\s*=\s*to_lowercase\(source\.field_(\w+)\)', line)
        if m:
            var_name, field_ref = m.group(1), m.group(2)
            variables[var_name] = get_field_value(field_ref, source_fields).lower()
            return None

        # lines = split_newline(trim(source.field_XX))  — older literal-only form
        m = re.match(r'(\w+)\s*=\s*split_newline\(trim\(source\.field_(\w+)\)\)', line)
        if m:
            var_name, field_ref = m.group(1), m.group(2)
            val = get_field_value(field_ref, source_fields)
            variables[var_name] = [l.strip() for l in val.split('\n') if l.strip()]
            return None

        # name = trim(lines[N]) — array index access
        m = re.match(r'(\w+)\s*=\s*trim\((\w+)\[(\d+)\]\)', line)
        if m:
            var_name, list_var, idx = m.group(1), m.group(2), int(m.group(3))
            lst = variables.get(list_var, [])
            if isinstance(lst, list) and len(lst) > idx:
                variables[var_name] = lst[idx].strip()
            else:
                variables[var_name] = ''
            return None

        # var = lines[N]
        m = re.match(r'(\w+)\s*=\s*(\w+)\[(\d+)\]$', line)
        if m:
            var_name, list_var, idx = m.group(1), m.group(2), int(m.group(3))
            lst = variables.get(list_var, [])
            if isinstance(lst, list) and len(lst) > idx:
                variables[var_name] = lst[idx]
            else:
                variables[var_name] = ''
            return None

        # bic = starts_with(lines[0], "/") ? ... : lines[0]  (ternary form)
        m = re.match(r'(\w+)\s*=\s*starts_with\((\w+)\[0\],\s*"/"\)\s*\?', line)
        if m:
            var_name, list_var = m.group(1), m.group(2)
            lines_val = variables.get(list_var, [])
            if isinstance(lines_val, list) and lines_val:
                first = lines_val[0]
                if first.startswith('/'):
                    variables[var_name] = lines_val[1] if len(lines_val) > 1 else ''
                else:
                    variables[var_name] = first
            elif isinstance(lines_val, str):
                variables[var_name] = lines_val
            return None

        # if (is_valid_bic(bic)) then return bic  — single-line guard+return
        m = re.match(r'if\s*\(is_valid_bic\((\w+)\)\)\s*then', line)
        if m:
            var_name = m.group(1)
            val = variables.get(var_name, '')
            if val and len(val) in (8, 11):
                raise _ReturnSignal(val)
            return None

        # if (... var == "value" ...) then  — EXISTING nested-lookahead
        # mechanism, kept exactly as-is. This is the mechanism that already
        # correctly handles :23B:'s purpose-code derivation.
        m = re.match(r'(?:else\s+)?if\s*\((\w+)\s*==\s*"([^"]+)"\)\s*then', line)
        if m:
            var_name, expected = m.group(1), m.group(2)
            actual = variables.get(var_name, '')
            if actual == expected:
                for j in range(1, 20):
                    if line_idx + j >= len(all_lines):
                        break
                    next_line = all_lines[line_idx + j].strip()
                    if next_line.startswith('else') or next_line.startswith('endif'):
                        break
                    pm = re.match(r'(\w+)\s*=\s*"([^"]+)"', next_line)
                    if pm:
                        variables[pm.group(1)] = pm.group(2)
                    cm = re.match(r'if\s*\(contains\((\w+),\s*"([^"]+)"\)\)\s*then', next_line)
                    if cm:
                        cvar, ckw = cm.group(1), cm.group(2)
                        cval = variables.get(cvar, '').lower()
                        if ckw.lower() in cval:
                            for k in range(1, 5):
                                if line_idx + j + k >= len(all_lines):
                                    break
                                inner = all_lines[line_idx + j + k].strip()
                                if inner.startswith('else') or inner.startswith('endif'):
                                    break
                                ipm = re.match(r'(\w+)\s*=\s*"([^"]+)"', inner)
                                if ipm:
                                    variables[ipm.group(1)] = ipm.group(2)
                                    break
            return None

        # if contains(var, "keyword") then NEXT_LINE — single-step lookahead
        m = re.match(r'if\s*\(contains\((\w+),\s*"([^"]+)"\)\)\s*then', line)
        if m:
            var_name, keyword = m.group(1), m.group(2)
            val = variables.get(var_name, '').lower()
            if keyword.lower() in val:
                for j in range(1, 4):
                    if line_idx + j < len(all_lines):
                        next_line = all_lines[line_idx + j].strip()
                        pm = re.match(r'(\w+)\s*=\s*"([^"]+)"', next_line)
                        if pm:
                            variables[pm.group(1)] = pm.group(2)
                            break
            return None

        # Ternary: val = (cond) ? "X" : var
        m = re.match(r'(\w+)\s*=\s*\(([^)]+)\)\s*\?\s*"([^"]+)"\s*:\s*(\w+)', line)
        if m:
            var_name = m.group(1)
            condition = m.group(2)
            true_val = m.group(3)
            false_var = m.group(4)
            cond_val = variables.get(false_var, '')
            if '==' in condition:
                parts = condition.split('==')
                left = variables.get(parts[0].strip(), parts[0].strip().strip('"'))
                right = parts[1].strip().strip('"')
                variables[var_name] = true_val if left == right else cond_val
            else:
                variables[var_name] = cond_val
            return None

        # return { Key: var, ... } → return first variable value
        m = re.match(r'return\s*\{(.+)\}', line, re.DOTALL)
        if m:
            pairs_str = m.group(1)
            pair = re.search(r'\w+\s*:\s*(\w+)', pairs_str)
            if pair:
                var_ref = pair.group(1)
                val = variables.get(var_ref, '')
                if not val:
                    val = get_field_value(var_ref, source_fields)
                raise _ReturnSignal(val or var_ref)
            return None

        # acct_id = { IBAN: account } → use account value
        m = re.match(r'acct(?:_id)?\s*=\s*\{[^}]+\}', line)
        if m and 'account' in variables:
            variables['acct_id'] = variables.get('account', '')
            variables['acct'] = variables.get('account', '')
            return None

        # NEW: return source.field_XX — direct field reference, no
        # intermediate variable. Previously only bare "return var" (no dot)
        # was recognized, so simple null-guard formulas of the shape
        # "if (source.field_XX == null) then return null endif
        #  return source.field_XX" (used by several fields, e.g. :52A:)
        # always silently failed to return anything even when the field had
        # a real value — this was a pre-existing gap, not introduced by the
        # branch-handling rewrite, but worth fixing while in this code.
        m = re.match(r'return\s+source\.field_(\w+)$', line)
        if m:
            raise _ReturnSignal(get_field_value(m.group(1), source_fields))

        # return var (simple)
        m = re.match(r'return\s+(\w+)$', line)
        if m:
            var_ref = m.group(1)
            raise _ReturnSignal(variables.get(var_ref, get_field_value(var_ref, source_fields)))

        # return "literal"
        m = re.match(r'return\s+"([^"]+)"', line)
        if m:
            raise _ReturnSignal(m.group(1))

        return None  # unrecognized line — silently ignored, as before

    # ── Main scan with real if/else if/else/endif branch handling ──────────
    # Wrapped in try/except _ReturnSignal: a 'return' statement — at the top
    # level or inside any branch — unwinds here, where result_value is set
    # and we proceed to the SAME fallback-to-first-variable safety net the
    # rest of the function always applied, rather than exiting immediately
    # (see _ReturnSignal's docstring for why this matters).
    result_value = ''
    try:
        i = 0
        while i < len(lines):
            line = lines[i]

            # Old-style "if/else if (var == \"value\") then" lines are handled
            # entirely by process_line's own nested-lookahead mechanism (see
            # above) — they must NOT be treated as bare branch markers (which
            # would just skip them) nor intercepted by the new generic chain
            # handler below (whose _eval_condition doesn't parse compound
            # "contains(...) OR contains(...)" conditions used by :23B: etc.).
            old_style_match = re.match(r'(?:else\s+)?if\s*\((\w+)\s*==\s*"([^"]+)"\)\s*then', line)

            if not old_style_match and (
                line in ('endif', 'else', 'end if') or re.match(r'^else\s+if\s*\(.+\)\s*then\s*$', line)
            ):
                # Dangling branch marker (malformed pseudocode) OR a branch the
                # new generic handler already jumped past — nothing to execute.
                i += 1
                continue

            chain_match = None if old_style_match else re.match(r'^if\s*\(.+\)\s*then\s*$', line)
            if chain_match:
                cond_text = re.match(r'^if\s*\((.+)\)\s*then\s*$', line).group(1)
                block_end_idx = _find_block_end(lines, i)
                branch_start = i + 1
                current_cond = cond_text

                while True:
                    next_branch_idx = _find_next_branch(lines, branch_start, block_end_idx)
                    if _eval_condition(current_cond, variables, source_fields):
                        for k in range(branch_start, next_branch_idx):
                            process_line(lines[k], k, lines)
                        break
                    if next_branch_idx >= block_end_idx:
                        break  # no more branches, nothing matched
                    marker = lines[next_branch_idx]
                    if marker == 'else':
                        for k in range(next_branch_idx + 1, block_end_idx):
                            process_line(lines[k], k, lines)
                        break
                    else:
                        em = re.match(r'^else\s+if\s*\((.+)\)\s*then\s*$', marker)
                        current_cond = em.group(1) if em else 'false'
                        branch_start = next_branch_idx + 1

                i = block_end_idx + 1
                continue

            process_line(line, i, lines)
            i += 1

    except _ReturnSignal as rs:
        result_value = rs.value

    # If no result from return (or the returned value was empty/falsy), fall
    # back to the first assigned variable's value — this safety net is what
    # makes several reference formulas resolve correctly even though one of
    # their middle steps uses a helper function this evaluator doesn't
    # implement (parse_decimal, replace(), etc.): the formula's intended
    # final variable never gets a value, but an earlier intermediate
    # variable (typically the raw or partially-processed source field) is
    # still usable once _post_process()'s pattern-matching cleans it up.
    if not result_value and variables:
        result_value = next(iter(variables.values()), '')
        if isinstance(result_value, list):
            result_value = result_value[0] if result_value else ''

    return _post_process(result_value, target_xpath)


# ── XML-dataset pseudocode dialect ──────────────────────────────────────────
#
# WHY THIS EXISTS: the reference mapping files in backend/dataset/mappings/
# (the ones RAG surfaces via exact_rag_lookup and Generate Elements pulls in
# as MappingElement.expression) are written in a *different* pseudocode
# dialect than _evaluate_legacy_dialect understands — e.g.
#   CdtTrfTxInf.Amt.InstdAmt = decimal(MT.F32A.amount.replace(",","."))
# instead of "var = source.field_XX". None of that dialect's tokens
# (MT.F32A, decimal(), .replace(), firstLine(), extractBIC(), ternaries,
# elvis ?:) matched anything the legacy evaluator recognized, so every RAG
# formula silently fell through to the raw, untransformed source field —
# meaning "mapped" elements produced garbage output at transform time even
# though Generate Elements correctly found a target for them. This is a
# small recursive-descent interpreter for that second dialect, built
# directly from the actual pseudocode found across MT103/MT202/MT900/
# MT910/MT940/MT950's reference files.
#
# Each PseudoCode block can assign MULTIPLE ISO target paths (e.g. one line
# sets the amount, a second sets its @Ccy attribute) even though a single
# MappingElement only tracks one target_xpath — so this evaluator runs every
# statement in the block and returns whichever assignment matches this
# element's own (normalized) target_xpath.

class _MTFieldRef:
    """A reference to one raw SWIFT field (e.g. MT.F32A), lazily exposing
    named sub-components (.amount/.currency/.date) for the one field that
    actually needs them: the composite :32A: Value Date/Currency/Amount."""

    __slots__ = ('tag', 'raw')

    def __init__(self, tag: str, raw: str):
        self.tag = tag
        self.raw = raw or ''

    def component(self, name: str) -> str:
        name = name.lower()
        clean_tag = self.tag.upper().strip(':')
        if clean_tag == '32A':
            if name == 'date':
                return self.raw[0:6] if len(self.raw) >= 6 else ''
            if name == 'currency':
                return extract_currency_from_32a(self.raw)
            if name == 'amount':
                return extract_amount_from_32a(self.raw)
        if clean_tag == '33B':
            # :33B: format is 3!a15d (currency + amount, no date prefix) —
            # unlike :32A:, so it needs its own offset.
            if name == 'currency':
                return self.raw[0:3] if len(self.raw) >= 3 else ''
            if name == 'amount':
                return self.raw[3:].replace(',', '.').strip() if len(self.raw) > 3 else ''
        if clean_tag == '61':
            # :61: format: 6!n[4!n]2a[1!a]15d1!a3!c16x[//16x] — value date
            # (6 digits, mandatory) + entry date (4 digits, OPTIONAL) +
            # D/C mark (1 letter, or 2 for reversal codes RC/RD) + funds
            # code (1 letter, optional) + amount + transaction type +
            # reference. A fixed offset for the D/C mark only works when
            # the entry date happens to be present — this project's
            # dataset originally assumed it always was. Detect it instead
            # by character class: digits right after the value date mean
            # an entry date is there to skip; a letter means the D/C mark
            # starts immediately.
            date, dc, amount = self._parse_61()
            if name == 'date':
                return date
            if name in ('dcmark', 'dc', 'dc_mark'):
                return dc
            if name == 'amount':
                return amount
        # Unknown component on a non-composite tag — best effort: hand back
        # the whole raw value rather than silently losing it.
        return self.raw

    def _parse_61(self):
        raw = self.raw
        if len(raw) < 7:
            return raw[0:6], '', ''
        date = raw[0:6]
        pos = 6
        if len(raw) >= pos + 4 and raw[pos:pos + 4].isdigit():
            pos += 4  # optional entry date present — skip it
        dc = ''
        if len(raw) > pos and raw[pos].isalpha():
            dc = raw[pos]
            pos += 1
            if len(raw) > pos and raw[pos].isalpha() and raw[pos] in ('C', 'D'):
                pos += 1  # second char of a reversal code (RC/RD)
        if len(raw) > pos and raw[pos].isalpha():
            pos += 1  # optional funds code (3rd currency letter)
        amount_start = pos
        amount_end = amount_start
        while amount_end < len(raw) and (raw[amount_end].isdigit() or raw[amount_end] == ','):
            amount_end += 1
        amount = raw[amount_start:amount_end].replace(',', '.')
        return date, dc, amount

    def __str__(self):
        return self.raw

    def __bool__(self):
        return bool(self.raw.strip())


class _MTBlockRef:
    """Reference to envelope data (currently only block1, for the
    'MT.Block1.SenderBIC' fallback used when :52A: is absent)."""

    __slots__ = ('name', 'source_fields')

    def __init__(self, name: str, source_fields: dict):
        self.name = name
        self.source_fields = source_fields

    def __bool__(self):
        return True


class _XMLPathRef:
    """Reference into a flat {dotted.path: value} map built by
    extract_xml_source_fields() — the XML-direction counterpart to
    _MTFieldRef, used by XML->MT pseudocode (e.g. "F50K = XML.Dbtr.Nm").

    Unlike MT.F32A (a single token that resolves immediately), XML paths
    are genuinely hierarchical and arrive one .segment at a time through
    the SAME generic postfix-chaining loop that already handles
    .replace()/.truncate()/etc — so this class doesn't parse a whole path
    at once. Each .component(name) call always appends one segment and
    returns another _XMLPathRef, deferring the actual dict lookup until
    the value is finally used (__str__/__bool__) — resolving eagerly as
    soon as *any* prefix matched a leaf would be wrong here, since sibling
    keys can share a prefix that is itself also a leaf (e.g.
    "Amt" = "8500.00" AND "Amt.@Ccy" = "EUR" both exist; greedily
    resolving at "Amt" would strand ".@Ccy" with nowhere to go).
    """

    __slots__ = ('path', 'source_fields')

    def __init__(self, path: str, source_fields: dict):
        self.path = path
        self.source_fields = source_fields

    def component(self, name: str):
        new_path = f"{self.path}.{name}" if self.path else name
        return _XMLPathRef(new_path, self.source_fields)

    def __str__(self):
        return self.source_fields.get(self.path, '') if self.path else ''

    def __bool__(self):
        return bool(self.source_fields.get(self.path, '')) if self.path else False


_GLOBAL_VARS_CACHE: Optional[dict] = None


def invalidate_global_variables_cache() -> None:
    """Called by business_variables.py after any create/update/delete so
    the next transform picks up the new value immediately instead of
    waiting for a process restart."""
    global _GLOBAL_VARS_CACHE
    _GLOBAL_VARS_CACHE = None


def _get_global_variables() -> dict:
    """Merges <Variable name=.. value=..> constants from every reference
    mapping file (CENTURY_CUTOFF_YEAR, OPENING_BALANCE_CODE, ...) into one
    dict, then lets the admin-editable business_variables table override
    any of them by name — that table is the actual source of truth once
    an admin has touched a value (see business_variables.py); the XML
    defaults just seed it and cover any name an admin hasn't edited yet.
    Cached for the life of the process (invalidated on edit) since this
    is looked up per formula-evaluation line."""
    global _GLOBAL_VARS_CACHE
    if _GLOBAL_VARS_CACHE is None:
        merged: dict = {}
        try:
            from app.services.xml_mapping_parser import xml_parser
            for mapping_data in xml_parser.load_all_mappings().values():
                gv = mapping_data.get('general_information', {}).get('global_variables', {}) or {}
                for name, info in gv.items():
                    merged.setdefault(name, info.get('value', ''))
        except Exception as e:
            logger.warning(f"Could not load global variables for XML-dialect evaluator: {e}")

        try:
            from app.database import SessionLocal
            from app.models.business_variable import BusinessVariable
            db = SessionLocal()
            try:
                for var in db.query(BusinessVariable).all():
                    merged[var.name] = var.value
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load business_variables overrides: {e}")

        _GLOBAL_VARS_CACHE = merged
    return _GLOBAL_VARS_CACHE


def _name_matches_watchlist(extracted_name: str, entries: list) -> Optional[str]:
    """Case-insensitive, either-direction substring match — deliberately
    simple (no fuzzy/phonetic matching) since this is a demo watchlist,
    not a production screening engine. Returns the matched entry's name
    or None."""
    name_upper = extracted_name.strip().upper()
    if not name_upper:
        return None
    for entry in entries:
        if entry.name in name_upper or name_upper in entry.name:
            return entry.name
    return None


# mt_type -> (business variable that names its duplicate-detection
# window, unit that variable is expressed in). Each mapping file names
# AND scopes this differently — MT103/MT202 document a DAYS window,
# MT900/MT910 document HOURS (their own <Conditions> blocks: "REJECT
# E004: Duplicate MT900 notification" / MT910 equivalent) — reconciling
# that inconsistency is exactly what this map is for, rather than
# silently only ever reading MT103's spelling and unit. MT940/MT950 are
# deliberately absent: they're bank-generated STATEMENT messages, not
# something that initiates a transfer, and neither declares a duplicate-
# detection variable at all.
_DUPLICATE_WINDOW_VAR_BY_TYPE = {
    'MT103': ('DUPLICATE_DETECTION_WINDOW_DAYS', 'days'),
    'MT202': ('DUPLICATE_WINDOW_DAYS', 'days'),
    'MT900': ('DUPLICATE_DETECTION_WINDOW_HOURS', 'hours'),
    'MT910': ('DUPLICATE_DETECTION_WINDOW_HOURS', 'hours'),
}


def _check_duplicate_reference(db: Session, current_user: User, mt_type: str, source_fields: dict, filename: str) -> None:
    """Field :20: (reference) checked against previously-processed
    messages of the SAME mt_type, within that type's own duplicate-
    window business variable. Blocks (like sanctions), since processing
    the same payment reference twice is a real double-debit risk, not
    just something to flag and wave through. Recording the reference on
    success happens separately, at the very end of the caller, so a
    request that fails for some OTHER reason doesn't falsely "use up"
    the reference. Takes mt_type directly (not a Mapping object) since
    it's called from both directions — MT source uses mapping.source,
    XML source (reverse direction) uses mapping.target."""
    window_config = _DUPLICATE_WINDOW_VAR_BY_TYPE.get(mt_type)
    if not window_config:
        return
    window_var, unit = window_config

    reference = (source_fields.get('20') or '').strip()
    if not reference:
        return

    global_vars = _get_global_variables()
    try:
        window_value = float(global_vars.get(window_var, 7))
    except (TypeError, ValueError):
        window_value = 7
    if window_value <= 0:
        return

    from app.models.processed_transaction import ProcessedTransaction
    from app.models.audit_log import AuditLog
    from app.models.notification import Notification
    from app.models.user import User as _User

    cutoff = datetime.utcnow() - timedelta(**{unit: window_value})
    existing = db.query(ProcessedTransaction).filter(
        ProcessedTransaction.mt_type == mt_type,
        ProcessedTransaction.reference == reference,
        ProcessedTransaction.created_at >= cutoff
    ).first()
    if not existing:
        return

    details = (
        f"{mt_type} \"{filename}\" reference \"{reference}\" duplicates a message already processed "
        f"on {existing.created_at.strftime('%Y-%m-%d %H:%M')} (\"{existing.file_name}\"), "
        f"within the {window_value:g}-{unit[:-1] if window_value == 1 else unit} detection window"
    )
    db.add(AuditLog(
        user_id=current_user.id, username=current_user.username,
        action="duplicate_block", entity_type="TransformationJob", details=details,
    ))
    for admin in db.query(_User).filter(_User.is_admin.is_(True)).all():
        db.add(Notification(
            user_id=admin.id,
            message=f"🔁 Duplicate blocked: {current_user.username}'s transform of \"{filename}\" reuses reference \"{reference}\", already processed.",
            link="/audit-log"
        ))
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Transform blocked: Duplicate message ID detected — reference \"{reference}\" was already processed within the last {window_value:g} {unit}."
    )


def _record_processed_transaction(db: Session, current_user: User, mt_type: str, source_fields: dict, filename: str) -> None:
    """Called only after a transform actually succeeds — see
    _check_duplicate_reference's docstring for why recording is split
    from checking (and why this takes mt_type directly)."""
    if mt_type not in _DUPLICATE_WINDOW_VAR_BY_TYPE:
        return
    reference = (source_fields.get('20') or '').strip()
    if not reference:
        return

    from app.models.processed_transaction import ProcessedTransaction
    db.add(ProcessedTransaction(
        mt_type=mt_type, reference=reference, file_name=filename, user_id=current_user.id,
    ))
    db.commit()


def _required_approvals_for_amount(db: Session, mt_type: str, source_fields: dict) -> Optional[int]:
    """Multi-level approval by threshold: how many DIFFERENT admins must
    sign off before this transform's output is released. None means no
    hold is needed. Reuses the same two business variables the AML flag
    already reads — CRITICAL_AMOUNT_THRESHOLD is checked first since
    it's the higher bar (2 approvals); LARGE_AMOUNT_THRESHOLD alone
    means 1. MT103-only — no other type declares a critical/large tier
    calling for a HOLD (as opposed to just an alert)."""
    if mt_type != 'MT103':
        return None
    parsed = _extract_32a_amount(source_fields)
    if not parsed:
        return None
    amount, currency = parsed

    from app.models.business_variable import BusinessVariable
    for name, required in (('CRITICAL_AMOUNT_THRESHOLD', 2), ('LARGE_AMOUNT_THRESHOLD', 1)):
        var = db.query(BusinessVariable).filter(BusinessVariable.name == name).first()
        if not var:
            continue
        try:
            threshold = float(var.value)
        except ValueError:
            continue
        if var.currency and var.currency.upper() != currency.upper():
            continue
        if amount >= threshold:
            return required
    return None


def _screening_parties(mt_type: str, source_fields: dict) -> tuple:
    """Which fields get screened, and against which list(s) — differs by
    message type since MT103 carries customer NAMES (:50K:/:59:) while
    MT202 carries INSTITUTION BICs (:52A:/:58A:, per its own <Conditions>
    block: 'NOT is_sanctioned_institution(bic) -> ... BLOCK message').
    PEP screening only applies to MT103 — "politically exposed person"
    is inherently about individuals, not the banks MT202 moves money
    between, and MT202's dataset never declares PEP_SCREENING_ENABLED
    at all. Returns (parties, pep_applicable)."""
    if mt_type == 'MT103':
        return [
            ('Ordering Customer (:50K:)', _fn_firstLine(source_fields.get('50K', ''))),
            ('Beneficiary (:59:)', _fn_firstLine(source_fields.get('59', ''))),
        ], True
    if mt_type == 'MT202':
        return [
            ('Ordering Institution (:52A:)', _fn_extractBIC(source_fields.get('52A', ''))),
            ('Beneficiary Institution (:58A:)', _fn_extractBIC(source_fields.get('58A', ''))),
        ], False
    return [], False


def _check_sanctions_and_pep(db: Session, current_user: User, mt_type: str, source_fields: dict, filename: str) -> Optional[dict]:
    """Ordering/beneficiary parties (see _screening_parties) checked
    against the watchlist_entities table, gated by the
    SANCTIONS_SCREENING_ENABLED / PEP_SCREENING_ENABLED business
    variables — the dataset's own <Conditions> blocks document
    is_sanctioned_party()/is_sanctioned_institution() -> "BLOCK message
    AND ALERT compliance team immediately" and, for MT103 only,
    is_politically_exposed_person() -> "FLAG for enhanced due diligence
    review AND PROCEED with hold". Sanctions hits raise immediately
    (block the transform) — audited/notified right here since nothing
    downstream needs to happen. PEP hits do NOT raise or log/notify
    here: they only return the hit info, because "PROCEED with hold"
    means the output has to actually be generated and saved first (see
    the caller's late hold-creation block, same place the large-amount
    hold is created) before there's anything to hold. Returns the PEP
    hit as {'role', 'name', 'matched'}, or None."""
    parties, pep_applicable = _screening_parties(mt_type, source_fields)
    if not parties:
        return None

    global_vars = _get_global_variables()
    sanctions_enabled = str(global_vars.get('SANCTIONS_SCREENING_ENABLED', 'true')).strip().lower() == 'true'
    pep_enabled = pep_applicable and str(global_vars.get('PEP_SCREENING_ENABLED', 'true')).strip().lower() == 'true'
    if not sanctions_enabled and not pep_enabled:
        return None

    from app.models.watchlist_entity import WatchlistEntity
    from app.models.audit_log import AuditLog
    from app.models.notification import Notification
    from app.models.user import User as _User

    # 'active' entries are fully approved; 'pending_remove' ones are still
    # enforced too — a removal only stops here once a SECOND compliance
    # officer confirms it (see watchlist.py's maker-checker), so a single
    # officer can't silently disable a hit just by requesting removal.
    enforced_statuses = ('active', 'pending_remove')
    sanctions_list = db.query(WatchlistEntity).filter(
        WatchlistEntity.list_type == 'SANCTIONS', WatchlistEntity.status.in_(enforced_statuses)
    ).all() if sanctions_enabled else []
    pep_list = db.query(WatchlistEntity).filter(
        WatchlistEntity.list_type == 'PEP', WatchlistEntity.status.in_(enforced_statuses)
    ).all() if pep_enabled else []

    for role, name in parties:
        if not name:
            continue

        sanctions_hit = _name_matches_watchlist(name, sanctions_list) if sanctions_enabled else None
        if sanctions_hit:
            details = f"{mt_type} \"{filename}\" {role} \"{name}\" matches sanctions watchlist entry \"{sanctions_hit}\""
            db.add(AuditLog(
                user_id=current_user.id, username=current_user.username,
                action="sanctions_block", entity_type="TransformationJob", details=details,
            ))
            for admin in db.query(_User).filter(_User.is_admin.is_(True)).all():
                db.add(Notification(
                    user_id=admin.id,
                    message=f"🚫 SANCTIONS HIT: {current_user.username}'s transform of \"{filename}\" was blocked — {role} \"{name}\" matches the sanctions watchlist.",
                    link="/audit-log"
                ))
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Transform blocked: {role} matches a sanctions watchlist entry. Compliance has been alerted."
            )

        pep_hit = _name_matches_watchlist(name, pep_list) if pep_enabled else None
        if pep_hit:
            return {'role': role, 'name': name, 'matched': pep_hit}

    return None


def _extract_32a_amount(source_fields: dict) -> Optional[tuple]:
    """Parses field :32A: (YYMMDD + 3-letter currency + comma-decimal
    amount) into (amount: float, currency: str), or None if the field is
    missing/malformed. Same composite format (SWIFT '6!n3!a15d') across
    MT103/MT202/MT900/MT910 — shared by the large-amount alert/hold
    checks, which all key off the same figure."""
    field_32a = source_fields.get('32A') or source_fields.get(':32A:')
    if not field_32a:
        return None
    match = re.match(r'^\d{6}([A-Z]{3})([\d,]+)$', field_32a.strip())
    if not match:
        return None
    currency, amount_str = match.group(1), match.group(2)
    try:
        amount = float(amount_str.replace(',', '.'))
    except ValueError:
        return None
    return amount, currency


# mt_type -> the business variable naming its large-amount alert
# threshold. MT103's own <Conditions> block documents "FLAG for AML
# compliance review AND PROCEED"; MT900/MT910's document the identical
# pattern under their own variable names ("ALERT treasury AND PROCEED —
# warning not rejection"). MT202 is deliberately absent: its dataset
# never declares a large-amount variable at all. MT940/MT950 likewise
# absent — statement messages, nothing being alerted on.
_LARGE_AMOUNT_VAR_BY_TYPE = {
    'MT103': 'LARGE_AMOUNT_THRESHOLD',
    'MT900': 'LARGE_DEBIT_THRESHOLD',
    'MT910': 'LARGE_CREDIT_THRESHOLD',
}


def _check_large_amount_flag(db: Session, current_user: User, mt_type: str, source_fields: dict, filename: str) -> None:
    """Field :32A: (date+currency+amount) checked against this mt_type's
    large-amount business variable (see _LARGE_AMOUNT_VAR_BY_TYPE) — the
    one enforcement each dataset's own <Conditions> block documents but
    that, until now, no code actually ran. Never blocks the transform —
    only logs + notifies, matching that documented ElseAction."""
    threshold_var_name = _LARGE_AMOUNT_VAR_BY_TYPE.get(mt_type)
    if not threshold_var_name:
        return
    parsed = _extract_32a_amount(source_fields)
    if not parsed:
        return
    amount, currency = parsed

    from app.models.business_variable import BusinessVariable
    threshold_var = db.query(BusinessVariable).filter(BusinessVariable.name == threshold_var_name).first()
    if not threshold_var:
        return
    try:
        threshold = float(threshold_var.value)
    except ValueError:
        return
    if threshold_var.currency and threshold_var.currency.upper() != currency.upper():
        return

    if amount < threshold:
        return

    from app.models.audit_log import AuditLog
    from app.models.notification import Notification
    from app.models.user import User as _User
    details = f"{mt_type} \"{filename}\" amount {amount:,.2f} {currency} >= {threshold_var_name} ({threshold:,.2f} {threshold_var.currency or currency})"
    db.add(AuditLog(
        user_id=current_user.id, username=current_user.username,
        action="aml_flag", entity_type="TransformationJob", details=details,
    ))
    for admin in db.query(_User).filter(_User.is_admin.is_(True)).all():
        db.add(Notification(
            user_id=admin.id,
            message=f"⚠️ Large amount alert: {current_user.username}'s transform of \"{filename}\" is {amount:,.2f} {currency}, above the {threshold:,.2f} threshold.",
            link="/audit-log"
        ))
    db.commit()


def _as_str(value) -> str:
    if isinstance(value, _MTFieldRef):
        return value.raw
    if isinstance(value, _MTBlockRef):
        return ''
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _xml_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (_MTFieldRef, _MTBlockRef)):
        return bool(value)
    text = str(value).strip()
    return bool(text) and text.lower() not in ('false', 'none', 'null', '0')


def _xml_arith(left, right, op: str) -> str:
    l_str, r_str = _as_str(left), _as_str(right)
    try:
        l_num, r_num = float(l_str), float(r_str)
    except (TypeError, ValueError):
        # Non-numeric operands: '+' still makes sense as concatenation;
        # '-' has no sensible string meaning, so just drop the right side.
        return (l_str + r_str) if op == 'PLUS' else l_str
    result = l_num + r_num if op == 'PLUS' else l_num - r_num
    return str(int(result)) if result == int(result) else str(result)


def _fn_trim(x=''): return (x or '').strip()
def _fn_upper(x=''): return (x or '').upper()
def _fn_normalize(x=''): return re.sub(r'\s+', ' ', x or '').strip()
def _fn_length(x=''): return str(len(x or ''))
def _fn_contains(x='', y=''): return (y or '') in (x or '')


def _fn_to_integer(x=''):
    try:
        return str(int((x or '').strip()))
    except Exception:
        return (x or '').strip()


def _fn_matches(x='', pattern=''):
    try:
        return bool(re.match(pattern, x or ''))
    except re.error:
        return False


def _fn_replace(x='', a='', b=''): return (x or '').replace(a, b)


def _fn_truncate(x='', n='0'):
    try:
        return (x or '')[:int(n)]
    except Exception:
        return x or ''


def _fn_substring(x='', start='1', length=None):
    x = x or ''
    try:
        s = max(int(start) - 1, 0)
    except Exception:
        s = 0
    if length is None or length == '':
        return x[s:]
    try:
        return x[s:s + int(length)]
    except Exception:
        return x[s:]


def _fn_substring_before(x='', sep=''):
    x = x or ''
    idx = x.find(sep)
    return x[:idx] if idx != -1 else x


def _fn_find(x='', needle='', start='1'):
    x = x or ''
    try:
        s = max(int(start) - 1, 0)
    except Exception:
        s = 0
    idx = x.find(needle, s)
    return str(idx + 1) if idx != -1 else str(len(x) + 1)


def _fn_decimal(x=''):
    """Cleans up an already comma->dot-converted SWIFT amount string,
    ensuring a two-digit decimal part (SWIFT allows a bare trailing comma
    for whole amounts, e.g. "25000," -> "25000.00")."""
    x = (x or '').strip()
    if not x:
        return ''
    if x.endswith('.'):
        return x + '00'
    m = re.match(r'^(-?\d+)\.(\d)$', x)
    if m:
        return f"{m.group(1)}.{m.group(2)}0"
    return x


_IBAN_RE = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$')
_BIC_RE = re.compile(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$')


def _fn_isIBAN(x=''): return bool(_IBAN_RE.match((x or '').strip()))
def _fn_is_valid_bic(x=''): return bool(_BIC_RE.match((x or '').strip()))


def _fn_extractBIC(x=''):
    x = (x or '').strip()
    for line in x.split('\n'):
        line = line.strip()
        if _BIC_RE.match(line):
            return line
    m = re.search(r'\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b', x)
    if m:
        return m.group(0)
    lines = [l.strip() for l in x.split('\n') if l.strip()]
    return lines[-1] if lines else ''


def _fn_firstLine(x=''):
    """SWIFT :50K:/:59:-style field: '/account' (optional) then name lines.
    Returns the NAME — i.e. the first line if there's no account line,
    otherwise the line after it."""
    lines = (x or '').split('\n')
    if not lines:
        return ''
    if lines[0].strip().startswith('/'):
        return lines[1].strip() if len(lines) > 1 else ''
    return lines[0].strip()


def _fn_accountLine(x=''):
    lines = (x or '').split('\n')
    if lines and lines[0].strip().startswith('/'):
        return lines[0].strip()[1:].strip()
    return ''


def _fn_joinLines(x=''):
    return ' '.join(l.strip() for l in (x or '').split('\n') if l.strip())


def _fn_now(fmt=''): return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
def _fn_today(fmt=''): return datetime.utcnow().strftime('%Y-%m-%d')


def _fn_expandCentury(x='', fmt='', hint=''):
    """SWIFT 2-digit year -> ISO date. hint is either a literal century
    ("20xx"/"19xx", used by MT202) or a cutoff year (e.g. "50" from
    CENTURY_CUTOFF_YEAR: yy >= cutoff -> 19xx, else 20xx)."""
    x = (x or '').strip()
    if len(x) < 6 or not x[:6].isdigit():
        return x
    yy, mm, dd = x[0:2], x[2:4], x[4:6]
    hint = (hint or '').strip()
    if hint.startswith('20'):
        century = '20'
    elif hint.startswith('19'):
        century = '19'
    else:
        try:
            cutoff = int(hint)
        except Exception:
            cutoff = 50
        century = '19' if int(yy) >= cutoff else '20'
    return f"{century}{yy}-{mm}-{dd}"


def _fn_parseDateTimeOffset(x='', cutoff=''):
    """:13D: format YYMMDDHHMM+HHMM (date/time indication with UTC offset)."""
    x = (x or '').strip()
    m = re.match(r'^(\d{6})(\d{4})', x)
    if not m:
        return x
    date_part = _fn_expandCentury(m.group(1), 'yyMMdd', cutoff)
    hh, mi = m.group(2)[0:2], m.group(2)[2:4]
    return f"{date_part}T{hh}:{mi}:00"


def _fn_extract_date(x=''): return _fn_expandCentury(x, 'yyMMdd', '50')
def _fn_extract_currency(x=''): return extract_currency_from_32a(x or '')


def _fn_isoDateToSwift(x=''):
    """XML->MT direction counterpart to expandCentury: ISO 'YYYY-MM-DD' ->
    SWIFT 'YYMMDD' (used to rebuild composite fields like :32A: from
    IntrBkSttlmDt, the reverse of extracting a date out of one)."""
    x = (x or '').strip()
    if len(x) != 10 or x[4] != '-' or x[7] != '-':
        return x
    return x[2:4] + x[5:7] + x[8:10]


def _fn_toSwiftDCMark(x=''):
    """XML->MT direction counterpart to the CdtDbtInd derivation in
    :60F:/:61:/:62F:/:64:/:65:'s forward pseudocode (dc_mark == "C" ->
    "CRDT" else "DBIT"): ISO CdtDbtInd ('CRDT'/'DBIT') -> SWIFT's
    single-char balance D/C mark ('C'/'D'), used to rebuild composite
    balance fields like :60F: from Bal_OPBD.CdtDbtInd."""
    x = (x or '').strip().upper()
    if x == 'CRDT':
        return 'C'
    if x == 'DBIT':
        return 'D'
    return x


def _fn_buildCustomerLine(account='', name='', town='', country=''):
    """XML->MT direction counterpart to accountLine()/firstLine(): builds a
    SWIFT :50K:/:59:-style customer field ('/account' on its own line, then
    name, then an optional town+country address line) from separate
    account/name/town/country values. Option K allows up to 4 name+address
    lines after the account line; town and country are appended as a third
    line so postal address isn't silently dropped on XML->MT conversion.
    Pseudo-code string literals don't unescape "\\n" into a real newline
    (the tokenizer treats STRING contents literally), so this exists as a
    named function rather than needing raw newline escaping in dataset XML.
    """
    account = (account or '').strip()
    name = (name or '').strip()
    town = (town or '').strip()
    country = (country or '').strip()
    lines = []
    if account:
        lines.append(f"/{account}")
    if name:
        lines.append(name)
    addr = ' '.join(p for p in (town, country) if p)
    if addr:
        lines.append(addr)
    return '\n'.join(lines) if lines else ''


def _fn_toSwiftAmount(x=''):
    """XML->MT direction counterpart to decimal(): ISO decimal amount
    ('8500.00') -> SWIFT comma-decimal ('8500,'/'8500,50'), stripping
    trailing zeros but always keeping the separating comma itself (SWIFT's
    convention for a whole-number amount)."""
    x = (x or '').strip().replace('.', ',')
    if ',' not in x:
        return x + ','
    whole, frac = x.split(',', 1)
    frac = frac.rstrip('0')
    return f"{whole},{frac}"


def _fn_purposeCodeMapping(op_code='', remittance=''):
    """Best-effort ISO 20022 purpose-code guess from free-text remittance
    info / bank operation code — the reference dataset has no real lookup
    table for this, so this fails open to the generic "OTHR" code rather
    than leaving the field empty."""
    text = f"{op_code} {remittance}".upper()
    keywords = [
        ('SALARY', 'SALA'), ('PAYROLL', 'SALA'), ('PENSION', 'PENS'),
        ('TAX', 'TAXS'), ('DIVIDEND', 'DIVD'), ('INVOICE', 'SUPP'),
        ('SUPPLIER', 'SUPP'), ('RENT', 'RENT'), ('LOAN', 'LOAN'),
        ('INSURANCE', 'INSU'),
    ]
    for kw, code in keywords:
        if kw in text:
            return code
    return 'OTHR'


# Compliance/reference-data lookups with no real backing data source in
# this evaluator: best-effort stubs that fail open (never block a transform
# on a check we have no way to actually perform).
def _fn_is_sanctioned_party(x=''): return False
def _fn_is_politically_exposed_person(x=''): return False
def _fn_exists_duplicate(x=''): return False
def _fn_lookupBIC(x=''): return x or ''
def _fn_coreAccountLookup(x=''): return x or ''


_REFERENCE_DATA_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def invalidate_reference_data_cache() -> None:
    """Called by reference_data.py after any create/update/delete/import so
    the next transform picks up the change immediately instead of waiting
    for a process restart — same reasoning as invalidate_global_variables_cache()
    above, for the same reason (this cache is looked up per formula line)."""
    global _REFERENCE_DATA_CACHE
    _REFERENCE_DATA_CACHE = None


def _get_reference_data_map(category: str) -> Dict[str, str]:
    """{code: name} for every active ReferenceData row in `category`,
    fetched once per process (or since the last invalidate) and cached —
    ReferenceLookup() calls this once per formula line, same access
    pattern as _get_global_variables(). Opens its own short-lived session
    rather than threading a `db` parameter through evaluate_expression():
    the XML-dialect evaluator has no db in scope at all (it runs during
    Transform, Generate Elements preview, and the pipeline auto-consumption
    path alike), so this matches how _get_global_variables() already
    solves the identical problem for BusinessVariable lookups."""
    global _REFERENCE_DATA_CACHE
    if _REFERENCE_DATA_CACHE is None:
        _REFERENCE_DATA_CACHE = {}
    if category not in _REFERENCE_DATA_CACHE:
        by_code: Dict[str, str] = {}
        try:
            from app.database import SessionLocal
            from app.models.reference_data import ReferenceData
            db = SessionLocal()
            try:
                rows = db.query(ReferenceData).filter(
                    ReferenceData.category == category, ReferenceData.is_active == True  # noqa: E712
                ).all()
                for r in rows:
                    by_code[r.code] = r.name
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load ReferenceData for category '{category}': {e}")
        _REFERENCE_DATA_CACHE[category] = by_code
    return _REFERENCE_DATA_CACHE[category]


def _fn_referenceLookup(category='', code=''):
    """ReferenceLookup("ISO_CURRENCY", currencyCode) / ReferenceLookup("COUNTRY",
    countryCode) — resolves a code to its Reference Data display name (e.g.
    "EUR" -> "Euro"). Empty string (not an error) when the category has no
    active rows or the code isn't found, so a formula using this to enrich
    a field degrades to a blank rather than aborting the whole transform."""
    return _get_reference_data_map(category).get((code or '').strip().upper(), '')
def _fn_describeSecurity(x=''): return x or ''
def _fn_defaultCustodian(): return ''


def _fn_extractISIN(x=''):
    m = re.search(r'\b[A-Z]{2}[A-Z0-9]{9}\d\b', x or '')
    return m.group(0) if m else (x or '')


def _fn_sum(*args):
    total = 0.0
    for a in args:
        try:
            total += float(a)
        except (TypeError, ValueError):
            pass
    return str(int(total)) if total == int(total) else str(total)


_XML_DIALECT_FUNCTIONS = {
    'trim': _fn_trim, 'upper': _fn_upper, 'normalize': _fn_normalize,
    'length': _fn_length, 'to_integer': _fn_to_integer, 'contains': _fn_contains,
    'matches': _fn_matches, 'replace': _fn_replace, 'truncate': _fn_truncate,
    'substring': _fn_substring, 'substring_before': _fn_substring_before,
    'find': _fn_find, 'decimal': _fn_decimal, 'isIBAN': _fn_isIBAN,
    'is_valid_bic': _fn_is_valid_bic, 'is_valid_bic_format': _fn_is_valid_bic,
    'validateBIC': _fn_is_valid_bic, 'extractBIC': _fn_extractBIC,
    'firstLine': _fn_firstLine, 'accountLine': _fn_accountLine,
    'joinLines': _fn_joinLines, 'now': _fn_now, 'today': _fn_today,
    'expandCentury': _fn_expandCentury, 'parseDateTimeOffset': _fn_parseDateTimeOffset,
    'extract_date': _fn_extract_date, 'extract_currency': _fn_extract_currency,
    'isoDateToSwift': _fn_isoDateToSwift, 'toSwiftAmount': _fn_toSwiftAmount,
    'toSwiftDCMark': _fn_toSwiftDCMark,
    'buildCustomerLine': _fn_buildCustomerLine,
    'purposeCodeMapping': _fn_purposeCodeMapping,
    'is_sanctioned_party': _fn_is_sanctioned_party,
    'is_sanctioned_institution': _fn_is_sanctioned_party,
    'is_sanctioned_entity': _fn_is_sanctioned_party,
    'is_politically_exposed_person': _fn_is_politically_exposed_person,
    'exists_duplicate': _fn_exists_duplicate, 'lookupBIC': _fn_lookupBIC,
    'coreAccountLookup': _fn_coreAccountLookup, 'describeSecurity': _fn_describeSecurity,
    'defaultCustodian': _fn_defaultCustodian, 'extractISIN': _fn_extractISIN,
    'sum': _fn_sum, 'ReferenceLookup': _fn_referenceLookup,
}


def _call_xml_function(name: str, args: list):
    sargs = [_as_str(a) for a in args]
    fn = _XML_DIALECT_FUNCTIONS.get(name)
    if fn is None:
        # Unrecognized function: best effort — pass its first argument
        # through unchanged rather than losing the whole assignment.
        return sargs[0] if sargs else ''
    try:
        return fn(*sargs)
    except Exception as e:
        logger.debug(f"XML-dialect function '{name}' failed on {sargs!r}: {e}")
        return sargs[0] if sargs else ''


def _access_component(value, name: str):
    if isinstance(value, _MTFieldRef):
        return value.component(name)
    if isinstance(value, _MTBlockRef):
        if name == 'SenderBIC':
            lt = value.source_fields.get('__block1_lt_address__', '') or ''
            return lt[:8] if len(lt) >= 8 else lt
        return ''
    if isinstance(value, _XMLPathRef):
        return value.component(name)
    return value


_XML_TOKEN_RE = re.compile(r'''
    \s*(?:
        (?P<STRING>"(?:[^"\\]|\\.)*") |
        (?P<NUMBER>\d+(?:\.\d+)?) |
        (?P<ELVIS>\?:) |
        (?P<QMARK>\?) |
        (?P<COLON>:) |
        (?P<EQ>==) |
        (?P<NEQ>!=) |
        (?P<NOT>!) |
        (?P<PLUS>\+) |
        (?P<MINUS>-) |
        (?P<LPAREN>\() |
        (?P<RPAREN>\)) |
        (?P<COMMA>,) |
        (?P<DOT>\.) |
        (?P<IDENT>[A-Za-z_@][A-Za-z0-9_@]*)
    )
''', re.VERBOSE)


def _tokenize_xml_expr(text: str):
    tokens = []
    pos = 0
    while pos < len(text):
        m = _XML_TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        if kind:
            tokens.append((kind, m.group(kind)))
    return tokens


class _XmlDialectParser:
    """Small recursive-descent parser/evaluator (parses and evaluates in
    the same pass — there's no need for a separate AST at this scale) for
    the expression grammar on the right-hand side of a pseudocode
    assignment: elvis (?:) > ternary (?:) > OR/AND > ==/!= > unary (!) >
    postfix (.method()/.component) > primary (literal / MT.Fxx / call)."""

    def __init__(self, tokens, source_fields, variables, global_vars):
        self.tokens = tokens
        self.pos = 0
        self.source_fields = source_fields
        self.variables = variables
        self.global_vars = global_vars

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def _advance(self):
        tok = self._peek()
        self.pos += 1
        return tok

    def _expect(self, kind):
        tok = self._advance()
        if tok[0] != kind:
            raise ValueError(f"Expected {kind}, got {tok}")
        return tok

    def parse(self):
        return self.parse_elvis()

    def parse_elvis(self):
        left = self.parse_ternary()
        if self._peek()[0] == 'ELVIS':
            self._advance()
            right = self.parse_ternary()
            return left if _xml_truthy(left) else right
        return left

    def parse_ternary(self):
        left = self.parse_or()
        if self._peek()[0] == 'QMARK':
            self._advance()
            true_val = self.parse_elvis()
            self._expect('COLON')
            false_val = self.parse_elvis()
            return true_val if _xml_truthy(left) else false_val
        return left

    def parse_or(self):
        left = self.parse_eq()
        while self._peek()[0] == 'IDENT' and self._peek()[1] in ('OR', 'AND'):
            op = self._advance()[1]
            right = self.parse_eq()
            left = (_xml_truthy(left) or _xml_truthy(right)) if op == 'OR' \
                else (_xml_truthy(left) and _xml_truthy(right))
        return left

    def parse_eq(self):
        left = self.parse_add()
        while self._peek()[0] in ('EQ', 'NEQ'):
            op = self._advance()[0]
            right = self.parse_add()
            eq = _as_str(left) == _as_str(right)
            left = eq if op == 'EQ' else (not eq)
        return left

    def parse_add(self):
        # Only used by the handful of formulas that compute a substring
        # length arithmetically (e.g. "amount_end - 12" in MT940/950's
        # :61: parsing) — real subtraction/concatenation, not comparison.
        left = self.parse_unary()
        while self._peek()[0] in ('PLUS', 'MINUS'):
            op = self._advance()[0]
            right = self.parse_unary()
            left = _xml_arith(left, right, op)
        return left

    def parse_unary(self):
        if self._peek()[0] == 'NOT':
            self._advance()
            return not _xml_truthy(self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        value = self.parse_primary()
        while self._peek()[0] == 'DOT':
            self._advance()
            name = self._expect('IDENT')[1]
            if self._peek()[0] == 'LPAREN':
                # Method-chain call (e.g. ".replace(a,b)", ".truncate(140)")
                # — the value before the dot is the call's implicit first
                # argument, same as Python's obj.method(args) desugaring to
                # method(obj, args).
                value = _call_xml_function(name, [value] + self.parse_args())
            else:
                value = _access_component(value, name)
        return value

    def parse_args(self):
        self._expect('LPAREN')
        args = []
        if self._peek()[0] != 'RPAREN':
            args.append(self.parse_elvis())
            while self._peek()[0] == 'COMMA':
                self._advance()
                args.append(self.parse_elvis())
        self._expect('RPAREN')
        return args

    def parse_primary(self):
        kind, text = self._peek()
        if kind == 'STRING':
            self._advance()
            return text[1:-1]
        if kind == 'NUMBER':
            self._advance()
            return text
        if kind == 'LPAREN':
            self._advance()
            value = self.parse_elvis()
            self._expect('RPAREN')
            return value
        if kind == 'IDENT':
            self._advance()
            if text == 'MT':
                self._expect('DOT')
                field_name = self._expect('IDENT')[1]
                if field_name.startswith('F') and len(field_name) > 1 and field_name[1].isdigit():
                    tag = field_name[1:]
                    return _MTFieldRef(tag, get_field_value(tag, self.source_fields))
                if field_name.lower().startswith('block'):
                    return _MTBlockRef(field_name.lower(), self.source_fields)
                return get_field_value(field_name, self.source_fields)
            if text == 'XML':
                self._expect('DOT')
                first_segment = self._expect('IDENT')[1]
                # Returns an unresolved _XMLPathRef holding just this first
                # segment — parse_postfix's normal .segment chaining (the
                # same loop that handles .replace()/.truncate()/etc for the
                # MT direction) descends the rest of the path one dot at a
                # time via _XMLPathRef.component().
                return _XMLPathRef(first_segment, self.source_fields)
            if self._peek()[0] == 'LPAREN':
                return _call_xml_function(text, self.parse_args())
            if text in self.variables:
                return self.variables[text]
            if text in self.global_vars:
                return self.global_vars[text]
            # Bare identifier that isn't a known variable/constant (e.g. a
            # boolean-ish literal used loosely in the pseudocode) — return
            # it as its own literal value.
            return text
        # Unrecognized token: consume it so we don't spin forever, contribute
        # nothing to the result.
        self._advance()
        return ''


_XML_ASSIGN_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_.]*(?:\.@[A-Za-z_][A-Za-z0-9_]*)?)\s*=\s*(.+)$')
_XML_IF_START_RE = re.compile(r'^if\s*\(')


def _split_if_guard(line: str):
    """Returns (cond_text, rest) for a leading 'if(...)' guard, or None.
    A regex like r'if\((.+?)\)(.+)' can't be used here: real conditions
    nest their own parens (e.g. 'if(!isIBAN(account)) Path = account'), so
    the first ')' encountered belongs to isIBAN(...), not to the guard —
    matching on it truncates the condition and corrupts the rest of the
    statement. This walks paren depth instead to find the guard's own
    matching close-paren."""
    m = _XML_IF_START_RE.match(line)
    if not m:
        return None
    depth = 1
    i = m.end()
    while i < len(line) and depth > 0:
        if line[i] == '(':
            depth += 1
        elif line[i] == ')':
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return line[m.end():i - 1], line[i:].strip()


def _eval_xml_snippet(text: str, source_fields: dict, variables: dict, global_vars: dict):
    tokens = _tokenize_xml_expr(text)
    try:
        return _XmlDialectParser(tokens, source_fields, variables, global_vars).parse()
    except Exception as e:
        logger.debug(f"XML-dialect snippet failed to parse: {text!r} ({e})")
        return ''


def _exec_xml_statement(line: str, variables: dict, target_values: dict, source_fields: dict, global_vars: dict):
    line = line.strip()
    if not line or line.startswith('//') or line.startswith('#'):
        return
    guard = _split_if_guard(line)
    if guard:
        cond_text, rest = guard
        if not _xml_truthy(_eval_xml_snippet(cond_text, source_fields, variables, global_vars)):
            return
        line = rest
    m = _XML_ASSIGN_RE.match(line)
    if not m:
        return
    lhs, rhs = m.group(1), m.group(2)
    value = _as_str(_eval_xml_snippet(rhs, source_fields, variables, global_vars))
    if lhs[0].isupper():
        # ISO 20022 target path (e.g. "CdtTrfTxInf.Amt.InstdAmt", or
        # "....@Ccy" for an XML attribute — captured but not currently
        # wired into the XML builder, which has no attribute support).
        target_values[lhs] = value
    else:
        # Local pseudocode variable (lowercase/snake_case by convention
        # across every reference file — e.g. "account", "dc_mark").
        variables[lhs] = value


def _normalize_target_path(xpath: str) -> str:
    """"/Document/FIToFICstmrCdtTrf/CdtTrfTxInf/Amt/InstdAmt" ->
    "CdtTrfTxInf.Amt.InstdAmt", matching the dotted target-path form used
    on the left-hand side of the XML dialect's assignments."""
    if not xpath:
        return ''
    parts = [p for p in xpath.replace('/Document/', '').split('/') if p]
    root_elements = ('BkToCstmrDbtCdtNtfctn', 'FIToFICstmrCdtTrf', 'FICdtTrf', 'BkToCstmrStmt')
    if parts and parts[0] in root_elements:
        parts = parts[1:]
    return '.'.join(parts)


def _match_target_value(target_values: dict, normalized_path: str) -> str:
    """Looks up the computed value for this element's own target_xpath among
    every path a multi-statement PseudoCode block assigned. Handles two
    mismatches between the assignment's left-hand side and the real XPath,
    seen in different reference files:

    1. The LHS is a *shorter, context-relative* name — e.g. MT900/MT910's
       "Ntry.Amt" for a field whose real XPath is ".../Ntfctn/Ntry/Amt",
       since the formula's author was thinking in terms of "the Ntry
       element currently being built", not the full document path. Handled
       by accepting the longest key that matches as a complete trailing
       SUFFIX of normalized_path — which also correctly picks "Ntry.Amt"
       over "TxDtls.Amt" for a target ending in ".../Ntry/Amt" rather than
       ".../TxDtls/Amt", since only one fully matches as a suffix.

    2. The LHS is *more specific* than the declared TargetField XPath — e.g.
       MT900's :25: sets "Ntfctn.Acct.Id.IBAN" or "...Othr.Id" depending on
       an isIBAN() branch, but the TargetField itself is only declared down
       to ".../Ntfctn/Acct/Id" (it doesn't distinguish the IBAN/Othr.Id
       sub-case). Handled by falling back to any key that has
       normalized_path as a complete leading PREFIX — whichever one of the
       mutually-exclusive conditional branches actually fired.

    Suffix match is tried first (it's the far more common shape); prefix
    match is only a fallback since normalized_path prefixing a key is a
    weaker signal (multiple sibling target elements could share a prefix).

    3. The target is a bare CONTAINER element (e.g. MT940/950's :61:,
       whose TargetField is just ".../Stmt/Ntry") and the formula assigns
       to several of its children using the container's own bare name as
       their leading segment — "Ntry.Amt", "Ntry.CdtDbtInd",
       "Ntry.ValDt.Dt" — rather than any single leaf matching the target
       exactly. Neither suffix nor prefix matching above can align these
       (the container name is the LAST segment of normalized_path but the
       FIRST segment of the keys), so this is a separate case: collect
       every key sharing that leading segment into a nested dict and
       return it instead of one string. set_xpath_value merges dicts, so
       returning here lets one MappingElement populate multiple children
       of the same composite element at once."""
    if not normalized_path:
        return ''
    if normalized_path in target_values:
        return target_values[normalized_path]
    norm_parts = normalized_path.split('.')
    best_key, best_len = None, 0
    for key in target_values:
        key_parts = key.split('.')
        if len(key_parts) > len(norm_parts) or len(key_parts) <= best_len:
            continue
        if all(key_parts[-i] == norm_parts[-i] for i in range(1, len(key_parts) + 1)):
            best_len = len(key_parts)
            best_key = key
    if best_key:
        return target_values.get(best_key, '')
    for key, value in target_values.items():
        key_parts = key.split('.')
        if len(key_parts) <= len(norm_parts):
            continue
        if key_parts[:len(norm_parts)] == norm_parts:
            return value

    container_name = norm_parts[-1]
    nested: dict = {}
    for key, value in target_values.items():
        key_parts = key.split('.')
        if len(key_parts) > 1 and key_parts[0] == container_name:
            cursor = nested
            for part in key_parts[1:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[key_parts[-1]] = value
    if nested:
        return nested

    return ''


def _evaluate_xml_dialect(expression: str, source_fields: dict, target_xpath: str = ""):
    variables: dict = {}
    target_values: dict = {}
    global_vars = _get_global_variables()
    for line in expression.split('\n'):
        _exec_xml_statement(line, variables, target_values, source_fields, global_vars)
    result = _match_target_value(target_values, _normalize_target_path(target_xpath))
    if isinstance(result, dict):
        # A composite-container match (see _match_target_value case 3) —
        # pass the nested dict through untouched. _post_process only knows
        # how to truncate/format a string leaf value.
        return result
    return _post_process(result, target_xpath)


def _is_legacy_dialect(expression: str) -> bool:
    return bool(
        'source.field_' in expression
        or re.search(r'\bthen\b', expression)
        or re.search(r'^\s*endif\s*$', expression, re.MULTILINE)
    )


def evaluate_expression(expression: str, source_fields: dict, target_xpath: str = "") -> str:
    """
    Public entry point for evaluating a MappingElement.expression against
    the parsed source MT fields. Two unrelated pseudocode dialects exist in
    this system and are dispatched between here:

      - The XML-dataset dialect (default): ISO-path assignments like
        'CdtTrfTxInf.Amt.InstdAmt = decimal(MT.F32A.amount.replace(",","."))',
        as authored in backend/dataset/mappings/*.xml and surfaced through
        RAG (exact_rag_lookup) into MappingElement.expression by Generate
        Elements.
      - The legacy dialect: 'var = source.field_XX' with real
        if/then/else/endif blocks, produced by MappingElements a user
        typed by hand through the Mapping page's Edit form (see its
        placeholder text) — kept working unchanged for backward
        compatibility.
    """
    if not expression:
        return ''
    if _is_legacy_dialect(expression):
        return _evaluate_legacy_dialect(expression, source_fields, target_xpath)
    return _evaluate_xml_dialect(expression, source_fields, target_xpath)


def _expression_computed_anything(expression: str, source_fields: dict) -> bool:
    """True if this pseudocode block assigned a value to AT LEAST ONE ISO
    target path — even if not this specific element's own target_xpath.

    Distinguishes two very different reasons evaluate_expression() can come
    back empty for one particular target:
      1. The pseudocode's own conditional logic legitimately decided this
         target gets no value (e.g. :50K:'s "if(isIBAN(account)) ... IBAN =
         account / if(!isIBAN(account)) ... Othr.Id = account" sets exactly
         ONE of its two targets depending on the account format — the other
         is correctly meant to stay unset).
      2. This evaluator genuinely couldn't process the expression at all
         (unsupported syntax, wrong dialect guess, etc).
    Callers should only fall back to the raw source field value in case
    (2) — applying it in case (1) would incorrectly stomp a deliberate
    "leave this one empty" decision with the same raw value used for the
    OTHER (correctly-set) target. Legacy-dialect expressions already carry
    their own internal fallback-to-first-variable safety net (see
    _evaluate_legacy_dialect), so they're always reported as "computed
    something" here — this distinction only matters for the XML dialect's
    genuinely independent multi-target assignments."""
    if not expression:
        return False
    if _is_legacy_dialect(expression):
        return True
    variables: dict = {}
    target_values: dict = {}
    global_vars = _get_global_variables()
    for line in expression.split('\n'):
        _exec_xml_statement(line, variables, target_values, source_fields, global_vars)
    return bool(target_values)


def resolve_element_value(el, source_fields: dict) -> str:
    """
    Single shared implementation of the "what's the final value for this
    MappingElement" fallback chain, used by every transform endpoint
    (previously duplicated three times with a subtly different bug in each
    copy):
      1. evaluate_expression() against the element's own target_field.
      2. If that's empty AND the pseudocode didn't compute anything for ANY
         of this source field's targets (see _expression_computed_anything),
         fall back to the raw source field value — extracting the account
         out of a multiline field (SWIFT's "/account\\nName" convention) if
         present. Gated on _expression_computed_anything so this never
         overwrites a target the pseudocode deliberately left empty.
      3. el.default_value as the absolute last resort.
    """
    expression = el.expression or ''
    target_xpath = el.target_field or ''
    value = evaluate_expression(expression, source_fields, target_xpath)

    # A target_xpath using an XPath predicate (e.g. MT940/950's
    # "Bal[Tp/CdOrPrtry/Cd='OPBD']") can never come out of
    # _normalize_target_path as a clean dotted path in the first place —
    # splitting on '/' shreds the predicate into garbage segments like
    # "Cd='OPBD']", so _match_target_value has structurally NO WAY to ever
    # resolve it, no matter what the dialect computed for sibling targets.
    # For those, "computed something for a sibling target" is not a
    # meaningful signal — the intended mechanism for this field is the raw
    # fallback below, whose value later gets specially decoded by
    # build_xml_from_dict's Bal_OPBD/Bal_CLBD handling. Only trust
    # _expression_computed_anything's gating for cleanly resolvable paths.
    normalized_has_predicate = '[' in _normalize_target_path(target_xpath)

    # Both fallbacks below use the SAME raw source value (default_value is
    # just that raw value, pre-captured as MessageDescriptionElement.example_
    # value — see generate_mapping_elements) — so both must be gated the
    # same way: only when the pseudocode computed NOTHING at all for this
    # source field, never when it deliberately left this one specific
    # target empty while setting a sibling target instead (see
    # _expression_computed_anything's docstring).
    if not value and (normalized_has_predicate or not _expression_computed_anything(expression, source_fields)):
        if el.source_field:
            clean = el.source_field.lstrip(':').rstrip(':')
            raw_value = (
                source_fields.get(el.source_field) or
                source_fields.get(f':{clean}:') or
                source_fields.get(clean) or
                ''
            )
            if raw_value and "\n" in raw_value:
                value = extract_iban_from_field(raw_value)
            else:
                value = raw_value
        if not value and el.default_value:
            value = el.default_value

    return value


def _post_process(result_value, target_xpath: str = "") -> str:
    """Shared post-processing for whatever evaluate_expression() produced,
    regardless of which return path (normal scan or branch chain) hit."""
    if isinstance(result_value, list):
        result_value = result_value[0] if result_value else ''
    if result_value is not None:
        result_value = str(result_value)

    # XML->MT targets are bare MT-tag keys ("F32A", "F20", ...) — never
    # dotted XML paths, which is what every heuristic below assumes. A
    # computed value like "260610EUR8500," here IS the correct final SWIFT
    # field value, not a raw source leftover that needs reformatting —
    # skip straight past the MT->XML-oriented heuristics.
    if result_value and re.match(r'^F[A-Z0-9]+$', target_xpath or ''):
        return result_value

    if result_value:
        if re.match(r'^\d{6}[A-Z]{3}[\d,]+', result_value):
            is_amt = any(k in (target_xpath or '').lower() for k in ['amt', 'instdamt'])
            if is_amt:
                result_value = extract_amount_from_32a(result_value)
            else:
                yy = result_value[0:2]
                mm = result_value[2:4]
                dd = result_value[4:6]
                century = '21' if int(yy) >= 50 else '20'
                result_value = f'{century}{yy}-{mm}-{dd}'
        elif "\n" in result_value and result_value.strip().startswith('/'):
            result_value = extract_iban_from_field(result_value)
        elif "\n" in result_value:
            sub_lines = [l.strip() for l in result_value.split("\n") if l.strip()]
            if sub_lines:
                first = sub_lines[0]
                if first.startswith('/'):
                    result_value = first[1:].strip()
                else:
                    result_value = first

    if result_value and re.match(r'^[\d]+\.$', result_value):
        result_value = result_value + '00'
    elif result_value and re.match(r'^[\d]+\.[\d]$', result_value):
        result_value = result_value + '0'

    return result_value or ''


def _deep_merge_dict(dest: dict, src: dict) -> dict:
    """Recursively merge src into dest, combining nested dicts instead of
    one overwriting the other. Needed because composite elements like
    :61:'s Ntry can receive a nested dict from one MappingElement (the
    :61: mapping itself, via _match_target_value's container case) and
    individual leaf values from OTHERS (e.g. :86:'s
    Ntry/NtryDtls/TxDtls/RmtInf/Ustrd) — whichever is processed second
    must not wipe out what the first one already built."""
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(dest.get(key), dict):
            _deep_merge_dict(dest[key], val)
        else:
            dest[key] = val
    return dest


def _occurrence_of(source_field: str):
    """Splits a MappingElement.source_field like ':61_2:' into its base
    tag ('61') and 1-based occurrence index (2), or (tag, 0) for the bare
    first occurrence (':61:') / anything without a repeat suffix.
    swift_txt_parser._parse_tags is what originally assigns these index
    suffixes to repeated SWIFT tags (MT940/950's :61:/:86: statement
    lines being the case that matters here)."""
    tag = (source_field or '').strip(':')
    m = re.match(r'^(\d{2}[A-Z]?)_(\d+)$', tag)
    if m:
        return m.group(1), int(m.group(2))
    return tag, 0


def _shift_source_fields_for_occurrence(source_fields: dict, base_tag: str, index: int) -> dict:
    """Returns source_fields with every key variant of base_tag (e.g.
    '61') overridden to the value of its index-th repeated occurrence, so
    an expression that only ever says 'MT.F61' (the dataset only authors
    the pattern once) resolves to THAT occurrence's own value instead of
    always the first — without any change to the expression evaluator
    itself. index=0 is the bare tag already, so it's a no-op."""
    if index == 0:
        return source_fields
    suffixed = f'{base_tag}_{index}'
    val = (
        source_fields.get(suffixed) or source_fields.get(f':{suffixed}:') or
        source_fields.get(suffixed.upper()) or source_fields.get(f':{suffixed.upper()}:')
    )
    if val is None:
        return source_fields
    shifted = dict(source_fields)
    for variant in (
        base_tag, base_tag.upper(), base_tag.lower(),
        f':{base_tag}:', f':{base_tag.upper()}:', f':{base_tag.lower()}:',
        f'field_{base_tag.lower()}', f'field_{base_tag.upper()}',
    ):
        shifted[variant] = val
    return shifted


def set_xpath_value(root_dict: dict, xpath: str, value):
    """Set a value in a nested dict using xpath-like path. `value` is
    usually a string leaf, but can be a nested dict (see
    _match_target_value's composite-container case) — in that case it's
    merged into whatever's already at that position rather than replacing
    it outright."""
    if not xpath or not value:
        return

    # Handle XPath predicates like Bal[Tp/CdOrPrtry/Cd='OPBD']
    # Convert to safe key: Bal_OPBD or Bal_CLBD
    import re as _re
    xpath_clean = xpath
    pred_match = _re.search(r"(\w+)\[.*?Cd='([^']+)'\]", xpath)
    if pred_match:
        elem_name = pred_match.group(1)
        code = pred_match.group(2)
        xpath_clean = xpath[:xpath.index(elem_name)] + f"{elem_name}_{code}" + xpath[xpath.index(']')+1:]

    # Clean xpath: /Document/BkToCstmrStmt/GrpHdr/MsgId -> GrpHdr/MsgId
    parts = [p for p in xpath_clean.replace('/Document/', '').split('/') if p]

    # Remove the root element
    root_elements = ('BkToCstmrDbtCdtNtfctn', 'FIToFICstmrCdtTrf',
                     'FICdtTrf', 'BkToCstmrStmt')
    if parts and parts[0] in root_elements:
        parts = parts[1:]

    if not parts:
        return

    current = root_dict
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        if isinstance(current[part], str):
            current[part] = {'_value': current[part]}
        current = current[part]

    last = parts[-1]
    if isinstance(value, dict) and isinstance(current.get(last), dict):
        _deep_merge_dict(current[last], value)
    else:
        current[last] = value


def build_xml_from_dict(data: dict, namespace: str, root_tag: str, iso_target: str) -> str:
    """Build ISO 20022 XML from a flat/nested dict."""
    ET.register_namespace('', namespace)
    doc = ET.Element(f"{{{namespace}}}Document")
    msg = ET.SubElement(doc, f"{{{namespace}}}{root_tag}")

    def add_elements(parent, data_dict, ns):
        for key, value in data_dict.items():
            # Handle balance types: Bal_OPBD, Bal_CLBD, Bal_CLAV, Bal_FWAV, ...
            # → proper camt.053 <Bal> structure. The code is whatever
            # follows "Bal_" in the key (set by set_xpath_value's predicate
            # rewrite of Bal[Tp/CdOrPrtry/Cd='XXXX']) rather than a
            # hardcoded pair — otherwise any balance type beyond
            # OPBD/CLBD (e.g. :64:'s CLAV, :65:'s FWAV) falls through to
            # the generic branch below and gets emitted as a literal
            # <Bal_CLAV> tag instead of a real nested <Bal> element.
            if key.startswith('Bal_'):
                code = key[len('Bal_'):]
                raw_val = str(value) if value is not None else ''
                _build_balance_element(parent, ns, code, raw_val)
                continue

            # Skip internal keys
            if key.startswith('_'):
                continue

            # Sanitize key - remove invalid XML chars
            safe_key = re.sub(r'[^a-zA-Z0-9_\-.]', '_', key)
            if not safe_key or safe_key[0].isdigit():
                safe_key = '_' + safe_key

            # A repeating group (e.g. MT940/950's :61:/:86: statement
            # lines, one <Ntry> per transaction — see the repeat-group
            # handling in transform_with_mapping) arrives here as a LIST
            # of per-entry dicts rather than one dict. Emit one sibling
            # element per item instead of collapsing them into one, or
            # every entry after the first would silently disappear.
            if isinstance(value, list):
                for item in value:
                    elem = ET.SubElement(parent, f"{{{ns}}}{safe_key}")
                    if isinstance(item, dict):
                        add_elements(elem, item, ns)
                    else:
                        elem.text = str(item) if item is not None else ''
                continue

            elem = ET.SubElement(parent, f"{{{ns}}}{safe_key}")
            if isinstance(value, dict):
                add_elements(elem, value, ns)
            else:
                elem.text = str(value) if value is not None else ''

    def _build_balance_element(parent, ns, code, raw_val):
        """Build proper camt.053 Bal element from SWIFT balance string like C260429EUR25000,"""
        bal = ET.SubElement(parent, f"{{{ns}}}Bal")
        tp = ET.SubElement(bal, f"{{{ns}}}Tp")
        cd_or_prtry = ET.SubElement(tp, f"{{{ns}}}CdOrPrtry")
        ET.SubElement(cd_or_prtry, f"{{{ns}}}Cd").text = code

        if raw_val and len(raw_val) >= 11:
            dc = raw_val[0]
            date_str = raw_val[1:7]
            ccy = raw_val[7:10]
            amt_str = raw_val[10:].replace(',', '.').rstrip('.')

            # Format date YYMMDD → YYYY-MM-DD
            try:
                yy = int(date_str[0:2])
                mm = date_str[2:4]
                dd = date_str[4:6]
                century = '21' if yy >= 50 else '20'
                iso_date = f"{century}{yy:02d}-{mm}-{dd}"
            except Exception:
                iso_date = '2026-01-01'

            # Amount
            amt_elem = ET.SubElement(bal, f"{{{ns}}}Amt")
            amt_elem.text = amt_str if amt_str else '0'
            amt_elem.set('Ccy', ccy)

            # CdtDbtInd
            ET.SubElement(bal, f"{{{ns}}}CdtDbtInd").text = 'CRDT' if dc == 'C' else 'DBIT'

            # Date
            dt = ET.SubElement(bal, f"{{{ns}}}Dt")
            ET.SubElement(dt, f"{{{ns}}}Dt").text = iso_date

    add_elements(msg, data, namespace)

    # Prettify
    xml_str = ET.tostring(doc, encoding='unicode')
    try:
        reparsed = minidom.parseString(xml_str.encode('utf-8'))
        pretty = reparsed.toprettyxml(indent="  ")
        lines = [l for l in pretty.split('\n') if l.strip()]
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        return f'<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)
    except Exception:
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'


async def _transform_xml_to_mt_with_mapping(mapping, elements, content_str: str, db: Session, current_user: User, upload_filename: str):
    """
    XML -> MT counterpart to transform_with_mapping's MT -> XML path below —
    same MappingElement-driven design (Generate Elements' accepted-formula
    and RAG-fallback pseudocode both work here unchanged), just producing
    flat MT field lines instead of a nested XML tree. Reuses mt_generator's
    existing field-ordering/envelope-restore machinery for the final
    assembly rather than reimplementing it — that part has nothing
    direction-specific about it.

    Also runs the SAME compliance checks (duplicate/sanctions/large-amount/
    multi-level-approval) as the MT->XML direction — these were originally
    wired up only there, which meant an XML source file converted back to
    MT text skipped all of them entirely. mapping.target (not
    mapping.source) is the actual MT type being produced here, so that's
    what gets passed to each check.

    Takes the already-decoded file content rather than an UploadFile:
    transform_with_mapping reads the upload once at the top (to run the
    pre-transform validation gate against it), and UploadFile's stream
    can't be read twice.
    """
    import tempfile, os, re as _re, json as _json
    from app.services.mt_generator import mt_generator

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as tmp:
        tmp.write(content_str)
        tmp_path = tmp.name

    try:
        xml_source_fields = extract_xml_source_fields(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not xml_source_fields:
        raise HTTPException(status_code=400, detail="No fields could be extracted from the XML file.")

    mt_fields: dict = {}
    mapped_count = 0
    skipped_count = 0
    for el in elements:
        if not el.target_field or not el.target_field.startswith('F'):
            skipped_count += 1
            continue
        value = resolve_element_value(el, xml_source_fields)
        if value:
            tag = f":{el.target_field[1:]}:"
            mt_fields[tag] = value
            mapped_count += 1
        else:
            skipped_count += 1

    if not mt_fields:
        raise HTTPException(status_code=400,
            detail="No values could be extracted from the XML using this mapping's elements.")

    logger.info(f"XML->MT via mapping {mapping.id}: {mapped_count} mapped, {skipped_count} skipped")

    mt_type = mapping.target.upper()
    # Same bare-tag convention extract_source_fields uses on the other
    # direction (e.g. source_fields['20'], not source_fields[':20:']) —
    # every check function keys off that convention.
    mt_source_fields = {tag.strip(':'): value for tag, value in mt_fields.items()}

    _check_duplicate_reference(db, current_user, mt_type, mt_source_fields, upload_filename)
    pep_hit = _check_sanctions_and_pep(db, current_user, mt_type, mt_source_fields, upload_filename)

    envelope = {}
    envelope_match = _re.search(r'SWIFT_ENVELOPE:({[^}]+(?:}[^}]*)*})', content_str, _re.DOTALL)
    if envelope_match:
        try:
            envelope = _json.loads(envelope_match.group(1))
        except Exception:
            pass

    mt_text = mt_generator.generate(mt_fields, mapping.target, envelope=envelope)

    filename = f"{mapping.target}_{mapping.source.replace('.', '_')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.txt"
    from app.config import settings as _settings
    output_dir = Path(_settings.UPLOAD_DIR).parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / filename, 'w', encoding='utf-8') as f:
        f.write(mt_text)

    _check_large_amount_flag(db, current_user, mt_type, mt_source_fields, upload_filename)
    _record_processed_transaction(db, current_user, mt_type, mt_source_fields, upload_filename)

    required_approvals = _required_approvals_for_amount(db, mt_type, mt_source_fields)
    if required_approvals:
        from app.models.pending_transaction import PendingTransactionApproval
        from app.models.notification import Notification as _Notification
        from app.models.user import User as _User
        from app.services.audit_service import log_action

        parsed_amount = _extract_32a_amount(mt_source_fields)
        amount_str, currency_str = (f"{parsed_amount[0]:,.2f}", parsed_amount[1]) if parsed_amount else (None, None)
        reference = (mt_source_fields.get('20') or '').strip() or None

        txn = PendingTransactionApproval(
            mapping_id=mapping.id, mt_type=mt_type, reference=reference,
            amount=amount_str, currency=currency_str, output_filename=filename,
            required_approvals=required_approvals, status="pending", submitted_by=current_user.id,
        )
        db.add(txn)
        log_action(
            db, current_user, action="hold_for_approval", entity_type="PendingTransactionApproval",
            details=f"Held \"{filename}\" ({amount_str} {currency_str}) — needs {required_approvals} approval(s)"
        )
        for admin in db.query(_User).filter(_User.is_admin.is_(True), _User.id != current_user.id).all():
            db.add(_Notification(
                user_id=admin.id,
                message=f"🔒 {current_user.username}'s transform of \"{upload_filename}\" ({amount_str} {currency_str}) needs {required_approvals} approval(s) before release.",
                link="/pending-transactions"
            ))
        db.commit()
        db.refresh(txn)
        return JSONResponse(status_code=202, content={
            "held_for_approval": True,
            "transaction_id": txn.id,
            "required_approvals": required_approvals,
            "message": f"This transaction ({amount_str} {currency_str}) exceeds the approval threshold and requires {required_approvals} admin approval(s) before the file is released. Check Pending Transactions for status."
        })

    elif pep_hit:
        from app.models.pending_transaction import PendingTransactionApproval
        from app.models.notification import Notification as _Notification
        from app.models.user import User as _User
        from app.services.audit_service import log_action

        parsed_amount = _extract_32a_amount(mt_source_fields)
        amount_str, currency_str = (f"{parsed_amount[0]:,.2f}", parsed_amount[1]) if parsed_amount else (None, None)
        reference = (mt_source_fields.get('20') or '').strip() or None
        reason = f"PEP match: {pep_hit['role']} \"{pep_hit['name']}\" (watchlist entry \"{pep_hit['matched']}\")"

        txn = PendingTransactionApproval(
            mapping_id=mapping.id, mt_type=mt_type, reference=reference,
            amount=amount_str, currency=currency_str, output_filename=filename,
            required_approvals=1, approver_role="compliance_officer", pending_reason=reason,
            status="pending", submitted_by=current_user.id,
        )
        db.add(txn)
        log_action(
            db, current_user, action="pep_hold", entity_type="PendingTransactionApproval",
            details=f"Held \"{filename}\" for compliance review — {reason}"
        )
        for officer in db.query(_User).filter(_User.is_compliance_officer.is_(True), _User.id != current_user.id).all():
            db.add(_Notification(
                user_id=officer.id,
                message=f"⚠️ PEP match: {current_user.username}'s transform of \"{upload_filename}\" — {pep_hit['role']} \"{pep_hit['name']}\" needs compliance review before release.",
                link="/pending-transactions"
            ))
        db.commit()
        db.refresh(txn)
        return JSONResponse(status_code=202, content={
            "held_for_approval": True,
            "transaction_id": txn.id,
            "required_approvals": 1,
            "message": f"{reason}. This requires enhanced due diligence review by a compliance officer before the file is released. Check Pending Transactions for status."
        })

    # "Validate Generated Output (Optional)" — informational only, never
    # blocks returning the file the transform already successfully
    # produced.
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    output_check = _validate_output_optional(mt_text, filename, db)
    if output_check is not None:
        headers['X-Output-Validation'] = _json.dumps(output_check)

    return Response(
        content=mt_text,
        media_type='text/plain',
        headers=headers
    )


def _detect_upload_type(tmp_path: str, filename: str) -> dict:
    """Run the same file-type/message-type detection FileProcessor already
    does on upload, standalone — used by the transform precheck pipeline to
    know what it's dealing with before any of the gates below can run."""
    from app.services.file_processor import FileProcessor
    file_info = FileProcessor.process_file(str(tmp_path))
    file_type = file_info.get("file_type")
    mt_info = file_info.get("mt_info") or {}
    mt_type = mt_info.get("mt_type")
    return {"file_type": file_type, "mt_type": mt_type}


def _run_transform_prechecks(content_str: str, filename: str, db: Session, current_user: User) -> None:
    """
    Full prerequisite pipeline for Transform, in order — mirrors the
    intended platform workflow: Message Description exists (and is
    approved) -> Validation Rules exist -> uploaded file passes validation.
    (Mapping Elements existing is checked separately by the caller, since
    that's a property of the MAPPING, not of this uploaded file.) Each
    stage is a hard block, same strictness tier as "Generate MD before
    Generate Elements" elsewhere in this app — nothing here is skippable
    just because a later stage would also have caught the problem.

    A failed validation (Gate 3) still blocks the transform immediately,
    same as before, but now also persists a PendingValidationCorrection
    row — otherwise the errors only ever existed in a toast the user
    dismissed, with no record left that a correction was still owed. A
    later SUCCESSFUL transform of the same mt_type/file_type by the same
    user auto-resolves any of their still-pending rows, on the theory
    that a corrected file passing validation IS the correction.
    """
    import tempfile, os
    from app.models.message_description import MessageDescription
    from app.api.routes.validation_routes import validate_file_at_path

    with tempfile.NamedTemporaryFile(mode='w', suffix=Path(filename).suffix or '.tmp',
                                      delete=False, encoding='utf-8') as tmp:
        tmp.write(content_str)
        tmp_path = tmp.name

    try:
        detected = _detect_upload_type(tmp_path, filename)
        mt_type = detected["mt_type"]
        file_type = detected["file_type"]

        # ── Gate 1: an APPROVED Message Description exists for this type ──
        # Deliberately requires approved=True, not just "one exists" —
        # that's the whole point of the Message Description page's
        # Approve/Reject step: an unreviewed, unapproved MD shouldn't be
        # trusted as the basis for validation rules or transforms.
        if mt_type:
            approved_md = db.query(MessageDescription).filter(
                MessageDescription.mt_type == mt_type,
                MessageDescription.file_type == file_type,
                MessageDescription.approved == True  # noqa: E712
            ).first()
            if not approved_md:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No approved Message Description found for {mt_type} ({file_type}). "
                        f"Upload a sample file of this type on the Message Description page, "
                        f"click Generate MD, and Approve it before transforming files of this type."
                    )
                )

        # ── Gates 2 + 3: validation rules exist, and this file passes them ──
        # validate_file_at_path() itself raises if no rules exist at all
        # for the detected type (Gate 2) — reusing it here means there is
        # exactly one implementation of "what does validating a file mean"
        # in this codebase, not a second copy that can drift from
        # /validate's behavior.
        result = validate_file_at_path(tmp_path, filename, db)
    finally:
        os.unlink(tmp_path)

    if not result.get('is_valid'):
        errors = result.get('errors') or []
        warnings = result.get('warnings') or []
        summary = '; '.join(
            f"{e.get('field')}: {', '.join(e.get('errors') or [])}" for e in errors[:5]
        )
        from app.models.pending_validation_correction import PendingValidationCorrection
        db.add(PendingValidationCorrection(
            mt_type=result.get('mt_type') or 'UNKNOWN',
            file_type=result.get('file_type') or 'UNKNOWN',
            original_filename=filename,
            errors=errors,
            warnings=warnings,
            failed_count=result.get('summary', {}).get('failed', len(errors)),
            status='pending',
            submitted_by=current_user.id,
        ))
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=(
                f"File failed validation against the {result.get('mt_type')} reference standard "
                f"({result.get('summary', {}).get('failed', len(errors))} field(s) failed) — "
                f"correct the file before transforming it. {summary}. Check Pending Transactions for a record of this correction."
            )
        )

    # Validation passed — a corrected file passing IS the correction, so
    # auto-resolve any of this user's still-pending rows for the same
    # mt_type/file_type rather than leaving them stuck at "pending" forever.
    from app.models.pending_validation_correction import PendingValidationCorrection
    from datetime import datetime as _datetime
    db.query(PendingValidationCorrection).filter(
        PendingValidationCorrection.submitted_by == current_user.id,
        PendingValidationCorrection.mt_type == result.get('mt_type'),
        PendingValidationCorrection.file_type == result.get('file_type'),
        PendingValidationCorrection.status == 'pending'
    ).update({'status': 'resolved', 'resolved_at': _datetime.utcnow()})
    db.commit()


def _validate_output_optional(content_str: str, filename: str, db: Session) -> Optional[dict]:
    """
    Non-blocking validation of the GENERATED output file — the "Validate
    Generated Output (Optional)" step. Unlike _run_transform_prechecks,
    this never raises: no rules for the output's type just means nothing
    to report, and a failure is informational only (the file was already
    produced and is still returned to the user). Returns None when there's
    nothing to report, otherwise a compact summary suitable for a response
    header.
    """
    import tempfile, os
    from app.api.routes.validation_routes import validate_file_at_path

    with tempfile.NamedTemporaryFile(mode='w', suffix=Path(filename).suffix or '.tmp',
                                      delete=False, encoding='utf-8') as tmp:
        tmp.write(content_str)
        tmp_path = tmp.name
    try:
        result = validate_file_at_path(tmp_path, filename, db)
    except HTTPException:
        return None
    except Exception:
        return None
    finally:
        os.unlink(tmp_path)

    return {
        "is_valid": result.get("is_valid"),
        "failed": result.get("summary", {}).get("failed", 0),
        "warnings": result.get("summary", {}).get("warnings", 0),
        "total_rules": result.get("summary", {}).get("total_rules", 0),
    }


@router.post("/mapping/{mapping_id}")
async def transform_with_mapping(
    mapping_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transform a SWIFT MT file using a Mapping and its MappingElements.
    Returns the generated ISO 20022 XML file.
    """
    # Get the Mapping
    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")

    # A draft/inactive mapping hasn't been reviewed and approved by an
    # admin yet (see the maker-checker gate in mappings.py's update_mapping)
    # — using it for a real Transform would mean production data flowing
    # through formulas nobody has actually signed off on.
    if mapping.status != MappingStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This mapping is not active yet (status: {mapping.status.value}) — "
                   f"an administrator must approve it before it can be used for Transform."
        )

    # Read the upload once — every gate below and whichever direction
    # branch runs afterward all need the content, and UploadFile's stream
    # can only be read once.
    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except Exception:
        content_str = content.decode('latin-1')

    # Gates, in workflow order: Message Description exists+approved ->
    # Validation Rules exist -> file passes validation -> (below) Mapping
    # Elements exist. Each is a hard block on its own, not just a
    # best-effort check — see _run_transform_prechecks's docstring.
    _run_transform_prechecks(content_str, file.filename, db, current_user)

    # Get MappingElements — the "Mapping Formula exists" gate, checked
    # last per the intended workflow order since it's a property of the
    # MAPPING rather than of this specific uploaded file.
    elements = db.query(MappingElement).filter(
        MappingElement.mapping_id == mapping_id,
        MappingElement.status == 'mapped'
    ).all()

    if not elements:
        raise HTTPException(status_code=400, detail="No mapped elements found. Please Generate Elements first.")

    is_iso_to_mt = not mapping.source.upper().startswith('MT')

    if is_iso_to_mt:
        return await _transform_xml_to_mt_with_mapping(mapping, elements, content_str, db, current_user, file.filename)

    # Save file temporarily then parse
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
        tmp.write(content_str)
        tmp_path = tmp.name

    try:
        parser = SwiftTxtParser()
        parsed = parser.parse(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not parsed:
        raise HTTPException(status_code=400, detail="Failed to parse SWIFT MT file")

    mt_blocks = parsed.get('mt_blocks') or {}
    source_fields = extract_source_fields(mt_blocks)

    logger.info(f"Parsed SWIFT file: {len(source_fields)} source fields")

    # Duplicate detection, then sanctions/PEP screening — both checked
    # before any mapping work so a blocked transaction doesn't waste
    # effort building XML that will never be returned.
    _check_duplicate_reference(db, current_user, mapping.source.upper(), source_fields, file.filename)
    pep_hit = _check_sanctions_and_pep(db, current_user, mapping.source.upper(), source_fields, file.filename)

    # Build target data dict by evaluating each MappingElement expression
    target_data = {}
    mapped_count = 0
    skipped_count = 0

    # Repeating groups — MT940/950's :61:/:86: statement lines, one pair
    # per transaction (see swift_txt_parser._parse_tags's index-suffix
    # handling and mappings.py's generate_mapping_elements repeat-tag
    # fallback, which copies the base tag's target_field onto every
    # suffixed occurrence). Any element whose source_field carries a
    # numeric suffix (":61_2:") marks its target_field as belonging to a
    # repeating container — every element sharing that target_field
    # (including the un-suffixed first occurrence) needs to be evaluated
    # PER OCCURRENCE into a list, or occurrence 2+ would just overwrite
    # occurrence 1 in a single shared dict.
    repeat_target_fields = set()
    for el in elements:
        if not el.target_field or not el.source_field:
            continue
        _, idx = _occurrence_of(el.source_field)
        if idx > 0:
            repeat_target_fields.add(el.target_field)

    repeat_elements = [el for el in elements if el.target_field in repeat_target_fields]
    onetime_elements = [el for el in elements if el.target_field not in repeat_target_fields]

    for el in onetime_elements:
        if not el.target_field:
            skipped_count += 1
            continue

        value = resolve_element_value(el, source_fields)

        if value:
            set_xpath_value(target_data, el.target_field, value)
            mapped_count += 1
        else:
            skipped_count += 1

    if repeat_elements:
        entries_by_index: dict = {}
        for el in repeat_elements:
            base_tag, idx = _occurrence_of(el.source_field)
            shifted_fields = _shift_source_fields_for_occurrence(source_fields, base_tag, idx)
            value = resolve_element_value(el, shifted_fields)
            if not value:
                continue
            entry = entries_by_index.setdefault(idx, {})
            # Same set_xpath_value used for every other element — just
            # accumulating into this occurrence's own dict instead of the
            # shared target_data, so :61:'s and :86:'s contributions for
            # the SAME transaction line merge together correctly.
            set_xpath_value(entry, el.target_field, value)
            mapped_count += 1

        if entries_by_index:
            ntry_list = []
            for i in sorted(entries_by_index.keys()):
                entry = entries_by_index[i]
                # Every repeat_elements target_field nests under Stmt/Ntry
                # — the only repeating group this dataset authors formulas
                # for — so drill down to the actual per-entry sub-dict
                # rather than the container shape the loop above builds.
                ntry_list.append(entry.get('Stmt', {}).get('Ntry', entry))
            target_data.setdefault('Stmt', {})['Ntry'] = ntry_list

    logger.info(f"Transform result: {mapped_count} mapped, {skipped_count} skipped")

    if not target_data:
        raise HTTPException(status_code=400,
            detail="No values could be extracted. Check source file format and mapping expressions.")

    # Add mandatory ISO 20022 fields if missing
    if 'GrpHdr' not in target_data:
        target_data['GrpHdr'] = {}
    if 'MsgId' not in target_data.get('GrpHdr', {}):
        target_data.setdefault('GrpHdr', {})['MsgId'] = f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    if 'CreDtTm' not in target_data.get('GrpHdr', {}):
        target_data.setdefault('GrpHdr', {})['CreDtTm'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    # NbOfTxs/CtrlSum are mandatory GrpHdr fields in every ISO 20022 message
    # this project targets (pacs.008/009, camt.053/054) — /transform/auto
    # already guarantees them; this endpoint was missing them entirely,
    # producing an incomplete GrpHdr for the exact same mapping depending
    # on which of the two transform routes the UI happened to call.
    target_data.setdefault('GrpHdr', {}).setdefault('NbOfTxs', '1')
    _ctrl_sum = (
        target_data.get('CdtTrfTxInf', {}).get('Amt', {}).get('InstdAmt', '') or
        target_data.get('PmtInf', {}).get('Amt', '') or
        '0'
    )
    if isinstance(_ctrl_sum, dict):
        _ctrl_sum = '0'
    target_data.setdefault('GrpHdr', {}).setdefault('CtrlSum', str(_ctrl_sum))

    # Reorder: GrpHdr must come first in ISO 20022
    ordered_data = {}
    if 'GrpHdr' in target_data:
        ordered_data['GrpHdr'] = target_data.pop('GrpHdr')
    ordered_data.update(target_data)
    target_data = ordered_data

    _check_large_amount_flag(db, current_user, mapping.source.upper(), source_fields, file.filename)

    # Get ISO namespace and root element
    iso_target = mapping.target
    namespace = ISO_NAMESPACES.get(iso_target, ISO_NAMESPACES['camt.054.001.08'])
    root_tag = ISO_ROOT_ELEMENTS.get(iso_target, 'BkToCstmrDbtCdtNtfctn')

    # Generate XML
    xml_content = build_xml_from_dict(target_data, namespace, root_tag, iso_target)

    # Store SWIFT envelope in XML comment for round-trip restore
    import json as _json
    def _get_sf(block, key):
        sf = block.get('sub_fields', {})
        val = sf.get(key, '')
        return val.get('value', '') if isinstance(val, dict) else str(val)

    b1 = mt_blocks.get('block1', {})
    b2 = mt_blocks.get('block2', {})
    b3 = mt_blocks.get('block3', {})
    b5 = mt_blocks.get('block5', {})
    envelope = _json.dumps({
        'block1': _get_sf(b1,'ApplicationIdentifier') + _get_sf(b1,'ServiceIdentifier') + _get_sf(b1,'LogicalTerminalAddress') + _get_sf(b1,'SessionNumber') + _get_sf(b1,'SequenceNumber'),
        'block2_dest': _get_sf(b2,'DestinationAddress'),
        'block2_priority': _get_sf(b2,'Priority'),
        # Several MT types share one ISO target (MT900/MT910 -> camt.054,
        # MT940/MT950 -> camt.053) — preserve the real source type here so
        # a later ISO->MT conversion doesn't have to guess it purely from
        # the ISO namespace.
        'block2_msgtype': mapping.source,
        'block3_108': _get_sf(b3,'108'),
        'block5_chk': _get_sf(b5,'CHK') or '000000000000'
    })
    xml_content = xml_content.replace(
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- SWIFT_ENVELOPE:{envelope} -->'
    )

    # Save to outputs directory
    filename = f"{mapping.source}_to_{iso_target.replace('.','_')}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xml"
    from app.config import settings
    output_dir = Path(settings.UPLOAD_DIR).parent / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    logger.info(f"✅ Saved output: {filename}")

    # Record this reference now that the transform has actually
    # succeeded — see _record_processed_transaction's docstring for why
    # this isn't done earlier, alongside the duplicate check itself.
    _record_processed_transaction(db, current_user, mapping.source.upper(), source_fields, file.filename)

    # Multi-level approval by threshold — the output already exists on
    # disk at this point, but a high-value transaction doesn't get
    # RELEASED (returned to the browser) until enough different admins
    # approve it. Below LARGE_AMOUNT_THRESHOLD this is skipped entirely
    # and behaves exactly as before.
    required_approvals = _required_approvals_for_amount(db, mapping.source.upper(), source_fields)
    if required_approvals:
        from app.models.pending_transaction import PendingTransactionApproval
        from app.models.notification import Notification
        from app.services.audit_service import log_action
        parsed_amount = _extract_32a_amount(source_fields)
        amount_str, currency_str = (f"{parsed_amount[0]:,.2f}", parsed_amount[1]) if parsed_amount else (None, None)
        reference = (source_fields.get('20') or '').strip() or None

        txn = PendingTransactionApproval(
            mapping_id=mapping.id, mt_type=mapping.source.upper(), reference=reference,
            amount=amount_str, currency=currency_str, output_filename=filename,
            required_approvals=required_approvals, status="pending", submitted_by=current_user.id,
        )
        db.add(txn)
        log_action(
            db, current_user, action="hold_for_approval", entity_type="PendingTransactionApproval",
            details=f"Held \"{filename}\" ({amount_str} {currency_str}) — needs {required_approvals} approval(s)"
        )
        for admin in db.query(User).filter(User.is_admin.is_(True), User.id != current_user.id).all():
            db.add(Notification(
                user_id=admin.id,
                message=f"🔒 {current_user.username}'s transform of \"{file.filename}\" ({amount_str} {currency_str}) needs {required_approvals} approval(s) before release.",
                link="/pending-transactions"
            ))
        db.commit()
        db.refresh(txn)
        return JSONResponse(status_code=202, content={
            "held_for_approval": True,
            "transaction_id": txn.id,
            "required_approvals": required_approvals,
            "message": f"This transaction ({amount_str} {currency_str}) exceeds the approval threshold and requires {required_approvals} admin approval(s) before the file is released. Check Pending Transactions for status."
        })
    elif pep_hit:
        from app.models.pending_transaction import PendingTransactionApproval
        from app.models.notification import Notification
        from app.models.user import User as _User
        from app.services.audit_service import log_action
        parsed_amount = _extract_32a_amount(source_fields)
        amount_str, currency_str = (f"{parsed_amount[0]:,.2f}", parsed_amount[1]) if parsed_amount else (None, None)
        reference = (source_fields.get('20') or '').strip() or None
        reason = f"PEP match: {pep_hit['role']} \"{pep_hit['name']}\" (watchlist entry \"{pep_hit['matched']}\")"

        txn = PendingTransactionApproval(
            mapping_id=mapping.id, mt_type=mapping.source.upper(), reference=reference,
            amount=amount_str, currency=currency_str, output_filename=filename,
            required_approvals=1, approver_role="compliance_officer", pending_reason=reason,
            status="pending", submitted_by=current_user.id,
        )
        db.add(txn)
        log_action(
            db, current_user, action="pep_hold", entity_type="PendingTransactionApproval",
            details=f"Held \"{filename}\" for compliance review — {reason}"
        )
        for officer in db.query(_User).filter(_User.is_compliance_officer.is_(True), _User.id != current_user.id).all():
            db.add(Notification(
                user_id=officer.id,
                message=f"⚠️ PEP match: {current_user.username}'s transform of \"{file.filename}\" — {pep_hit['role']} \"{pep_hit['name']}\" needs compliance review before release.",
                link="/pending-transactions"
            ))
        db.commit()
        db.refresh(txn)
        return JSONResponse(status_code=202, content={
            "held_for_approval": True,
            "transaction_id": txn.id,
            "required_approvals": 1,
            "message": f"{reason}. This requires enhanced due diligence review by a compliance officer before the file is released. Check Pending Transactions for status."
        })

    # "Validate Generated Output (Optional)" — informational only, never
    # blocks returning the file the transform already successfully
    # produced.
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    output_check = _validate_output_optional(xml_content, filename, db)
    if output_check is not None:
        headers['X-Output-Validation'] = _json.dumps(output_check)

    return Response(
        content=xml_content,
        media_type='application/xml',
        headers=headers
    )


@router.get("/mapping/{mapping_id}/preview")
async def preview_transform(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Preview what the transform will produce — shows mapping elements and expected output."""
    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")

    elements = db.query(MappingElement).filter(
        MappingElement.mapping_id == mapping_id
    ).all()

    return {
        "mapping_id": mapping.id,
        "name": mapping.name,
        "source": mapping.source,
        "target": mapping.target,
        "total_elements": len(elements),
        "mapped_elements": len([e for e in elements if e.status == 'mapped']),
        "pending_elements": len([e for e in elements if e.status == 'pending']),
        "elements": [
            {
                "source_field": e.source_field,
                "target_field": e.target_field,
                "has_expression": bool(e.expression),
                "status": e.status
            }
            for e in elements
        ]
    }