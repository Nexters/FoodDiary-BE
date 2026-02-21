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

    Kakao API 제약:
    - 페이지당 최대 15개 결과
    - 최대 45페이지까지 조회 가능 (총 675개)
    - 페이지네이션을 통해 가능한 모든 결과를 수집

    Args:
        latitude: 위도
        longitude: 경도
        radius: 검색 반경 (미터, 기본값 500m)

    Returns:
        list[dict]: 검색된 음식점 목록 (최대 675개)
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
    base_params = {
        "query": "음식점",
        "x": str(longitude),
        "y": str(latitude),
        "radius": radius,
        "category_group_code": "FD6",  # 음식점 카테고리
        "size": 15,  # 페이지당 최대 결과 수
    }

    all_restaurants = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for page in range(1, 46):  # 최대 45페이지
                params = {**base_params, "page": page}
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                documents = data.get("documents", [])
                if not documents:
                    break  # 더 이상 결과가 없으면 중단

                restaurants = [
                    {
                        "name": place["place_name"],
                        "address": place["address_name"],
                        "road_address": place.get("road_address_name", ""),
                        "kakao_id": place.get("id", ""),
                        "category": place.get("category_name", ""),
                        "distance": int(place.get("distance", 0)),
                    }
                    for place in documents
                ]
                all_restaurants.extend(restaurants)

                # 마지막 페이지인지 확인
                meta = data.get("meta", {})
                if meta.get("is_end", True):
                    break

            return all_restaurants
    except Exception:
        return []  # API 실패 시 빈 리스트 반환


async def search_restaurants_by_keyword(
    keyword: str,
    page: int = 1,
    size: int = 15,
) -> dict:
    """
    키워드로 음식점을 검색합니다.

    Args:
        keyword: 검색 키워드 (음식점 이름)
        page: 페이지 번호 (1~45)
        size: 페이지당 결과 수 (1~15)

    Returns:
        dict: {"restaurants": [...], "total_count": int, "is_end": bool}
    """
    if not settings.KAKAO_REST_API_KEY:
        return {"restaurants": [], "total_count": 0, "is_end": True}

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {
        "query": keyword,
        "category_group_code": "FD6",
        "page": page,
        "size": size,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            documents = data.get("documents", [])
            meta = data.get("meta", {})

            restaurants = [
                {
                    "name": place["place_name"],
                    "road_address": place.get("road_address_name", ""),
                    "url": place.get("place_url", ""),
                    "category": place.get("category_name", "").split(" > ")[-1],
                }
                for place in documents
            ]

            return {
                "restaurants": restaurants,
                "total_count": meta.get("total_count", 0),
                "is_end": meta.get("is_end", True),
            }
    except Exception:
        return {"restaurants": [], "total_count": 0, "is_end": True}
