"""Diary 서비스 레이어"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Diary
from app.schemas.diary import DiaryWithPhotos, PhotoInDiary


async def get_or_create_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_date: date,
    time_type: str,
) -> Diary:
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
        Diary: 조회되거나 생성된 다이어리
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
            tags=[],
        )
        db.add(diary)
        await db.commit()
        await db.refresh(diary)

    return diary


async def get_diaries_by_date_range(
    db: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> dict[str, dict]:
    """
    날짜 범위로 다이어리 목록을 조회합니다.

    user_id + diary_date(범위) + deleted_at IS NULL 조건으로 조회하고,
    날짜별로 그룹핑하여 반환합니다.

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        start_date: 시작 날짜 (포함)
        end_date: 종료 날짜 (포함)

    Returns:
        { "YYYY-MM-DD": { "diaries": [...] }, ... }
        다이어리가 없는 날짜도 빈 배열로 포함합니다.
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
        )
        .order_by(Diary.diary_date, Diary.time_type)
    )
    result = await db.execute(stmt)
    diaries = result.scalars().all()

    # 날짜별 그룹핑용 빈 딕셔너리 생성 (다이어리 없는 날도 키 포함)
    response: dict[str, dict] = {}
    cur = start_date
    while cur <= end_date:
        response[cur.isoformat()] = {"diaries": []}
        cur = cur + timedelta(days=1)

    # 다이어리를 날짜별로 채움 (analysis_status NULL이면 "done"으로 처리)
    for diary in diaries:
        date_key = diary.diary_date.date().isoformat()
        if date_key not in response:
            response[date_key] = {"diaries": []}

        status = diary.analysis_status or "done"
        cover_photo_url = None
        if diary.cover_photo is not None:
            cover_photo_url = diary.cover_photo.image_url

        diary_date_str = diary.diary_date.date().isoformat()
        photos = [
            {
                "photo_id": p.id,
                "image_url": p.image_url,
                "analysis_status": status,
            }
            for p in sorted(diary.photos, key=lambda x: x.id)
        ]

        response[date_key]["diaries"].append(
            {
                "id": diary.id,
                "user_id": diary.user_id,
                "diary_date": diary_date_str,
                "time_type": diary.time_type,
                "analysis_status": status,
                "restaurant_name": diary.restaurant_name,
                "restaurant_url": diary.restaurant_url,
                "road_address": diary.road_address,
                "category": diary.category,
                "cover_photo_id": diary.cover_photo_id,
                "cover_photo_url": cover_photo_url,
                "note": diary.note,
                "tags": diary.tags or [],
                "photo_count": diary.photo_count,
                "created_at": diary.created_at,
                "updated_at": diary.updated_at,
                "photos": photos,
            }
        )

    return response


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
        )
    )
    result = await db.execute(stmt)
    diary = result.scalar_one_or_none()
    if diary is None:
        return None

    status = diary.analysis_status or "done"
    cover_photo_url = None
    if diary.cover_photo is not None:
        cover_photo_url = diary.cover_photo.image_url

    diary_date_only = diary.diary_date.date()
    photos = [
        PhotoInDiary(
            photo_id=p.id,
            image_url=p.image_url,
            analysis_status=status,
        )
        for p in sorted(diary.photos, key=lambda x: x.id)
    ]

    return DiaryWithPhotos(
        id=diary.id,
        user_id=diary.user_id,
        diary_date=diary_date_only,
        time_type=diary.time_type,
        analysis_status=status,
        restaurant_name=diary.restaurant_name,
        restaurant_url=diary.restaurant_url,
        road_address=diary.road_address,
        category=diary.category,
        cover_photo_id=diary.cover_photo_id,
        cover_photo_url=cover_photo_url,
        note=diary.note,
        tags=diary.tags or [],
        photo_count=diary.photo_count,
        created_at=diary.created_at,
        updated_at=diary.updated_at,
        photos=photos,
    )
