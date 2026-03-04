"""JWT 인증 dependency 테스트"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dependencies import get_current_user_id
from app.services.jwt import create_access_token, decode_access_token


def make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


class TestJWTDependency:
    """JWT 인증 dependency 단위 테스트"""

    def test_valid_bearer_token(self):
        """유효한 Bearer token에서 user_id 추출 성공"""
        user_id = uuid4()
        token = create_access_token(user_id=str(user_id), provider="apple")

        result = get_current_user_id(make_credentials(token))

        assert result == user_id

    def test_invalid_jwt_token(self):
        """유효하지 않은 JWT 토큰 시 401 에러"""
        credentials = make_credentials("invalid_token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "유효하지 않은 토큰입니다"

    def test_token_payload_contains_correct_claims(self):
        """JWT 토큰에 올바른 클레임이 포함되어 있는지 검증"""
        user_id = uuid4()
        provider = "google"

        token = create_access_token(user_id=str(user_id), provider=provider)
        payload = decode_access_token(token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["provider"] == provider
        assert "iat" in payload

    def test_different_users_have_different_tokens(self):
        """서로 다른 사용자는 서로 다른 토큰 및 user_id를 가짐"""
        user_id_1 = uuid4()
        user_id_2 = uuid4()

        token_1 = create_access_token(user_id=str(user_id_1), provider="apple")
        token_2 = create_access_token(user_id=str(user_id_2), provider="google")

        extracted_id_1 = get_current_user_id(make_credentials(token_1))
        extracted_id_2 = get_current_user_id(make_credentials(token_2))

        assert extracted_id_1 == user_id_1
        assert extracted_id_2 == user_id_2
        assert extracted_id_1 != extracted_id_2
        assert token_1 != token_2
