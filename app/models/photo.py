from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.diary import Diary


class Photo(Base):
    """업로드한 사진 모델 (사진 단위로 분석 결과를 독립적으로 가짐)"""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diary_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("diaries.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # PostgreSQL POINT 타입: "(longitude, latitude)" 형태로 저장
    # 예: "(127.027621, 37.497928)"
    taken_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    diary: Mapped["Diary"] = relationship(
        "Diary",
        back_populates="photos",
        foreign_keys=[diary_id],
    )
    analysis_result: Mapped["PhotoAnalysisResult | None"] = relationship(
        "PhotoAnalysisResult",
        back_populates="photo",
        uselist=False,
        passive_deletes=True,
    )

    def get_full_url(self, base_url: str) -> str:
        path = self.image_url.removeprefix("storage/")
        return f"{base_url}/{path}"

    def __repr__(self) -> str:
        return f"<Photo(id={self.id}, diary_id={self.diary_id})>"


class PhotoAnalysisResult(Base):
    """사진 하나에 대한 AI 추론 결과 (유저 미확정 상태)"""

    __tablename__ = "photo_analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    photo_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    food_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    restaurant_name_candidates: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    menu_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    photo: Mapped["Photo"] = relationship("Photo", back_populates="analysis_result")

    def __repr__(self) -> str:
        return f"<PhotoAnalysisResult(id={self.id}, photo_id={self.photo_id})>"
