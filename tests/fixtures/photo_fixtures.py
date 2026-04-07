"""사진 업로드 테스트용 fixture 함수들"""

import io
from datetime import UTC, datetime

from fastapi import UploadFile
from PIL import Image

from app.services.analysis_service import AnalysisData


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
    taken_at: datetime | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """고정 ExifData 반환"""
    return {
        "taken_at": taken_at or datetime(2026, 1, 15, 3, 30, 0, tzinfo=UTC),
        "latitude": latitude,
        "longitude": longitude,
    }


def mock_analysis_data(photo_id: int) -> AnalysisData:
    """고정 AnalysisData 반환"""
    return AnalysisData(
        photo_id=photo_id,
        food_category="한식",
        restaurant_candidates=[
            {
                "name": "테스트식당",
                "confidence": 0.9,
                "address": "서울시 중구",
                "url": "https://place.map.kakao.com/12345",
                "road_address": "서울시 중구 테스트로 1",
            }
        ],
        menu_candidates=[{"name": "칼국수"}],
        keywords=["얼큰한", "구수한"],
        raw_response="{'food_category': '한식'}",
    )
