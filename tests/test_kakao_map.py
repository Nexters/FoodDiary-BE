"""Kakao Map API 통합 테스트"""

import pytest

from app.core.config import settings
from app.services.kakao_map_service import search_nearby_restaurants

PLACEHOLDER_VALUES = {"", "your_kakao_api_key_here", "test_kakao_key"}


@pytest.mark.asyncio
async def test_search_nearby_restaurants():
    """
    실제 Kakao API로 주변 음식점 검색:
    - 서울 시청 좌표로 검색
    - name, address, road_address, kakao_id 필드 존재 확인
    - API 키가 없거나 placeholder면 SKIP
    """
    if settings.KAKAO_REST_API_KEY in PLACEHOLDER_VALUES:
        pytest.skip("유효한 KAKAO_REST_API_KEY가 없어 테스트를 건너뜁니다.")

    # When: 서울 시청 좌표
    results = await search_nearby_restaurants(
        latitude=37.5666,
        longitude=126.9784,
        radius=500,
    )

    # Then
    assert len(results) > 0
    first = results[0]
    assert "name" in first
    assert "address" in first
    assert "road_address" in first
    assert "kakao_id" in first


@pytest.mark.asyncio
async def test_search_nearby_restaurants_no_api_key(monkeypatch):
    """
    API 키 없을 때:
    - 빈 리스트 반환
    """
    # Given
    monkeypatch.setattr(
        "app.services.kakao_map_service.settings.KAKAO_REST_API_KEY", ""
    )

    # When
    results = await search_nearby_restaurants(latitude=37.5666, longitude=126.9784)

    # Then
    assert results == []
