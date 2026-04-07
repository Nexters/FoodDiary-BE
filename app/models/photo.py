from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.diary import Diary


class Photo(Base):
    """업로드한 사진 모델"""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("diaries.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # PostgreSQL POINT 타입: "(longitude, latitude)" 형태로 저장
    # 예: "(127.027621, 37.497928)"
    taken_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    diary: Mapped["Diary"] = relationship(
        "Diary",
        back_populates="photos",
        foreign_keys=[diary_id],
    )

    def get_full_url(self, base_url: str) -> str:
        path = self.image_url.removeprefix("storage/")
        return f"{base_url}/{path}"

    def __repr__(self) -> str:
        return f"<Photo(id={self.id}, diary_id={self.diary_id})>"
