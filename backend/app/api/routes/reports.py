import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin_or_compliance
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.pending_transaction import PendingTransactionApproval
from app.models.user import User

router = APIRouter()

# Every audit action a regulator/compliance auditor would actually care
# about, bucketed into the categories a report like this groups by. Not
# every AuditLog action belongs here — routine CRUD (create/update/delete
# on Message Descriptions, Mappings, ...) is operational history, not a
# regulatory control event.
#
# 'approve_transaction'/'reject_transaction' are deliberately absent here:
# pending_transactions.py logs that same action name for BOTH large-amount
# holds and PEP holds (approver_role is what actually distinguishes them,
# not the action string), so a static action->category map would put every
# PEP-hold approval under "Large-Amount Approval". _categorize looks up
# each row's approver_role instead — see _approver_role_lookup.
REGULATORY_CATEGORIES = {
    'sanctions_block': 'Sanctions & PEP Screening',
    'aml_flag': 'Sanctions & PEP Screening',
    'pep_hold': 'Sanctions & PEP Screening',
    'pep_flag': 'Sanctions & PEP Screening',
    'hold_for_approval': 'Large-Amount Approval',
    'duplicate_block': 'Duplicate Detection',
    'propose_add': 'Watchlist Governance',
    'approve_add': 'Watchlist Governance',
    'reject_add': 'Watchlist Governance',
    'propose_remove': 'Watchlist Governance',
    'approve_remove': 'Watchlist Governance',
    'reject_remove': 'Watchlist Governance',
    'request_access': 'Access Control',
    'grant_access': 'Access Control',
    'deny_access': 'Access Control',
}

# The two role-ambiguous actions, handled separately by _categorize.
_ROLE_AMBIGUOUS_ACTIONS = ('approve_transaction', 'reject_transaction')
ALL_REGULATORY_ACTIONS = list(REGULATORY_CATEGORIES.keys()) + list(_ROLE_AMBIGUOUS_ACTIONS)
ALL_CATEGORIES = sorted(set(REGULATORY_CATEGORIES.values()))

# Which action strings could possibly resolve to a given category — used
# to narrow the SQL query when a single category is requested. The two
# role-ambiguous actions have to be included for BOTH categories they can
# resolve to, since the action string alone doesn't say which; the real
# filtering for those happens after _categorize runs (see _fetch_events).
_CATEGORY_CANDIDATE_ACTIONS = {}
for _action, _cat in REGULATORY_CATEGORIES.items():
    _CATEGORY_CANDIDATE_ACTIONS.setdefault(_cat, []).append(_action)
for _cat in ('Sanctions & PEP Screening', 'Large-Amount Approval'):
    _CATEGORY_CANDIDATE_ACTIONS.setdefault(_cat, []).extend(_ROLE_AMBIGUOUS_ACTIONS)


def _regulatory_rows(db: Session, start_dt: Optional[datetime], end_dt: Optional[datetime], category: Optional[str]):
    actions = _CATEGORY_CANDIDATE_ACTIONS.get(category, ALL_REGULATORY_ACTIONS) if category else ALL_REGULATORY_ACTIONS
    query = db.query(AuditLog).filter(AuditLog.action.in_(actions))
    if start_dt:
        query = query.filter(AuditLog.created_at >= start_dt)
    if end_dt:
        query = query.filter(AuditLog.created_at <= end_dt)
    return query


def _approver_role_lookup(db: Session, rows) -> dict:
    """entity_id -> approver_role for every PendingTransactionApproval
    referenced by a role-ambiguous row, so _categorize can tell a PEP-hold
    approval apart from a large-amount-hold approval sharing the same
    action string."""
    ids = {r.entity_id for r in rows if r.action in _ROLE_AMBIGUOUS_ACTIONS and r.entity_id is not None}
    if not ids:
        return {}
    txns = db.query(PendingTransactionApproval.id, PendingTransactionApproval.approver_role).filter(
        PendingTransactionApproval.id.in_(ids)
    ).all()
    return {t.id: t.approver_role for t in txns}


