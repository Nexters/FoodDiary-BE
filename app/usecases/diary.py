import asyncio
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import diary as crud_diary
from app.models import Diary, Photo
from app.schemas.diary import DiaryUpdate, DiaryWithPhotos, PhotoInDiary
from app.services import photo_service
from app.services.diary_service import _build_tags, _merge_date_with_cover_taken_at


class DiaryNotFoundError(Exception):
    pass


class PhotoRequiredError(Exception):
    pass


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
    update_data = body.model_dump(exclude_unset=True, exclude={"photo_ids"})
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
        created_at=diary.created_at,
        updated_at=diary.updated_at,
        photos=[
            PhotoInDiary(
                photo_id=p.id, image_url=p.get_full_url(settings.IMAGE_BASE_URL)
            )
            for p in photos
        ],
    )
