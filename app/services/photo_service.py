"""Photo 서비스 레이어 — 순수 도메인 로직 (DB 접근 없음)"""

import asyncio
import io
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile


async def delete_photo_files(image_urls: list[str]) -> None:
    """사진 파일을 실제 스토리지에서 삭제합니다."""
    for image_url in image_urls:
        path = Path(image_url)
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)


@dataclass
class PhotoSyncResult:
    """동기 단계에서 생성된 사진/다이어리 정보 (비동기 단계 인수용)"""

    photo_id: int
    diary_id: int
    time_type: str
    image_url: str
    is_new_diary: bool
    analysis_status: str


def to_upload_files(
    file_buffers: list[tuple[str, bytes, str]],
) -> list[UploadFile]:
    return [
        UploadFile(
            file=io.BytesIO(content),
            filename=filename,
            headers={"content-type": content_type},
        )
        for filename, content, content_type in file_buffers
    ]
