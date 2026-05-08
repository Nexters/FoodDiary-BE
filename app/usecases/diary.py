import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.crud import diary as crud_diary
from app.crud import photo as crud_photo
from app.crud.device import get_device_id_for_user
from app.crud.diary import (
    apply_top_restaurant,
    claim_diary_for_processing,
    mark_diaries_done,
    mark_diaries_pending,
    save_diary_analysis,
)
from app.crud.photo import get_photos_by_diary_id
from app.models import Diary, Photo
from app.models.diary import DiaryCategory
from app.schemas.diary import DiaryUpdate, DiaryWithPhotos, PhotoInDiary
from app.services import photo_service
from app.services.analysis_service import analyze_diary_photos
from app.services.diary_service import (
    MAX_PHOTOS_PER_DIARY,
    _build_tags,
    _merge_date_with_cover_taken_at,
)
from app.services.notification_service import send_silent_notification
from app.utils.file_storage import save_user_photo
from app.utils.timezone import utc_to_kst_naive

logger = logging.getLogger(__name__)


@dataclass
class AnalysisData:
    diary_id: int
    result: list


async def analyze_and_notify(
    diary_ids: list[int],
    device_id: str | None,
    target_date: date,
    test_mode: bool = False,
) -> None:
    await asyncio.gather(
        *[
            _claim_and_analyze(diary_id, device_id, target_date, test_mode)
            for diary_id in diary_ids
        ],
        return_exceptions=True,
    )


async def _claim_and_analyze(
    diary_id: int,
    device_id: str | None,
    target_date: date,
    test_mode: bool,
) -> None:
    async with AsyncSessionLocal() as db:
        if not await claim_diary_for_processing(db, diary_id):
            logger.debug("[Analysis] 클레임 실패, 건너뜀: diary_id=%d", diary_id)
            return  # 다른 프로세스가 이미 클레임 — 중복 분석 방지
    logger.info("[Analysis] 분석 시작: diary_id=%d", diary_id)
    await _run_analysis_pipeline(diary_id, test_mode=test_mode)
    async with AsyncSessionLocal() as db:
        await send_silent_notification(
            db=db,
            device_id=device_id,
            data={"type": "analysis_complete", "diary_date": str(target_date)},
        )


async def _run_analysis_pipeline(diary_id: int, test_mode: bool = False) -> None:
    try:
        data = await _analyze_diary(diary_id, test_mode)
        await _save_analysis_result(data)
        logger.info("[Analysis] 완료 → done: diary_id=%d", diary_id)
    except Exception:
        logger.exception("[Analysis] 실패 → pending 복귀: diary_id=%d", diary_id)
        async with AsyncSessionLocal() as db:
            await mark_diaries_pending(db, [diary_id])
            await db.commit()  # pending 복귀 — 스케줄러가 다음 tick에 재시도


async def _analyze_diary(diary_id: int, test_mode: bool) -> AnalysisData:
    if test_mode:
        return _create_mock_analysis_data(diary_id)
    return await _analyze_with_new_session(diary_id)


async def _save_analysis_result(data: AnalysisData) -> None:
    # 저장과 done 마크를 같은 트랜잭션으로 묶음 — 중간 실패 시 stale 복구가 재시도 가능
    async with AsyncSessionLocal() as db:
        await save_diary_analysis(db, data.diary_id, data.result)
        top = _extract_top_restaurant(data.result)
        if top:
            await apply_top_restaurant(db, data.diary_id, **top)
        await mark_diaries_done(db, [data.diary_id])
        await db.commit()


async def _analyze_with_new_session(diary_id: int) -> AnalysisData:
    async with AsyncSessionLocal() as db:
        photos = await get_photos_by_diary_id(db, diary_id)
    result = await analyze_diary_photos(photos)
    if not result:
        raise ValueError(f"분석 결과 없음: diary_id={diary_id}")
    return AnalysisData(diary_id=diary_id, result=result)


def _extract_top_restaurant(result: list[dict]) -> dict | None:
    if not result:
        return None
    top = result[0]
    return {
        "restaurant_name": top.get("restaurant_name"),
        "restaurant_url": top.get("restaurant_url"),
        "road_address": top.get("road_address"),
        "category": DiaryCategory.from_str(top.get("category")),
        "note": top.get("memo") or None,
    }


