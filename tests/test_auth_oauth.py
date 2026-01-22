import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.auth import TokenVerificationError
from tests.fixtures.auth_fixtures import (
    create_login_request_payload,
    create_test_user_data,
)


@pytest.mark.asyncio
async def test_login_existing_user_updates_last_login(
    test_client,
    test_db_session,
    mock_verify_apple_token_success,
):
    """
    기존 사용자 로그인 테스트:
    - User가 이미 DB에 존재
    - verify_oauth_token 성공
    - last_login_at 업데이트
    - is_first=False 반환
    - access_token 생성
    """
    # Given: Pre-populate DB with existing user
    user_data = create_test_user_data()
    existing_user = User(**user_data)
    test_db_session.add(existing_user)
    await test_db_session.commit()

    original_last_login = existing_user.last_login_at

    # When: Login with existing user credentials
    payload = create_login_request_payload()
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response success with is_first=False
    assert response.status_code == 200
    data = response.json()
    assert data["is_first"] is False
    assert "access_token" in data
    assert "id" in data

    # Verify last_login_at was updated
    result = await test_db_session.execute(
        select(User).where(User.id == existing_user.id)
    )
    updated_user = result.scalars().first()
    assert updated_user.last_login_at > original_last_login

    # Verify no new user created
    count_result = await test_db_session.execute(select(User))
    assert len(count_result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_login_new_user_creates_account(
    test_client,
    test_db_session,
    mock_verify_apple_token_success,
):
    """
    신규 사용자 로그인 테스트:
    - User가 DB에 존재하지 않음
    - verify_oauth_token 성공
    - 새 User 레코드 생성
    - is_first=True 반환
    - access_token 생성
    """
    # Given: Empty database (no existing users)
    # (test_db_session is clean by default)

    # When: Login with new user credentials
    payload = create_login_request_payload()
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response success with is_first=True
    assert response.status_code == 200
    data = response.json()
    assert data["is_first"] is True
    assert "access_token" in data
    assert "id" in data

    # Verify new user was created in DB
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1

    new_user = users[0]
    assert new_user.provider == "apple"
    assert new_user.provider_user_id == "apple_user_123"
    assert new_user.email == "test@apple.com"
    assert new_user.last_login_at is not None


@pytest.mark.asyncio
async def test_login_provider_auth_failure_returns_401(
    test_client,
    test_db_session,
    mock_verify_apple_token_failure,
):
    """
    Provider 인증 실패 테스트:
    - verify_oauth_token이 TokenVerificationError 발생
    - 401 Unauthorized 응답
    - DB에 변경사항 없음
    """
    # Given: Mock Apple token verification to fail
    # (mock_verify_apple_token_failure fixture applied)

    # When: Login with invalid token
    payload = create_login_request_payload(id_token="invalid_token")
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response 401 Unauthorized
    assert response.status_code == 401
    assert "detail" in response.json()

    # Verify no user was created
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_login_missing_email_in_claims_fails(
    test_client,
    monkeypatch,
):
    """
    JWT claims 누락 테스트:
    - Apple token에 email 클레임 누락
    - TokenVerificationError 발생
    - 401 Unauthorized 응답
    """

    # Given: Mock Apple token verification to return claims without email
    async def mock_verify_no_email(id_token: str, **kwargs):
        raise TokenVerificationError("필수 클레임 누락: {'email'}")

    monkeypatch.setattr("app.services.auth.verify_apple_token", mock_verify_no_email)

    # When: Login with token missing email
    payload = create_login_request_payload()
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response 401
    assert response.status_code == 401
    assert "필수 클레임 누락" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_returns_valid_jwt_token(
    test_client,
    test_db_session,
    mock_verify_apple_token_success,
):
    """
    생성된 JWT 토큰 검증 테스트:
    - 로그인 성공 후 토큰 발급
    - 토큰 디코딩 가능
    - 올바른 claims 포함 (sub, provider)
    """
    # Given: Successful login
    payload = create_login_request_payload()
    response = await test_client.post("/auth/login", json=payload)
    assert response.status_code == 200

    # When: Decode returned access token
    from app.core.security import decode_access_token

    access_token = response.json()["access_token"]
    decoded = decode_access_token(access_token)

    # Then: Token contains correct claims
    assert decoded is not None
    assert "sub" in decoded  # user_id
    assert "provider" in decoded
    assert decoded["provider"] == "apple"
