"""PublishConnection model for ClipForge: a user's linked social platform account."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Platform(str, enum.Enum):
    tiktok = "tiktok"
    instagram = "instagram"
    youtube_shorts = "youtube_shorts"


class PublishConnection(Base):
    """A user's OAuth connection to a publishing platform.

    access_token / refresh_token are stored as plain String columns here;
    encryption at rest is handled at the service layer.
    """

    __tablename__ = "publish_connections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    access_token: Mapped[str] = mapped_column(String(2000), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    account_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="publish_connections")

    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_publish_connections_user_platform"),
    )
