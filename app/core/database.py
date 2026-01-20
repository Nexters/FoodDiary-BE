from sqlmodel import Session, create_engine

from app.core.config import settings

# SQLModel 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # DEBUG 모드일 때만 SQL 쿼리 로그 출력
    pool_pre_ping=True,  # 연결 전 ping으로 연결 상태 확인
)


def get_session():
    """
    데이터베이스 세션을 생성하고 반환하는 의존성 함수
    FastAPI의 Depends에서 사용
    """
    with Session(engine) as session:
        yield session
