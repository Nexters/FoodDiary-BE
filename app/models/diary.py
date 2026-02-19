import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, desc, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.photo import Photo
    from app.models.user import User


class Diary(Base):
    """끼니별 일기 모델 (아침/점심/저녁/간식)"""

    __tablename__ = "diaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    diary_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    time_type: Mapped[str] = mapped_column(String(20), nullable=False)
    restaurant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    restaurant_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    road_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )  # processing | done | failed (새로 생성 = 분석 전)
    cover_photo_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("photos.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    photo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="diaries")
    photos: Mapped[list["Photo"]] = relationship(
        "Photo",
        back_populates="diary",
        foreign_keys="Photo.diary_id",
        passive_deletes=True,
    )
    cover_photo: Mapped["Photo | None"] = relationship(
        "Photo",
        foreign_keys=[cover_photo_id],
        post_update=True,
    )
    analysis: Mapped["DiaryAnalysis | None"] = relationship(
        "DiaryAnalysis",
        back_populates="diary",
        uselist=False,
        passive_deletes=True,
    )

    # 인덱스 정의 (main 브랜치의 인사이트 기능 유지)
    __table_args__ = (
        Index(
            "idx_diaries_user_date_active",
            "user_id",
            desc("diary_date"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Diary(id={self.id}, user_id={self.user_id}, "
            f"diary_date={self.diary_date}, time_type={self.time_type})>"
        )


class DiaryAnalysis(Base):
    """다이어리 하나에 대한 AI 추론 결과 (유저 미확정 상태)"""

    __tablename__ = "diary_analysis"

    diary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("diaries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    restaurant_candidates: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    category_candidates: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    menu_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    # Relationships
    diary: Mapped["Diary"] = relationship("Diary", back_populates="analysis")

    def __repr__(self) -> str:
        return f"<DiaryAnalysis(diary_id={self.diary_id})>"
