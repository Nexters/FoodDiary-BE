"""LLM 서비스 - Gemini API를 사용한 음식 이미지 분석 및 블로그 글 생성."""

import asyncio
import io
import json
import logging
import re

import aiofiles
import google.generativeai as genai
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gemini API 설정
genai.configure(api_key=settings.GEMINI_API_KEY)

# 끼니 타입 한글 매핑
TIME_TYPE_KO = {
    "breakfast": "아침",
    "lunch": "점심",
    "dinner": "저녁",
    "snack": "간식",
}


async def analyze_food_images(
    image_paths: list[str],
    restaurant_candidates: list[dict],
) -> list[dict]:
    """
    같은 끼니의 음식 사진 여러 장을 한 번에 분석합니다.

    Args:
        image_paths: 분석할 이미지 파일 경로 목록
        restaurant_candidates: Kakao Map에서 조회한 주변 식당 후보 목록
            [{"name": str, "url": str, "road_address": str, ...}, ...]

    Returns:
        list[dict]: 분석 결과 객체 배열 (최대 5개)
            각 객체: {restaurant_name, restaurant_url, road_address,
                tags, category, memo} — restaurant 필드는 후보 원본 그대로 사용
    """
    try:
        # 이미지 로드 및 리사이즈
        image_parts = []
        for path in image_paths:
            async with aiofiles.open(path, "rb") as f:
                raw = await f.read()
            resized = _resize_image_bytes(raw)
            image_parts.append({"mime_type": "image/jpeg", "data": resized})

        model = genai.GenerativeModel("gemini-2.5-flash")

        _cats = "korean, chinese, japanese, western, etc, home_cooked"

        if restaurant_candidates:
            restaurant_list = "\n".join(
                f"- name:{r['name']}"
                f" url:{r.get('url', '')}"
                f" road_address:{r.get('road_address', '')}"
                f" category:{r.get('category', '')}"
                for r in restaurant_candidates
            )
            n = min(len(restaurant_candidates), 5)
            restaurant_section = (
                f"주변 식당 후보 {len(restaurant_candidates)}개"
                " (name/url/road_address/category 값은 반드시 원본 그대로 사용):\n"
                f"{restaurant_list}\n\n"
                f"사진과 어울리는 순으로 정확히 {n}개를 배열로 반환."
                " 각 후보마다 객체 1개씩."
            )
        else:
            restaurant_section = (
                "주변 식당 정보 없음."
                " restaurant_name/restaurant_url/road_address는 null."
                f" category는 반드시 다음 6개 중 하나 → {_cats}."
                " 객체 1개만 반환."
            )

        prompt = (
            f"같은 끼니 사진 {len(image_parts)}장 분석. JSON 배열만 출력.\n"
            f"{restaurant_section}\n\n"
            "각 객체 필드:\n"
            "  restaurant_name: 식당명 (후보에서 선택, 없으면 null)\n"
            "  restaurant_url: 식당 URL (후보 원본 그대로, 없으면 null)\n"
            "  road_address: 도로명 주소 (후보 원본 그대로, 없으면 null)\n"
            "  tags: 메뉴명·키워드 통합 리스트 (사진에서 보이는 것만)\n"
            f"  category: 반드시 다음 6개 중 하나만 사용 → {_cats}\n"
            "    (후보 식당 category 참고해 분류. 집밥→home_cooked, 분류 불명→etc)\n"
            "  memo: AI 브리핑 3~5줄"
            " (도입 한 줄 + 불릿 3~5개, 없는 내용 지어내지 말 것)\n\n"
            f"출력 예시 (후보 {min(len(restaurant_candidates), 5)}개 반환하는 경우):\n"
            "["
            + ",".join(
                f'{{"restaurant_name":"{chr(65+i)}식당",'
                f'"restaurant_url":"https://...",'
                f'"road_address":"서울...",'
                f'"tags":["메뉴{i+1}"],'
                f'"category":"etc",'
                f'"memo":"..."}}'
                for i in range(min(len(restaurant_candidates), 5))
            )
            + "]"
        )

        response = model.generate_content([*image_parts, prompt])

        response_text = _extract_json_text(response.text.strip())
        result = json.loads(response_text)

        if not isinstance(result, list):
            result = []

        logger.info(f"그룹 LLM 분석 완료: {len(image_paths)}장, 후보 {len(result)}개")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"그룹 LLM 응답 JSON 파싱 실패: {e}")
        raise
    except FileNotFoundError as e:
        logger.error(f"이미지 파일을 찾을 수 없음: {e}")
        raise
    except Exception as e:
        logger.error(f"그룹 LLM 분석 실패: {e}")
        raise


async def generate_blog_text(diary_info: dict) -> str:
    """
    다이어리 정보로 네이버 맛집 블로그 스타일 글을 생성합니다.

    Args:
        diary_info: 다이어리 정보 딕셔너리
            (식당명, 주소, 카테고리, 메모, 태그, 날짜, 끼니, URL 등)

    Returns:
        str: 생성된 블로그 본문 텍스트

    Raises:
        Exception: Gemini API 호출 실패 시
    """
    return await asyncio.to_thread(_generate_blog_text_sync, diary_info)


