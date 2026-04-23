"""사진 업로드 테스트용 fixture 함수들"""

import io

from fastapi import UploadFile
from PIL import Image


def create_test_image_bytes() -> bytes:
    """1x1 JPEG 이미지 바이트 생성"""
    img = Image.new("RGB", (1, 1), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def create_test_upload_file(
    filename: str = "test.jpg",
    content_type: str = "image/jpeg",
) -> UploadFile:
    """테스트용 UploadFile 생성"""
    content = create_test_image_bytes()
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


def mock_exif_data(
    taken_at=None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """고정 ExifData 반환"""
    from datetime import UTC, datetime

    return {
        "taken_at": taken_at or datetime(2026, 1, 15, 3, 30, 0, tzinfo=UTC),
        "latitude": latitude,
        "longitude": longitude,
    }
