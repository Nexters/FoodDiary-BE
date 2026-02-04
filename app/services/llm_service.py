"""LLM 서비스 - Gemini API를 사용한 음식 이미지 분석."""

import json
import logging

import aiofiles
import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Gemini API 설정
genai.configure(api_key=settings.GEMINI_API_KEY)


async def analyze_food_image(image_path: str) -> dict:
    """
    음식 이미지를 분석하여 음식 정보를 추출합니다.

    Args:
        image_path: 분석할 이미지 파일 경로

    Returns:
        dict: 분석 결과 (food_category, menus, keywords)
    """
    default_result = {
        "food_category": "기타",
        "menus": [],
        "keywords": [],
    }

    try:
        # 이미지 파일 로드
        async with aiofiles.open(image_path, "rb") as f:
            image_data = await f.read()

        # Gemini 모델 설정 (gemini-2.0-flash 사용)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # 프롬프트 작성
        prompt = """이 음식 사진을 분석해서 다음 정보를 JSON 형식으로 추출해주세요:

1. food_category: 음식 카테고리
   (한식, 중식, 일식, 양식, 분식, 카페/디저트, 패스트푸드, 기타 중 하나)
2. menus: 사진에 보이는 메뉴 이름들 (리스트)
3. keywords: 이 음식을 설명하는 키워드들 (예: 매운맛, 건강식, 고단백 등) (리스트)

반드시 아래 JSON 형식으로만 응답해주세요:
{
    "food_category": "카테고리",
    "menus": ["메뉴1", "메뉴2"],
    "keywords": ["키워드1", "키워드2"]
}"""

        # API 호출
        response = model.generate_content(
            [
                {"mime_type": "image/jpeg", "data": image_data},
                prompt,
            ]
        )

        # 응답 파싱
        response_text = response.text.strip()

        # JSON 블록 추출 (```json ... ``` 형식 처리)
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        result = json.loads(response_text)

        # 필수 필드 검증
        if "food_category" not in result:
            result["food_category"] = "기타"
        if "menus" not in result:
            result["menus"] = []
        if "keywords" not in result:
            result["keywords"] = []

        logger.info(f"LLM 분석 완료: {image_path}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"LLM 응답 JSON 파싱 실패: {e}")
        return default_result
    except FileNotFoundError:
        logger.error(f"이미지 파일을 찾을 수 없음: {image_path}")
        return default_result
    except Exception as e:
        logger.error(f"LLM 분석 실패: {e}")
        return default_result
