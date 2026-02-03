"""Kakao Map API 연동 서비스"""

import httpx

from app.core.config import settings


async def search_nearby_restaurants(
    latitude: float,
    longitude: float,
    radius: int = 500,
) -> list[dict]:
    """
    GPS 좌표 주변의 음식점을 검색합니다.

    Args:
        latitude: 위도
        longitude: 경도
        radius: 검색 반경 (미터, 기본값 500m)

    Returns:
        list[dict]: 검색된 음식점 목록
            [
                {
                    "name": "식당명",
                    "address": "주소",
                    "category": "카테고리",
                    "distance": 거리(m)
                },
                ...
            ]
    """
    if not settings.KAKAO_REST_API_KEY:
        return []

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {
        "query": "음식점",
        "x": str(longitude),
        "y": str(latitude),
        "radius": radius,
        "category_group_code": "FD6",  # 음식점 카테고리
        "size": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "name": place["place_name"],
                    "address": place["address_name"],
                    "category": place.get("category_name", ""),
                    "distance": int(place.get("distance", 0)),
                }
                for place in data.get("documents", [])
            ]
    except Exception:
        return []  # API 실패 시 빈 리스트 반환