def _create_mock_analysis_data(diary_id: int) -> AnalysisData:
    categories = ["한식", "일식", "중식", "양식", "카페"]
    food_category = categories[diary_id % len(categories)]

    restaurant_data = {
        "한식": [
            {
                "name": "할머니집",
                "confidence": 0.85,
                "address": "서울시 강남구 테헤란로 123",
            },
            {
                "name": "명동교자",
                "confidence": 0.75,
                "address": "서울시 중구 명동길 29",
            },
        ],
        "일식": [
            {
                "name": "스시히로바",
                "confidence": 0.90,
                "address": "서울시 강남구 역삼동 456",
            },
            {
                "name": "돈코츠라멘",
                "confidence": 0.70,
                "address": "서울시 서초구 서초대로 789",
            },
        ],
        "중식": [
            {
                "name": "중화루",
                "confidence": 0.80,
                "address": "서울시 마포구 서교동 321",
            },
            {
                "name": "차이나팩토리",
                "confidence": 0.65,
                "address": "서울시 용산구 이태원로 111",
            },
        ],
        "양식": [
            {
                "name": "이탈리안키친",
                "confidence": 0.88,
                "address": "서울시 강남구 압구정로 222",
            },
            {
                "name": "스테이크하우스",
                "confidence": 0.72,
                "address": "서울시 서초구 반포대로 333",
            },
        ],
        "카페": [
            {
                "name": "스타벅스",
                "confidence": 0.92,
                "address": "서울시 강남구 선릉로 444",
            },
            {
                "name": "투썸플레이스",
                "confidence": 0.78,
                "address": "서울시 송파구 올림픽로 555",
            },
        ],
    }

    tags_data = {
        "한식": ["김치찌개", "된장찌개", "매운", "구수한", "국물"],
        "일식": ["스시세트", "라멘", "신선한", "회", "담백한"],
        "중식": ["짜장면", "짬뽕", "기름진", "볶음"],
        "양식": ["파스타", "스테이크", "크림", "치즈"],
        "카페": ["아메리카노", "카페라떼", "디저트", "달콤한"],
    }

    result = [
        {
            "restaurant_name": r["name"],
            "restaurant_url": r.get("url", ""),
            "road_address": r.get("address", ""),
            "tags": tags_data[food_category],
            "category": food_category,
            "memo": f"[TEST MODE] {r['name']} 분석 결과",
        }
        for r in restaurant_data[food_category]
    ]
    return AnalysisData(diary_id=diary_id, result=result)


_STALE_THRESHOLD_MINUTES = 5
MAX_SEND_CNT = 3  # 1회 초기 시도 + 재시도 2회


async def expire_stale_diaries() -> int:
    stale_before = datetime.now(UTC) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)
    async with AsyncSessionLocal() as db:
        count = await crud_diary.expire_stale_processing_diaries(db, stale_before)
        await db.commit()
    return count


async def dispatch_pending_diary(diary_id: int) -> None:
    """send_cnt가 한도 미만이면 분석 시작, 초과면 failed 처리."""
    async with AsyncSessionLocal() as db:
        diary = await crud_diary.get_diary(db, diary_id)
        if diary is None:
            return
        if diary.send_cnt >= MAX_SEND_CNT:
            logger.warning(
                "[Analysis] send_cnt 한도 초과 → failed: diary_id=%d, send_cnt=%d/%d",
                diary_id,
                diary.send_cnt,
                MAX_SEND_CNT,
            )
            await exhaust_failed_diary(db, diary_id)
            return
        device_id = await get_device_id_for_user(db, diary.user_id)
    await analyze_and_notify(
        diary_ids=[diary_id],
        device_id=device_id,
        target_date=diary.diary_date.date(),
    )


async def exhaust_failed_diary(session: AsyncSession, diary_id: int) -> None:
    diary = await crud_diary.get_diary(session, diary_id)
    if diary is None:
        return
    await crud_diary.mark_diaries_failed(session, [diary_id])
    await session.commit()  # 알림 실패가 상태 변경을 롤백하지 않도록 먼저 확정
    device_id = await get_device_id_for_user(session, diary.user_id)
    await send_silent_notification(
        db=session,
        device_id=device_id,
        data={
            "type": "analysis_failed",
            "diary_date": str(diary.diary_date.date()),
        },
    )


class DiaryNotFoundError(Exception):
    pass


class PhotoRequiredError(Exception):
    pass


class PhotoLimitExceededError(Exception):
    pass


class DateRangeInvalidError(Exception):
    pass


class DateRangeTooLongError(Exception):
    pass


async def get_diaries_by_date_range(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
) -> list[DiaryWithPhotos]:
    if start_date > end_date:
        raise DateRangeInvalidError
    if (end_date - start_date).days > 42:
        raise DateRangeTooLongError
    diaries = await crud_diary.get_diaries_by_date_range(
        session, user_id, start_date, end_date
    )
    return [
        _build_diary_with_photos(d, sorted(d.photos, key=lambda x: x.id))
        for d in diaries
    ]


