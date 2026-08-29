"""Pydantic schemas for usage & billing-limit responses."""
from datetime import datetime

from pydantic import BaseModel


class UsageSummaryResponse(BaseModel):
    """Current calendar-month usage totals against the user's plan limits."""

    plan_type: str
    monthly_minutes_limit: int
    monthly_clips_limit: int
    minutes_used_this_period: float
    clips_used_this_period: int

    class Config:
        from_attributes = True


class UsageRecordResponse(BaseModel):
    """A single logged usage event (one project's processing run)."""

    id: int
    project_id: int | None
    minutes_processed: float
    clips_generated: int
    recorded_at: datetime

    class Config:
        from_attributes = True
