"""Business logic for usage tracking and plan-limit lookups.

`record_usage` is the integration point other modules (e.g. the Clip
Generation pipeline) call after a project finishes processing, so it logs a
`UsageRecord` for that run. `check_within_limits` is a read-only helper that
compares the current calendar month's usage against the user's plan limits;
it does not block or raise, and nothing in this pass wires it into the
pipeline as an enforcement gate (see TODO below).
"""
import calendar
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.plan_limit import PlanLimit, PlanType
from app.models.usage_record import UsageRecord
from app.schemas.usage import UsageSummaryResponse

logger = logging.getLogger(__name__)

# Free-tier defaults applied the first time a user is seen by this module.
DEFAULT_FREE_MONTHLY_MINUTES_LIMIT = 60
DEFAULT_FREE_MONTHLY_CLIPS_LIMIT = 20


def _current_period_start(now: datetime | None = None) -> datetime:
    """Return the start (UTC, tz-aware) of the current calendar month."""
    reference = now or datetime.now(timezone.utc)
    return reference.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    )


def _current_period_end(now: datetime | None = None) -> datetime:
    """Return the start (UTC, tz-aware) of the calendar month after the current one."""
    reference = now or datetime.now(timezone.utc)
    days_in_month = calendar.monthrange(reference.year, reference.month)[1]
    period_start = _current_period_start(reference)
    return period_start.replace(day=days_in_month) + timedelta(days=1)


def get_or_create_plan_limit(db: Session, user_id: int) -> PlanLimit:
    """Fetch the user's `PlanLimit`, creating a default free-tier row if absent."""
    plan_limit = db.query(PlanLimit).filter(PlanLimit.user_id == user_id).first()
    if plan_limit:
        return plan_limit

    plan_limit = PlanLimit(
        user_id=user_id,
        plan_type=PlanType.free,
        monthly_minutes_limit=DEFAULT_FREE_MONTHLY_MINUTES_LIMIT,
        monthly_clips_limit=DEFAULT_FREE_MONTHLY_CLIPS_LIMIT,
    )
    db.add(plan_limit)
    db.commit()
    db.refresh(plan_limit)
    logger.info("Created default free-tier PlanLimit for user_id=%s", user_id)
    return plan_limit


def record_usage(
    db: Session,
    user_id: int,
    project_id: int | None,
    minutes_processed: float,
    clips_generated: int,
) -> UsageRecord:
    """Log a usage event (e.g. after a project finishes processing).

    Callers (such as the Clip Generation pipeline) can invoke this
    unconditionally after a run completes; it never raises to reject usage.
    """
    record = UsageRecord(
        user_id=user_id,
        project_id=project_id,
        minutes_processed=minutes_processed,
        clips_generated=clips_generated,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "Recorded usage for user_id=%s project_id=%s minutes=%s clips=%s",
        user_id,
        project_id,
        minutes_processed,
        clips_generated,
    )
    return record


def has_usage_record(db: Session, project_id: int) -> bool:
    """Return whether a project already has a recorded usage entry.

    Used by the pipeline's finalize step to guard against recording the same
    completed run's usage twice (e.g. a race between two render tasks
    finishing near-simultaneously, or a Celery task retry).
    """
    return db.query(UsageRecord).filter(UsageRecord.project_id == project_id).first() is not None


def delete_usage_records_for_project(db: Session, project_id: int) -> None:
    """Delete a project's usage records, e.g. before reprocessing it from
    scratch so the new run can record a single fresh usage entry.

    Deliberately does NOT commit: this is called from within
    `project_service.start_processing`'s row-locked transaction, and an
    intermediate commit there would end that transaction early, releasing
    the lock before the function finishes (defeating the lock's purpose of
    serializing concurrent process requests). The caller owns the commit.
    """
    db.query(UsageRecord).filter(UsageRecord.project_id == project_id).delete()
    db.flush()


def _sum_current_period_usage(db: Session, user_id: int) -> tuple[float, int]:
    """Sum this calendar month's minutes/clips for a user."""
    period_start = _current_period_start()
    period_end = _current_period_end()
    records = (
        db.query(UsageRecord)
        .filter(
            UsageRecord.user_id == user_id,
            UsageRecord.recorded_at >= period_start,
            UsageRecord.recorded_at < period_end,
        )
        .all()
    )
    minutes_used = sum(r.minutes_processed for r in records)
    clips_used = sum(r.clips_generated for r in records)
    return minutes_used, clips_used


def check_within_limits(db: Session, user_id: int) -> bool:
    """Return whether the user's current-month usage is within their plan limits.

    Read-only check: this does not block anything. Nothing in this pass calls
    this to reject/halt processing.

    TODO(future pass): wire this into the Clip Generation pipeline as a hard
    enforcement gate (e.g. reject/queue new processing jobs once a user is
    over their monthly minutes/clips limit) rather than a read-only check.
    """
    plan_limit = get_or_create_plan_limit(db, user_id)
    minutes_used, clips_used = _sum_current_period_usage(db, user_id)
    return (
        minutes_used <= plan_limit.monthly_minutes_limit
        and clips_used <= plan_limit.monthly_clips_limit
    )


def get_usage_summary(db: Session, user_id: int) -> UsageSummaryResponse:
    """Build the current calendar-month usage summary vs. plan limits."""
    plan_limit = get_or_create_plan_limit(db, user_id)
    minutes_used, clips_used = _sum_current_period_usage(db, user_id)
    return UsageSummaryResponse(
        plan_type=plan_limit.plan_type.value,
        monthly_minutes_limit=plan_limit.monthly_minutes_limit,
        monthly_clips_limit=plan_limit.monthly_clips_limit,
        minutes_used_this_period=minutes_used,
        clips_used_this_period=clips_used,
    )


def get_usage_history(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[UsageRecord]:
    """Return the user's usage records, most recent first."""
    return (
        db.query(UsageRecord)
        .filter(UsageRecord.user_id == user_id)
        .order_by(UsageRecord.recorded_at.desc(), UsageRecord.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
