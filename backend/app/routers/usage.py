"""Usage & billing-limit endpoints for ClipForge (read-only; no payment processing)."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.usage_record import UsageRecord
from app.models.user import User
from app.schemas.usage import UsageRecordResponse, UsageSummaryResponse
from app.services import usage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/me", response_model=UsageSummaryResponse)
async def get_my_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageSummaryResponse:
    """Return the current user's calendar-month usage vs. their plan limits."""
    return usage_service.get_usage_summary(db, current_user.id)


@router.get("/history", response_model=list[UsageRecordResponse])
async def get_my_usage_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UsageRecord]:
    """Return the current user's usage records, most recent first."""
    return usage_service.get_usage_history(db, current_user.id, skip=skip, limit=limit)
