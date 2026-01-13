# 🍽️ FoodDiary Backend

> 사진 한 장으로 완성되는 음식 기록 서비스 — 백엔드 API 서버

## 프로젝트 소개

음식 사진을 업로드하면 기록이 자동으로 완성되는 서비스입니다.

- 📍 **장소 추론**: 사진 메타데이터 + 지도 API
- 🍜 **음식 분석**: 이미지 분석으로 메뉴 인식
- 📝 **기록 자동화**: 날짜, 시간, 메뉴, 장소 자동 입력

## 로컬 실행

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

- Health Check: http://localhost:8000/health
- API 문서: http://localhost:8000/docs

## 프로젝트 구조

```
app/
├── main.py          # 엔트리포인트
├── routers/         # API 라우터
├── services/        # 비즈니스 로직
├── schemas/         # Pydantic 모델
└── core/            # 설정
```

## 문서

- [프로젝트 개요](docs/00_overview.md)
- [협업 원칙](docs/01_collaboration_principles.md)
- [Git & PR 가이드](docs/02_git_pr_guide.md)
- [코드 컨벤션](docs/03_code_conventions.md)
