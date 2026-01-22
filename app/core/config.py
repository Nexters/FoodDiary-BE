from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FoodDiary API"
    DEBUG: bool = False

    # CORS 설정
    CORS_ORIGINS: list[str] = ["*"]

    # Database 설정
    DATABASE_URL: str = ""

    # API Keys
    KAKAO_REST_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Apple OAuth Settings
    APPLE_CLIENT_ID: str = ""
    APPLE_JWK_URL: str = "https://appleid.apple.com/auth/keys"
    APPLE_BASE_URL: str = "https://appleid.apple.com"

    # JWT Settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 0  # 0 = no expiration
    # JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 향후 추가 시

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
