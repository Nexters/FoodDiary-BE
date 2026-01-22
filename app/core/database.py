from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base

# SQLAlchemy 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # DEBUG 모드일 때만 SQL 쿼리 로그 출력
    pool_pre_ping=True,  # 연결 전 ping으로 연결 상태 확인
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """
    데이터베이스 세션을 생성하고 반환하는 의존성 함수
    FastAPI의 Depends에서 사용
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_tables():
    """모든 테이블 생성"""
    Base.metadata.create_all(bind=engine)
