"""Diary 서비스 레이어"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Diary, Photo
from app.models.diary import DiaryAnalysis
from app.schemas.diary import (
    DiaryAnalysisResponse,
    DiaryUpdate,
    DiaryWithPhotos,
    PhotoInDiary,
    RestaurantCandidate,
)
from app.utils.file_storage import save_user_photo

# 다이어리당 최대 사진 개수
MAX_PHOTOS_PER_DIARY = 10


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
    날짜 범위로 다이어리 사진 목록을 조회합니다. (캘린더 뷰용 간소화 형식)

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        start_date: 시작 날짜 (포함)
        end_date: 종료 날짜 (포함)

    Returns:
        { "YYYY-MM-DD": { "photos": ["url1", "url2", ...] }, ... }
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
        .options(selectinload(Diary.photos))
        .order_by(Diary.diary_date, Diary.time_type)
    )
    result = await db.execute(stmt)
    diaries = result.scalars().all()

    response: dict[str, dict] = {}
    cur = start_date
    while cur <= end_date:
        response[cur.isoformat()] = {"photos": []}
        cur = cur + timedelta(days=1)

    for diary in diaries:
        date_key = diary.diary_date.date().isoformat()
        if date_key not in response:
            response[date_key] = {"photos": []}
        for p in sorted(diary.photos, key=lambda x: x.id):
            response[date_key]["photos"].append(p.image_url)

    return response


async def get_diaries_by_date(
    db: AsyncSession,
    user_id: UUID,
    query_date: date,
) -> dict:
    """
    특정 날짜의 다이어리 목록을 조회합니다. (일간 뷰용 상세 형식)

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        query_date: 조회할 날짜

    Returns:
        { "diaries": [...DiaryWithPhotos...] }
    """
    start_bound = datetime.combine(query_date, datetime.min.time(), tzinfo=UTC)
    end_bound = start_bound + timedelta(days=1)

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
        .order_by(Diary.time_type)
    )
    result = await db.execute(stmt)
    diaries = result.scalars().all()

    diary_list = []
    for diary in diaries:
        status = diary.analysis_status or "done"
        cover_photo_url = diary.cover_photo.image_url if diary.cover_photo else None
        photos = [
            PhotoInDiary(
                photo_id=p.id,
                image_url=p.image_url,
                analysis_status=status,
            )
            for p in sorted(diary.photos, key=lambda x: x.id)
        ]
        diary_list.append(
            DiaryWithPhotos(
                id=diary.id,
                user_id=diary.user_id,
                diary_date=diary.diary_date.date(),
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
        )

    return {"diaries": diary_list}


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


async def get_diary_analysis(
    db: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> DiaryAnalysisResponse | None:
    """
    다이어리 분석 후보 조회

    DiaryAnalysis의 restaurant_candidates, category_candidates, menu_candidates 반환
    "이 식당을 찾고 계신가요?" 화면에서 사용

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        diary_id: 다이어리 ID

    Returns:
        DiaryAnalysisResponse 또는 None
    """
    # 1. Diary 소유자 검증
    diary_stmt = select(Diary).where(
        Diary.id == diary_id,
        Diary.user_id == user_id,
        Diary.deleted_at.is_(None),
    )
    diary_result = await db.execute(diary_stmt)
    diary = diary_result.scalar_one_or_none()

    if diary is None:
        return None

    # 2. DiaryAnalysis 조회
    analysis_stmt = select(DiaryAnalysis).where(DiaryAnalysis.diary_id == diary_id)
    analysis_result = await db.execute(analysis_stmt)
    analysis = analysis_result.scalar_one_or_none()

    if analysis is None:
        # 분석 결과가 없으면 빈 리스트 반환
        return DiaryAnalysisResponse(
            restaurant_candidates=[],
            category_candidates=[],
            menu_candidates=[],
        )

    # 3. restaurant_candidates 변환
    restaurant_candidates = []
    if analysis.restaurant_candidates:
        for r in analysis.restaurant_candidates:
            restaurant_candidates.append(
                RestaurantCandidate(
                    name=r.get("name", ""),
                    confidence=r.get("confidence"),
                    address=r.get("address"),
                    url=r.get("url"),
                )
            )

    # 4. category_candidates (이미 문자열 리스트)
    category_candidates = analysis.category_candidates or []

    # 5. menu_candidates (이미 문자열 리스트)
    menu_candidates = analysis.menu_candidates or []

    return DiaryAnalysisResponse(
        restaurant_candidates=restaurant_candidates,
        category_candidates=category_candidates,
        menu_candidates=menu_candidates,
    )


async def update_diary(
    db: AsyncSession,
    user_id: UUID,
    diary_id: int,
    body: DiaryUpdate,
) -> DiaryWithPhotos | None:
    """
    다이어리 수정. 소유자 검증 후 전달된 필드만 업데이트.
    photo_ids가 있으면 해당 ID만 유지·순서 반영, 나머지 사진은 삭제.
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

    # 전달된 필드만 반영 (None이 아닌 값만)
    if body.category is not None:
        diary.category = body.category
    if body.restaurant_name is not None:
        diary.restaurant_name = body.restaurant_name
    if body.restaurant_url is not None:
        diary.restaurant_url = body.restaurant_url
    if body.road_address is not None:
        diary.road_address = body.road_address
    if body.tags is not None:
        diary.tags = body.tags
    if body.note is not None:
        diary.note = body.note
    if body.cover_photo_id is not None:
        diary.cover_photo_id = body.cover_photo_id

    if body.photo_ids is not None:
        # 이 다이어리 소속인지 검증
        check = await db.execute(
            select(Photo.id).where(
                Photo.diary_id == diary_id,
                Photo.id.in_(body.photo_ids),
            )
        )
        valid_ids = {r[0] for r in check.fetchall()}
        if len(valid_ids) != len(body.photo_ids):
            # 다른 다이어리 사진이 포함됨 → 무시하거나 400. 여기서는 유효한 ID만 사용
            photo_ids_ordered = [pid for pid in body.photo_ids if pid in valid_ids]
        else:
            photo_ids_ordered = body.photo_ids

        if photo_ids_ordered:
            await db.execute(
                delete(Photo).where(
                    Photo.diary_id == diary_id,
                    Photo.id.notin_(photo_ids_ordered),
                )
            )
        else:
            await db.execute(delete(Photo).where(Photo.diary_id == diary_id))
        diary.photo_count = len(photo_ids_ordered)
        if diary.cover_photo_id not in photo_ids_ordered:
            diary.cover_photo_id = photo_ids_ordered[0] if photo_ids_ordered else None

    await db.commit()
    # 세션의 모든 객체를 만료시켜 다음 조회 시 DB에서 최신 데이터 로드
    db.expire_all()
    return await get_diary_by_id(db, user_id, diary_id)


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
