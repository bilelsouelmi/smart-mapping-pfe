from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin_or_compliance, get_db
from app.models.audit_log import AuditLog
from app.models.business_variable import BusinessVariable
from app.models.pending_transaction import PendingTransactionApproval
from app.models.pending_validation_correction import PendingValidationCorrection
from app.models.processed_transaction import ProcessedTransaction
from app.models.user import User

router = APIRouter()

# Outright blocks/flags a transform can hit before a hold is even created —
# distinct from the holds themselves (PendingTransactionApproval), which
# are transforms that succeeded but got gated pending review.
_BLOCK_ACTIONS = ('sanctions_block', 'duplicate_block', 'aml_flag')

# Same name -> role mapping the turnaround averages already use, so each
# target lines up with the metric it's judging. Defaults here only matter
# if the Business Variable row is ever missing (e.g. a fresh DB before
# anyone's touched Business Variables) — the admin-editable row is the
# real source of truth once it exists, same pattern as every other
# threshold in this codebase (see transform_mapping.py's _get_global_variables).
_SLA_TARGET_VARS = {'admin': ('SLA_ADMIN_HOLD_HOURS', 4.0), 'compliance_officer': ('SLA_PEP_HOLD_HOURS', 2.0)}


def _sla_targets_hours(db: Session) -> dict:
    targets = {}
    for role, (var_name, default) in _SLA_TARGET_VARS.items():
        var = db.query(BusinessVariable).filter(BusinessVariable.name == var_name).first()
        try:
            targets[role] = float(var.value) if var else default
        except (TypeError, ValueError):
            targets[role] = default
    return targets


def _in_range(query, column, start_dt: Optional[datetime], end_dt: Optional[datetime]):
    if start_dt:
        query = query.filter(column >= start_dt)
    if end_dt:
        query = query.filter(column <= end_dt)
    return query


@router.get("/sla-summary")
def sla_summary(
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
    current_user: User = Depends(get_current_admin_or_compliance),
    db: Session = Depends(get_db)
):
    """
    Operational performance snapshot over a date range: transform volume,
    how long holds take to clear (by role, since a PEP hold and a
    large-amount hold have very different reviewers), how often
    validation fails, how often a transform gets blocked outright before
    a hold is even created. Every number is a straight aggregation of
    tables that already exist for their own feature (ProcessedTransaction,
    PendingTransactionApproval, PendingValidationCorrection, AuditLog) —
    nothing new is tracked here, this just answers "how is the platform
    performing" instead of "what happened" (that's regulatory-summary).
    """
    total_transforms = _in_range(
        db.query(ProcessedTransaction), ProcessedTransaction.created_at, start_datetime, end_datetime
    ).count()

    holds = _in_range(
        db.query(PendingTransactionApproval), PendingTransactionApproval.created_at, start_datetime, end_datetime
    ).all()

    holds_by_role = {'admin': 0, 'compliance_officer': 0}
    turnaround_sums = {'admin': 0.0, 'compliance_officer': 0.0}
    turnaround_counts = {'admin': 0, 'compliance_officer': 0}
    still_pending = 0
    for h in holds:
        role = h.approver_role or 'admin'
        holds_by_role[role] = holds_by_role.get(role, 0) + 1
        if h.status == 'pending':
            still_pending += 1
        elif h.resolved_at:
            seconds = (h.resolved_at - h.created_at).total_seconds()
            turnaround_sums[role] = turnaround_sums.get(role, 0.0) + seconds
            turnaround_counts[role] = turnaround_counts.get(role, 0) + 1

    avg_turnaround_seconds = {
        role: (turnaround_sums[role] / turnaround_counts[role]) if turnaround_counts[role] else None
        for role in ('admin', 'compliance_officer')
    }

    # SLA in the literal sense: an actual target compared against the
    # measured average, not just the average on its own — "within_target"
    # is None (not True/False) when there's no resolved hold yet to judge,
    # since "no data" and "met the target" are different things a
    # dashboard shouldn't conflate.
    sla_target_hours = _sla_targets_hours(db)
    sla_status = {}
    for role in ('admin', 'compliance_officer'):
        target_hours = sla_target_hours[role]
        avg_seconds = avg_turnaround_seconds[role]
        sla_status[role] = {
            "target_hours": target_hours,
            "within_target": (avg_seconds <= target_hours * 3600) if avg_seconds is not None else None,
        }

    validations = _in_range(
        db.query(PendingValidationCorrection), PendingValidationCorrection.created_at, start_datetime, end_datetime
    ).all()
    validation_status_counts = {'pending': 0, 'resolved': 0, 'dismissed': 0}
    for v in validations:
        validation_status_counts[v.status] = validation_status_counts.get(v.status, 0) + 1

    block_counts = defaultdict(int)
    for row in _in_range(
        db.query(AuditLog).filter(AuditLog.action.in_(_BLOCK_ACTIONS)), AuditLog.created_at, start_datetime, end_datetime
    ).all():
        block_counts[row.action] += 1

    return {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "total_transforms": total_transforms,
        "holds_created": len(holds),
        "holds_by_role": holds_by_role,
        "holds_still_pending": still_pending,
        "avg_turnaround_seconds": avg_turnaround_seconds,
        "sla_status": sla_status,
        "validation_failures": len(validations),
        "validation_status_counts": validation_status_counts,
        "block_counts": dict(block_counts),
    }


@router.get("/sla-timeseries")
def sla_timeseries(
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
    current_user: User = Depends(get_current_admin_or_compliance),
    db: Session = Depends(get_db)
):
    """Daily counts for charting — transform volume, holds created, outright
    blocks, and validation failures, one point per calendar day in range.
    Every day in the range is included even if empty, so a chart doesn't
    silently skip gaps and mislead about zero-activity days."""
    end_dt = end_datetime or datetime.utcnow()
    start_dt = start_datetime or (end_dt - timedelta(days=30))

    by_day = defaultdict(lambda: {"transforms": 0, "holds": 0, "blocks": 0, "validation_failures": 0})

    for row in _in_range(db.query(ProcessedTransaction), ProcessedTransaction.created_at, start_dt, end_dt).all():
        by_day[row.created_at.date().isoformat()]["transforms"] += 1

    for row in _in_range(db.query(PendingTransactionApproval), PendingTransactionApproval.created_at, start_dt, end_dt).all():
        by_day[row.created_at.date().isoformat()]["holds"] += 1

    for row in _in_range(
        db.query(AuditLog).filter(AuditLog.action.in_(_BLOCK_ACTIONS)), AuditLog.created_at, start_dt, end_dt
    ).all():
        by_day[row.created_at.date().isoformat()]["blocks"] += 1

    for row in _in_range(db.query(PendingValidationCorrection), PendingValidationCorrection.created_at, start_dt, end_dt).all():
        by_day[row.created_at.date().isoformat()]["validation_failures"] += 1

    result = []
    d = start_dt.date()
    end_d = end_dt.date()
    while d <= end_d:
        key = d.isoformat()
        entry = by_day.get(key, {"transforms": 0, "holds": 0, "blocks": 0, "validation_failures": 0})
        result.append({"date": key, **entry})
        d += timedelta(days=1)

    return result