def _generate_blog_text_sync(diary_info: dict) -> str:
    """
    다이어리 정보로 네이버 맛집 블로그 스타일 글을 동기 생성합니다.
    (Gemini SDK가 동기이므로 이 함수를 asyncio.to_thread로 호출)
    """
    model = genai.GenerativeModel("gemini-2.5-flash")

    restaurant_name = diary_info.get("restaurant_name") or "이름 없는 맛집"
    road_address = diary_info.get("road_address") or ""
    category = diary_info.get("category") or "음식"
    note = diary_info.get("note") or ""
    tags = diary_info.get("tags") or []
    diary_date = diary_info.get("diary_date") or ""
    time_type_ko = diary_info.get("time_type_ko") or "식사"
    restaurant_url = diary_info.get("restaurant_url") or ""

    tags_str = ", ".join(tags) if tags else "없음"
    prompt = (
        "다음 맛집 다이어리 정보를 바탕으로, "
        "네이버 맛집 블로그처럼 **섹션별로 정리된** 포스팅 본문을 작성해주세요.\n\n"
        "**다이어리 정보:**\n"
        f"- 식당명: {restaurant_name}\n"
        f"- 주소: {road_address or '정보 없음'}\n"
        f"- 카테고리: {category}\n"
        f"- 방문 시기: {diary_date} {time_type_ko}\n"
        f"- note(식당 요약 정보, 반드시 활용): {note or '없음'}\n"
        f"- 태그(메뉴/키워드): {tags_str}\n"
        f"- 지도/링크: {restaurant_url or '없음'}\n\n"
        "**중요:** note는 해당 식당에 대한 요약된 정보이므로, 장소·메뉴·방문 후기 등 "
        "본문 여러 섹션에 반드시 녹여서 활용하세요. 단순 나열 금지.\n\n"
        "**아래 형식으로 섹션 나눠 작성. 각 섹션 본문다운 분량으로:**\n\n"
        "■ 장소\n"
        "식당명·주소·지도 링크 안내 후, 위치·찾아가기·매장 분위기를 "
        "2~4문장으로 서술.\n\n"
        "■ 가격정보\n"
        "가격 있으면 구체적으로, 없으면 '방문 시 확인 추천' 등 한 줄.\n\n"
        "■ 메뉴 / 추천메뉴\n"
        "태그·메모에 나온 메뉴 나열 후, 먹어본 메뉴는 맛·특징 1~2문장씩. "
        "전체 3~6문장.\n\n"
        "■ 방문 후기\n"
        "방문 동기·분위기·맛 평가·총평을 **4~7문장**으로 구체적으로. "
        "블로그 리뷰처럼 읽을 만한 분량으로.\n\n"
        "**포맷(네이버 블로그 복붙용):**\n"
        "- 섹션 제목(■ 장소 등)은 반드시 한 줄에만 쓰고, 그 다음 줄은 비우고, "
        "그 다음 줄부터 본문 작성.\n"
        "- 단락과 단락 사이에는 빈 줄 하나 넣기. (복붙 시 네이버 블로그에서 "
        "단락 구분이 예쁘게 보이도록)\n"
        "- 출력에는 마크다운(**), 이모지, # 등 사용 금지. 순수 텍스트+줄바꿈만.\n\n"
        "**규칙:** 제목 없이 본문만. 각 섹션 충분히 풀어서 작성."
    )

    response = model.generate_content(prompt)
    text = (response.text or "").strip()
    # 복붙 시 네이버 블로그에서 깔끔하게 보이도록 후처리
    text = _normalize_blog_text_for_paste(text)
    return text


def _normalize_blog_text_for_paste(text: str) -> str:
    """
    복사·붙여넣기 시 네이버 블로그에서 줄바꿈·단락이 제대로 보이도록 정규화.
    - 마크다운 기호 제거
    - 줄바꿈 통일 (\\r\\n, \\r → \\n)
    - 섹션 제목(■ ...) 앞뒤로 빈 줄 보장 (\\n\\n)
    - 연속 빈 줄은 최대 2개로
    """
    for char in ("**", "__", "#"):
        text = text.replace(char, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 섹션 제목(■ ...) 앞에 빈 줄 하나 보장
    text = re.sub(r"\n(■ [^\n]+)", r"\n\n\1", text)
    # 섹션 제목 다음에 빈 줄 하나 보장
    text = re.sub(r"(■ [^\n]+)\n", r"\1\n\n", text)
    # 연속 개행 3개 이상을 \n\n 로
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_json_text(response_text: str) -> str:
    """Gemini 응답에서 JSON 텍스트만 추출합니다."""
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        return response_text[start:end].strip()
    if "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        return response_text[start:end].strip()
    return response_text


def _resize_image_bytes(data: bytes, max_size: int = 1024) -> bytes:
    """장축을 max_size px로 리사이즈하여 JPEG bytes 반환 (원본 비율 유지)."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
