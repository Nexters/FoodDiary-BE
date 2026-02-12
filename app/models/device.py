import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Device(Base, TimestampMixin):
    __tablename__ = "devices"
    __table_args__ = (
        Index("idx_device_device_id", "device_id"),
        Index("idx_device_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    device_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_version: Mapped[str] = mapped_column(String(20), nullable=False)
    os_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices")

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, device_id={self.device_id})>"