async def get_diary(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> DiaryWithPhotos:
    diary = await crud_diary.get_diary(session, diary_id)
    if diary is None or diary.user_id != user_id:
        raise DiaryNotFoundError
    return _build_diary_with_photos(diary, sorted(diary.photos, key=lambda x: x.id))


async def update_diary(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
    body: DiaryUpdate,
) -> DiaryWithPhotos:
    diary = await crud_diary.get_diary(session, diary_id)
    if diary is None or diary.user_id != user_id:
        raise DiaryNotFoundError

    # 클라이언트가 실제로 보낸 필드만 추출 (미전송 필드는 제외, photo_ids는 별도 처리)
    # 예: {"note": "맛있다"} 만 보내면 note만 덮어씀
    update_data = body.model_dump(
        exclude_unset=True, exclude_none=True, exclude={"photo_ids"}
    )
    for field, value in update_data.items():
        setattr(diary, field, value)

    # 이미 로드된 diary.photos에서 유효한 ID만 필터링 (순서 유지)
    existing_ids = {p.id for p in diary.photos}
    # 클라이언트가 보낸 photo_ids 중 실제로 존재하는 ID만 순서대로 추출
    photo_ids_ordered = [pid for pid in (body.photo_ids or []) if pid in existing_ids]
    if not photo_ids_ordered:
        raise PhotoRequiredError

    ids_to_delete = existing_ids - set(photo_ids_ordered)
    await crud_diary.delete_photos(session, ids_to_delete)

    # 트랜잭션 커밋 완료 후 파일 삭제
    image_urls_to_delete = [p.image_url for p in diary.photos if p.id in ids_to_delete]
    event.listen(
        session.sync_session,
        "after_commit",
        lambda _: asyncio.create_task(
            photo_service.delete_photo_files(image_urls_to_delete)
        ),
        once=True,
    )

    # 필요시 커버 사진 교체
    if diary.cover_photo_id not in photo_ids_ordered:
        diary.cover_photo_id = photo_ids_ordered[0]
    diary.photo_count = len(photo_ids_ordered)

    remaining_photos = [p for p in diary.photos if p.id in set(photo_ids_ordered)]
    return _build_diary_with_photos(diary, remaining_photos)


def _build_diary_with_photos(diary: Diary, photos: list[Photo]) -> DiaryWithPhotos:
    status = diary.analysis_status or "done"
    cover_photo = next((p for p in photos if p.id == diary.cover_photo_id), None)
    cover_photo_url = (
        cover_photo.get_full_url(settings.IMAGE_BASE_URL) if cover_photo else None
    )

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
        created_at=utc_to_kst_naive(diary.created_at),
        updated_at=utc_to_kst_naive(diary.updated_at),
        photos=[
            PhotoInDiary(
                photo_id=p.id, image_url=p.get_full_url(settings.IMAGE_BASE_URL)
            )
            for p in photos
        ],
    )


async def add_diary_photos(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
    files: list[UploadFile],
) -> list[int]:
    diary = await crud_diary.get_diary_for_update(session, diary_id)
    if diary is None or diary.user_id != user_id:
        raise DiaryNotFoundError

    total_photo_count = diary.photo_count + len(files)
    if total_photo_count > MAX_PHOTOS_PER_DIARY:
        raise PhotoLimitExceededError(
            f"다이어리당 최대 {MAX_PHOTOS_PER_DIARY}개의 사진만 업로드할 수 있습니다. "
            f"현재: {diary.photo_count}개, 추가 시도: {len(files)}개"
        )

    # 스토리지에 이미지 파일 저장
    image_urls = await asyncio.gather(
        *[save_user_photo(user_id, file) for file in files]
    )
    # 데이터베이스에 이미지 정보 저장
    photos = await crud_photo.create_photos(
        session, [Photo(diary_id=diary_id, image_url=url) for url in image_urls]
    )
    diary.photo_count += len(photos)
    return [photo.id for photo in photos]


async def delete_diary(
    session: AsyncSession,
    user_id: UUID,
    diary_id: int,
) -> None:
    diary = await crud_diary.get_diary(session, diary_id)
    if diary is None or diary.user_id != user_id:
        raise DiaryNotFoundError

    image_urls_to_delete = [p.image_url for p in diary.photos]
    photo_ids = {p.id for p in diary.photos}
    await crud_diary.delete_photos(session, photo_ids)
    await crud_diary.delete_diary(session, diary)

    # 트랜잭션 커밋 이후 사진 파일 삭제
    event.listen(
        session.sync_session,
        "after_commit",
        lambda _: asyncio.create_task(
            photo_service.delete_photo_files(image_urls_to_delete)
        ),
        once=True,
    )
