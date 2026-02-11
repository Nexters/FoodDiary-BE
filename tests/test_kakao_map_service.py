"""Kakao Map API 서비스 테스트"""

import pytest

from app.services.kakao_map_service import search_nearby_restaurants


@pytest.mark.asyncio
async def test_search_nearby_restaurants_real_location():
    """실제 위치로 음식점 검색 테스트 (스타필드 반경 500m)"""
    latitude = 37.287247
    longitude = 126.991836
    radius = 500

    results = await search_nearby_restaurants(latitude, longitude, radius)

    # 기본 검증
    assert isinstance(results, list)

    # 스타필드 수원은 음식점이 많은 지역이므로 최소 30개 이상 검색되어야 함
    assert len(results) >= 30, f"예상: 30개 이상, 실제: {len(results)}개"

    # 페이지네이션이 동작했는지 확인 (15개 초과)
    assert len(results) > 15, f"페이지네이션 미동작: {len(results)}개"

    # 결과 구조 검증
    first = results[0]
    assert "name" in first
    assert "address" in first
    assert "category" in first
    assert "distance" in first
    assert isinstance(first["distance"], int)

    # 모든 음식점이 반경 내에 있는지 확인
    for restaurant in results:
        distance = restaurant["distance"]
        name = restaurant["name"]
        assert distance <= radius, f"{name}이(가) 반경({radius}m)을 벗어남: {distance}m"
