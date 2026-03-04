import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.oauth2 import TokenVerificationError
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

    original_last_login = existing_user.last_login_at.replace(tzinfo=None)

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
    - 내부 에러 정보는 노출하지 않음
    """

    # Given: Mock Apple token verification to return claims without email
    async def mock_verify_no_email(id_token: str, **kwargs):
        raise TokenVerificationError("필수 클레임 누락: {'email'}")

    monkeypatch.setattr("app.services.oauth2.verify_apple_token", mock_verify_no_email)

    # When: Login with token missing email
    payload = create_login_request_payload()
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response 401 with generic message (no internal error details exposed)
    assert response.status_code == 401
    assert response.json()["detail"] == "인증에 실패했습니다. 다시 시도해 주세요."


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
    from app.services.jwt import decode_access_token

    access_token = response.json()["access_token"]
    decoded = decode_access_token(access_token)

    # Then: Token contains correct claims
    assert decoded is not None
    assert "sub" in decoded  # user_id
    assert "provider" in decoded
    assert decoded["provider"] == "apple"


# ======================
# Google OAuth 테스트
# ======================


@pytest.mark.asyncio
async def test_google_login_new_user_creates_account(
    test_client,
    test_db_session,
    mock_verify_google_token_success,
):
    """
    Google 신규 사용자 로그인 테스트:
    - Google OAuth로 첫 로그인
    - 새 User 레코드 생성
    - is_first=True 반환
    - provider='google' 저장
    """
    # Given: Empty database
    # When: Login with Google
    payload = create_login_request_payload(provider="google", id_token="google_token")
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response success with is_first=True
    assert response.status_code == 200
    data = response.json()
    assert data["is_first"] is True
    assert "access_token" in data
    assert "id" in data

    # Verify new user was created with correct provider
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1

    new_user = users[0]
    assert new_user.provider == "google"
    assert new_user.provider_user_id == "google_user_456"
    assert new_user.email == "test@gmail.com"
    assert new_user.last_login_at is not None


@pytest.mark.asyncio
async def test_google_login_existing_user(
    test_client,
    test_db_session,
    mock_verify_google_token_success,
):
    """
    Google 기존 사용자 로그인 테스트:
    - Google로 이미 가입한 사용자
    - last_login_at 업데이트
    - is_first=False 반환
    """
    # Given: Pre-existing Google user
    user_data = create_test_user_data(
        provider="google",
        provider_user_id="google_user_456",
        email="test@gmail.com",
    )
    existing_user = User(**user_data)
    test_db_session.add(existing_user)
    await test_db_session.commit()

    original_last_login = existing_user.last_login_at.replace(tzinfo=None)

    # When: Login with existing Google account
    payload = create_login_request_payload(provider="google", id_token="google_token")
    response = await test_client.post("/auth/login", json=payload)

    # Then: Success with is_first=False
    assert response.status_code == 200
    data = response.json()
    assert data["is_first"] is False
    assert "access_token" in data

    # Verify last_login_at updated
    result = await test_db_session.execute(
        select(User).where(User.id == existing_user.id)
    )
    updated_user = result.scalars().first()
    assert updated_user.last_login_at > original_last_login


@pytest.mark.asyncio
async def test_google_token_verification_failure(
    test_client,
    test_db_session,
    mock_verify_google_token_failure,
):
    """
    Google 토큰 검증 실패 테스트:
    - 잘못된 Google id_token
    - 401 Unauthorized 응답
    - DB에 변경사항 없음
    """
    # Given: Mock Google token verification failure
    # When: Login with invalid token
    payload = create_login_request_payload(
        provider="google", id_token="invalid_google_token"
    )
    response = await test_client.post("/auth/login", json=payload)

    # Then: Response 401 Unauthorized
    assert response.status_code == 401
    assert "detail" in response.json()

    # Verify no user was created
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 0


@pytest.mark.asyncio
async def test_apple_and_google_users_are_separate(
    test_client,
    test_db_session,
    mock_verify_apple_token_success,
    mock_verify_google_token_success,
):
    """
    Apple과 Google 사용자가 별도로 관리되는지 테스트:
    - 같은 이메일이라도 provider가 다르면 다른 사용자
    - 각각 독립적인 User 레코드 생성
    """
    # Given: Login with Apple
    apple_payload = create_login_request_payload(provider="apple")
    apple_response = await test_client.post("/auth/login", json=apple_payload)
    assert apple_response.status_code == 200
    apple_user_id = apple_response.json()["id"]

    # When: Login with Google (different provider)
    google_payload = create_login_request_payload(provider="google")
    google_response = await test_client.post("/auth/login", json=google_payload)

    # Then: Both succeed and create separate users
    assert google_response.status_code == 200
    google_user_id = google_response.json()["id"]

    # Verify two separate users exist
    result = await test_db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 2

    # Verify they have different IDs
    assert apple_user_id != google_user_id

    # Verify correct providers
    apple_user = next(u for u in users if u.provider == "apple")
    google_user = next(u for u in users if u.provider == "google")
    assert apple_user.provider_user_id == "apple_user_123"
    assert google_user.provider_user_id == "google_user_456"
