"""Diary 서비스 레이어"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Diary, Photo
from app.schemas.diary import DiaryWithPhotos, PhotoInDiary
from app.utils.file_storage import save_user_photo

# 다이어리당 최대 사진 개수
MAX_PHOTOS_PER_DIARY = 10


async def get_or_create_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_date: date,
    time_type: str,
) -> tuple[Diary, bool]:
    """
    다이어리를 조회하거나 생성합니다 (upsert).

    user_id + date + time_type 조합으로 다이어리를 찾고,
    없으면 새로 생성합니다.

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        diary_date: 일기 날짜
        time_type: 끼니 타입 ('breakfast', 'lunch', 'dinner', 'snack')

    Returns:
        tuple[Diary, bool]: (조회되거나 생성된 다이어리, 신규 생성 여부)
    """
    # diary_date를 datetime으로 변환 (timezone aware)
    diary_datetime = datetime.combine(diary_date, datetime.min.time(), tzinfo=UTC)

    # 1. SELECT로 기존 다이어리 조회
    stmt = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date == diary_datetime,
        Diary.time_type == time_type,
        Diary.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()

    # 2. 없으면 INSERT
    if diary is None:
        diary = Diary(
            user_id=user_id,
            diary_date=diary_datetime,
            time_type=time_type,
            photo_count=0,
        )
        db.add(diary)
        await db.commit()
        await db.refresh(diary)
        return diary, True

    return diary, False


async def get_diaries_by_date_range(
    db: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> list[Diary]:
    """
    날짜 범위로 다이어리 목록을 조회합니다.

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        start_date: 시작 날짜 (포함)
        end_date: 종료 날짜 (포함)

    Returns:
        Diary ORM 객체 리스트 (photos, cover_photo eager-loaded)
    """
    start_bound = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_bound = datetime.combine(end_date, datetime.min.time(), tzinfo=UTC) + timedelta(
        days=1
    )

    stmt = (
        select(Diary)
        .where(
            Diary.user_id == user_id,
            Diary.diary_date >= start_bound,
            Diary.diary_date < end_bound,
            Diary.deleted_at.is_(None),
        )
        .options(
            selectinload(Diary.photos),
            selectinload(Diary.cover_photo),
            selectinload(Diary.analysis),
        )
        .order_by(Diary.diary_date, Diary.time_type)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_diary_by_id(
    db: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> DiaryWithPhotos | None:
    """
    다이어리 ID로 단일 조회합니다.

    소유자(user_id) 일치 및 deleted_at IS NULL 검증.
    없으면 None 반환 (라우터에서 404 처리).

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        diary_id: 다이어리 ID

    Returns:
        DiaryWithPhotos 또는 None
    """
    stmt = (
        select(Diary)
        .where(
            Diary.id == diary_id,
            Diary.user_id == user_id,
            Diary.deleted_at.is_(None),
        )
        .options(
            selectinload(Diary.photos),
            selectinload(Diary.cover_photo),
            selectinload(Diary.analysis),
        )
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()
    if diary is None:
        return None

    status = diary.analysis_status or "done"
    cover_photo_url = diary.get_cover_photo_url(settings.IMAGE_BASE_URL)
    photos = [
        PhotoInDiary(
            photo_id=p.id,
            image_url=p.get_full_url(settings.IMAGE_BASE_URL),
        )
        for p in sorted(diary.photos, key=lambda x: x.id)
    ]

    return DiaryWithPhotos(
        id=diary.id,
        user_id=diary.user_id,
        diary_date=_merge_date_with_cover_taken_at(diary),
        time_type=diary.time_type,
        analysis_status=status,
        restaurant_name=diary.restaurant_name,
        restaurant_url=diary.restaurant_url,
        road_address=diary.road_address,
        category=diary.category,
        cover_photo_id=diary.cover_photo_id,
        cover_photo_url=cover_photo_url,
        note=diary.note,
        tags=_build_tags(diary),
        photo_count=diary.photo_count,
        created_at=diary.created_at,
        updated_at=diary.updated_at,
        photos=photos,
    )


async def add_photos_to_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_id: int,
    files: list[UploadFile],
) -> list[int] | None:
    """
    기존 다이어리에 사진을 추가합니다.
    소유자 검증 후 파일 저장 + Photo 생성, diary.photo_count 증가.
    없거나 권한 없으면 None 반환.
    사진은 최대 10개까지 추가 가능.

    Raises:
        ValueError: 사진 개수가 10개를 초과하는 경우
    """
    # SELECT ... FOR UPDATE로 락 획득하여 동시성 제어
    stmt = (
        select(Diary)
        .where(
            Diary.id == diary_id,
            Diary.user_id == user_id,
            Diary.deleted_at.is_(None),
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()
    if diary is None:
        return None

    # 사진 개수 제한 체크
    current_photo_count = diary.photo_count
    new_photo_count = len(files)
    total_photo_count = current_photo_count + new_photo_count

    if total_photo_count > MAX_PHOTOS_PER_DIARY:
        raise ValueError(
            f"다이어리당 최대 {MAX_PHOTOS_PER_DIARY}개의 사진만 업로드할 수 있습니다. "
            f"현재: {current_photo_count}개, 추가 시도: {new_photo_count}개"
        )

    new_photo_ids: list[int] = []
    for file in files:
        image_url = await save_user_photo(user_id, file)
        photo = Photo(
            diary_id=diary_id,
            image_url=image_url,
        )
        db.add(photo)
        await db.flush()
        new_photo_ids.append(photo.id)
        diary.photo_count += 1

    await db.commit()
    return new_photo_ids


async def delete_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> bool:
    """
    다이어리 전체 삭제 (소프트 삭제).
    소유자만 가능. 없거나 권한 없으면 False.
    """
    stmt = select(Diary).where(
        Diary.id == diary_id,
        Diary.user_id == user_id,
        Diary.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()
    if diary is None:
        return False
    diary.deleted_at = datetime.now(UTC)
    await db.commit()
    return True


def _build_tags(diary: Diary) -> list[str]:
    """Diary.tags 반환."""
    return diary.tags or []


def _merge_date_with_cover_taken_at(diary: Diary) -> datetime:
    """커버 사진의 taken_at 시각을 diary_date와 합쳐 datetime으로 반환.

    taken_at이 없으면 00:00:00으로 반환.
    """
    time = (
        diary.cover_photo.taken_at.time()
        if diary.cover_photo and diary.cover_photo.taken_at
        else datetime.min.time()
    )
    return datetime.combine(diary.diary_date.date(), time)
