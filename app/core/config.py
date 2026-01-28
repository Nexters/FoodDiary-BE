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
    OPENAI_API_KEY: str = ""

    # Google OAuth 설정
    GOOGLE_CLIENT_ID: str = ""  # 웹/백엔드용
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # 안드로이드 앱 클라이언트 ID (id_token 검증 시 허용)
    GOOGLE_ANDROID_CLIENT_ID: str = ""

    # JWT 설정
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7일

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
