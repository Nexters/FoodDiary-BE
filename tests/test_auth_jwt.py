"""JWT 인증 dependency 테스트"""

import pytest

from app.core.dependencies import get_current_user_id
from app.core.security import create_access_token


class TestJWTDependency:
    """JWT 인증 dependency 단위 테스트"""

    def test_valid_bearer_token(self):
        """유효한 Bearer token에서 user_id 추출 성공"""
        # Given: 유효한 JWT 토큰
        from uuid import uuid4

        user_id = uuid4()
        token = create_access_token(user_id=str(user_id), provider="apple")
        authorization = f"Bearer {token}"

        # When: get_current_user_id 호출
        result = get_current_user_id(authorization)

        # Then: user_id가 올바르게 추출됨
        assert result == user_id

    def test_missing_bearer_prefix(self):
        """Bearer 접두사 없이 토큰만 전달 시 401 에러"""
        from fastapi import HTTPException

        # Given: Bearer 없는 토큰
        token = create_access_token(user_id="test-id", provider="apple")

        # When/Then: HTTPException 발생
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "올바르지 않은 인증 형식입니다"

    def test_invalid_jwt_token(self):
        """유효하지 않은 JWT 토큰 시 401 에러"""
        from fastapi import HTTPException

        # Given: 잘못된 JWT
        authorization = "Bearer invalid_token"

        # When/Then: HTTPException 발생
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(authorization)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "유효하지 않은 토큰입니다"

    def test_case_insensitive_bearer(self):
        """Bearer 대소문자 무관하게 인식"""
        from uuid import uuid4

        # Given: 소문자 "bearer"
        user_id = uuid4()
        token = create_access_token(user_id=str(user_id), provider="google")
        authorization = f"bearer {token}"

        # When: get_current_user_id 호출
        result = get_current_user_id(authorization)

        # Then: 정상 인식
        assert result == user_id

    def test_multiple_spaces_in_header(self):
        """Authorization header에 공백이 여러 개인 경우 401 에러"""
        from fastapi import HTTPException

        # Given: 공백이 여러 개
        authorization = "Bearer  token  extra"

        # When/Then: HTTPException 발생
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(authorization)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "올바르지 않은 인증 형식입니다"

    def test_extract_user_id_from_real_token(self):
        """실제 JWT 토큰에서 user_id 추출 및 검증"""
        from uuid import uuid4

        # Given: 실제 사용자 ID와 JWT 토큰 생성
        original_user_id = uuid4()
        provider = "apple"
        jwt_token = create_access_token(
            user_id=str(original_user_id), provider=provider
        )

        # When: Bearer token으로 포맷하여 user_id 추출
        authorization_header = f"Bearer {jwt_token}"
        extracted_user_id = get_current_user_id(authorization_header)

        # Then: 추출된 user_id가 원본과 일치
        assert extracted_user_id == original_user_id
        assert isinstance(extracted_user_id, type(original_user_id))

    def test_token_payload_contains_correct_claims(self):
        """JWT 토큰에 올바른 클레임이 포함되어 있는지 검증"""
        from uuid import uuid4

        from app.core.security import decode_access_token

        # Given: user_id와 provider로 JWT 생성
        user_id = uuid4()
        provider = "google"
        token = create_access_token(user_id=str(user_id), provider=provider)

        # When: 토큰 디코딩
        payload = decode_access_token(token)

        # Then: payload에 올바른 클레임 포함
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["provider"] == provider
        assert "iat" in payload

    def test_different_users_have_different_tokens(self):
        """서로 다른 사용자는 서로 다른 토큰 및 user_id를 가짐"""
        from uuid import uuid4

        # Given: 두 명의 서로 다른 사용자
        user_id_1 = uuid4()
        user_id_2 = uuid4()

        token_1 = create_access_token(user_id=str(user_id_1), provider="apple")
        token_2 = create_access_token(user_id=str(user_id_2), provider="google")

        # When: 각각의 토큰에서 user_id 추출
        extracted_id_1 = get_current_user_id(f"Bearer {token_1}")
        extracted_id_2 = get_current_user_id(f"Bearer {token_2}")

        # Then: 각 user_id가 원본과 일치하며 서로 다름
        assert extracted_id_1 == user_id_1
        assert extracted_id_2 == user_id_2
        assert extracted_id_1 != extracted_id_2
        assert token_1 != token_2
