# 🍽️ FoodDiary Backend

> 사진 한 장으로 완성되는 음식 기록 서비스 — 백엔드 API 서버

## 프로젝트 소개

음식 사진을 업로드하면 기록이 자동으로 완성되는 서비스입니다.

- 📍 **장소 추론**: 사진 메타데이터 + 지도 API
- 🍜 **음식 분석**: 이미지 분석으로 메뉴 인식
- 📝 **기록 자동화**: 날짜, 시간, 메뉴, 장소 자동 입력

## 로컬 실행

### Docker 사용 (권장)

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 필요한 값 수정 (API 키, DB 비밀번호 등)

# 2. 컨테이너 실행
docker-compose -f docker/docker-compose.local.yml up -d

# 3. 로그 확인
docker-compose -f docker/docker-compose.local.yml logs -f api

# 4. 종료
docker-compose -f docker/docker-compose.local.yml down
```

### Python 직접 실행

```bash
# 1. 가상환경
python -m venv .venv
source .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수
cp .env.example .env

# 4. 서버 실행
uvicorn app.main:app --reload
```

### 접속 주소

- Health Check: http://localhost:8000/health
- API 문서: http://localhost:8000/docs

## 데이터베이스

### DB 초기화

PostgreSQL 데이터베이스를 Docker로 실행하고 초기화합니다:

```bash
# 1. PostgreSQL 컨테이너 실행
docker-compose -f docker/docker-compose.local.yml up -d db

# 2. DB 초기화 스크립트 실행
docker exec -i fooddiary-db psql -U fooddiary_user -d fooddiary < scripts/init-db.sql

# 3. 테이블 확인
docker exec fooddiary-db psql -U fooddiary_user -d fooddiary -c "\dt"
```

### DB 스키마 구조

#### 주요 테이블

| 테이블                   | 설명                                | 주요 필드                   |
| ------------------------ | ----------------------------------- | --------------------------- |
| `users`                  | Google/Apple OAuth 사용자 정보      | provider_user_id (OAuth ID) |
| `diaries`                | 끼니별 일기 (아침/점심/저녁/간식)   | diary_date, photo_count     |
| `diary_analysis`         | 다이어리 단위 AI 추론 결과 (후보)   | restaurant_candidates       |
| `photos`                 | 업로드된 사진 정보 (EXIF, GPS 포함) | taken_at, taken_location    |
| `photo_analysis_results` | 사진별 AI 분석 결과 (후보)          | keywords, menu_candidates   |

#### 관계도

```
User (1) ─────────── (N) Diary
                          │
                          ├─── (1:1) DiaryAnalysis
                          │
                          └─── (N) Photo
                                 │
                                 └─── (1:1) PhotoAnalysisResult
```

### SQLAlchemy 모델

모든 모델은 `app/models/`에 정의되어 있습니다:

```python
from app.models import (
    User,                    # 사용자
    Diary,                   # 일기
    DiaryAnalysis,           # 일기 AI 분석
    Photo,                   # 사진
    PhotoAnalysisResult,     # 사진 AI 분석
)
```

### DB 접속 정보

```
Host: localhost
Port: 5432
Database: fooddiary
User: fooddiary_user
Password: fooddiary1234
```

> ⚠️ 운영 환경에서는 반드시 `.env` 파일의 비밀번호를 변경하세요!

## 프로젝트 구조

```
FoodDiary-BE/
├── app/
│   ├── main.py              # FastAPI 앱 엔트리포인트
│   ├── core/                # 핵심 설정
│   │   ├── config.py        # 환경변수 설정
│   │   ├── database.py      # DB 연결 및 세션 관리
│   │   ├── security.py      # JWT 인증
│   │   └── dependencies.py  # 공통 의존성
│   ├── models/              # SQLAlchemy ORM 모델
│   │   ├── user.py          # User
│   │   ├── diary.py         # Diary, DiaryAnalysis
│   │   └── photo.py         # Photo, PhotoAnalysisResult
│   ├── schemas/             # Pydantic 스키마 (Request/Response)
│   │   ├── auth.py
│   │   ├── diary.py
│   │   └── photo.py
│   ├── routers/             # API 엔드포인트
│   │   ├── auth.py          # 인증 (OAuth, JWT)
│   │   ├── diaries.py       # 일기 CRUD
│   │   └── photos.py        # 사진 업로드/분석
│   └── services/            # 비즈니스 로직
│       ├── auth.py          # 인증 처리
│       ├── diary_service.py # 일기 관리
│       ├── photo_service.py # 사진 처리 (EXIF, S3)
│       └── analysis_service.py # AI 분석 (LLM, Kakao Map)
├── scripts/
│   └── init-db.sql          # DB 초기화 스크립트
├── tests/                   # 테스트 코드
├── docker/                  # Docker 설정
│   └── docker-compose.local.yml
└── docs/                    # 문서
    └── 설계/
        └── DB_API설계.md
```

## 문서

### 협업 가이드

- [프로젝트 개요](docs/00_overview.md)
- [협업 원칙](docs/01_collaboration_principles.md)
- [Git & PR 가이드](docs/02_git_pr_guide.md)
- [코드 컨벤션](docs/03_code_conventions.md)
- [Python & FastAPI 가이드](docs/04_why_python_and_fastapi.md)
- [Spring 개발자를 위한 FastAPI](docs/05_fastapi_for_spring_developers.md)

### 설계 문서

- [DB & API 설계](docs/설계/DB_API설계.md)
- [개발 작업 플로우](docs/설계/개발_작업_플로우.md) ⭐ 단계별 구현 가이드
