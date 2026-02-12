from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "FoodDiary API"
    DEBUG: bool = False

    # CORS 설정
    CORS_ORIGINS: list[str] = ["*"]

    # Database 설정
    DATABASE_URL: str = ""

    # API Keys
    # External API Keys
    KAKAO_REST_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Google OAuth 설정 (모바일 앱용)
    GOOGLE_CLIENT_ID: str = ""  # 웹 클라이언트 ID (모바일에서도 사용)
    GOOGLE_ANDROID_CLIENT_ID: str = ""  # 안드로이드 앱 클라이언트 ID

    # Firebase 설정 (모바일 앱용)
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""  # Base64 인코딩된 서비스 계정 JSON

    # Apple OAuth Settings
    APPLE_CLIENT_ID: str = ""
    APPLE_JWK_URL: str = "https://appleid.apple.com/auth/keys"
    APPLE_BASE_URL: str = "https://appleid.apple.com"

    # JWT Settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 0  # 0 = no expiration
    # JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 향후 추가 시


settings = Settings()
