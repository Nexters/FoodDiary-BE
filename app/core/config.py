from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FoodDiary API"
    DEBUG: bool = False

    # CORS 설정
    CORS_ORIGINS: list[str] = ["*"]

    KAKAO_REST_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra="ignore"  


settings = Settings()