def _categorize(row, approver_roles: dict) -> Optional[str]:
    if row.action in _ROLE_AMBIGUOUS_ACTIONS:
        role = approver_roles.get(row.entity_id)
        return 'Sanctions & PEP Screening' if role == 'compliance_officer' else 'Large-Amount Approval'
    return REGULATORY_CATEGORIES.get(row.action)


def _fetch_events(db: Session, start_dt: Optional[datetime], end_dt: Optional[datetime], category: Optional[str], order_asc: bool = False):
    """Rows + their resolved category, already filtered down to `category`
    if one was requested. The SQL-level filter in _regulatory_rows is only
    a candidate-narrowing pass for the two role-ambiguous actions (it can't
    know their real category without a DB lookup) — this is where that
    lookup happens and the final category match is enforced."""
    query = _regulatory_rows(db, start_dt, end_dt, category)
    query = query.order_by(AuditLog.created_at.asc() if order_asc else AuditLog.created_at.desc())
    rows = query.all()
    approver_roles = _approver_role_lookup(db, rows)

    events = [(r, _categorize(r, approver_roles)) for r in rows]
    if category:
        events = [(r, cat) for r, cat in events if cat == category]
    return events


@router.get("/regulatory-categories")
def regulatory_categories(current_user: User = Depends(get_current_admin_or_compliance)):
    """The fixed list of categories the report groups by — lets the
    frontend populate a category filter dropdown without hardcoding it."""
    return ALL_CATEGORIES


@router.get("/regulatory-summary")
def regulatory_summary(
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_admin_or_compliance),
    db: Session = Depends(get_db)
):
    """
    Aggregate counts of every compliance-relevant audit-log action within
    a datetime range, bucketed the way a regulator/auditor would want to
    see them. Purely a reshaping of the existing AuditLog trail — no new
    event tracking, since every one of these events was already being
    logged for its own feature (sanctions/PEP screening, large-amount
    holds, watchlist maker-checker, access control). Takes full
    datetimes, not just dates, so an auditor can narrow in on a specific
    incident window (e.g. "what happened between 14:00 and 14:30") rather
    than always pulling a whole day. `category` optionally scopes both the
    counts and (when set) the export down to just one of ALL_CATEGORIES —
    e.g. an auditor asked specifically for the sanctions/PEP trail doesn't
    need the other four categories' noise.
    """
    events = _fetch_events(db, start_datetime, end_datetime, category)

    counts = {cat: 0 for cat in ALL_CATEGORIES}
    for _, cat in events:
        if cat:
            counts[cat] += 1

    return {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "category": category,
        "total_events": len(events),
        "by_category": counts,
    }


@router.get("/regulatory-export")
def regulatory_export(
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_admin_or_compliance),
    db: Session = Depends(get_db)
):
    """CSV export of every compliance-relevant audit-log row in range —
    the actual document a compliance officer files or hands to a
    regulator, not just an on-screen summary. Optionally scoped to a
    single category, same as regulatory-summary."""
    events = _fetch_events(db, start_datetime, end_datetime, category, order_asc=True)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Timestamp', 'Category', 'Action', 'Username', 'Entity Type', 'Entity ID', 'Details'])
    for r, cat in events:
        writer.writerow([
            r.created_at.isoformat() if r.created_at else '',
            cat or r.action,
            r.action,
            r.username,
            r.entity_type,
            r.entity_id if r.entity_id is not None else '',
            r.details or '',
        ])

    def _fmt(dt):
        return dt.strftime('%Y%m%d-%H%M') if dt else 'all'

    category_suffix = f"_{category.replace(' ', '-').replace('&', 'and')}" if category else ""
    filename = f"regulatory_report_{_fmt(start_datetime)}_{_fmt(end_datetime)}{category_suffix}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
