"""PlanLimit model for ClipForge: per-user plan quota (one row per user)."""
import enum

from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"


class PlanLimit(Base):
    """A user's subscription plan and monthly usage limits."""

    __tablename__ = "plan_limits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_type: Mapped[PlanType] = mapped_column(
        Enum(PlanType), default=PlanType.free, nullable=False
    )
    monthly_minutes_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_clips_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    user = relationship("User", back_populates="plan_limit")
