from pydantic import BaseModel, EmailStr


class GoogleIdTokenRequest(BaseModel):
    """안드로이드/iOS에서 Google Sign-In으로 받은 id_token"""

    id_token: str


class GoogleUserInfo(BaseModel):
    """Google OAuth에서 받아오는 사용자 정보"""

    id: str
    email: EmailStr
    verified_email: bool
    name: str
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None


class TokenResponse(BaseModel):
    """JWT 토큰 응답"""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """사용자 정보 응답"""

    id: str
    email: EmailStr
    name: str
    picture: str | None = None


class AuthCallbackResponse(BaseModel):
    """OAuth 콜백 응답"""

    user: UserResponse
    token: TokenResponse
