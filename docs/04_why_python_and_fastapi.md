# Why Python & FastAPI?

> FastAPI를 왜 쓰는지 / 어떻게 쓰는지 / 구조 감각을 한 번에

---

## FastAPI 한 줄 요약

**"타입 힌트로 API 설계를 먼저 하고, 나머지는 자동으로 따라오게 하는 프레임워크"**

---

## 1️⃣ 왜 FastAPI를 쓰는가 (진짜 이유)

FastAPI는 편해서 쓰는 게 아니라 **사고방식이 맞아서** 쓰는 거다.

### FastAPI가 해결하려는 문제

- **API 입력 검증** → 매번 if문 쓰기 싫음
- **문서(Swagger)** → 코드랑 따로 관리하기 싫음
- **API 스펙 변경** → 프론트/백/문서 다 깨지는 거 싫음
- **인증/DB 세션** → 여기저기 복붙하기 싫음

👉 **"사람이 하던 귀찮은 구조 작업을 타입 선언 하나로 끝내자"** 가 핵심

---

## 2️⃣ FastAPI의 핵심 철학 (이거 하나만 기억)

### ✅ 타입 힌트 = API 계약서

```python
def create_user(user: UserCreate) -> UserResponse:
    ...
```

이 한 줄로 FastAPI가 자동으로 하는 것들:

- ✅ 요청 body 파싱
- ✅ 데이터 검증
- ✅ 에러 응답 생성
- ✅ OpenAPI 스펙 생성
- ✅ Swagger 문서 반영

👉 **타입을 쓰는 순간, FastAPI가 "아 이건 계약이구나" 하고 다 처리함**

---

## 3️⃣ FastAPI 구조의 핵심 3요소 (시험 나오면 이거)

### ① Path Operation (라우터 함수)

```python
@router.post("/users")
def create_user(...):
    ...
```

- HTTP 세계의 입구
- **여기서 비즈니스 로직 하면 안 됨**

👉 **역할**: "요청 받고 → 넘기고 → 결과 반환"

---

### ② Pydantic Model (schemas)

```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str
```

- 입력/출력 데이터의 표준
- 검증 + 문서 + 계약을 동시에 책임짐

👉 **FastAPI에서 모델 = 법**

---

### ③ Depends (의존성 주입)

```python
def get_current_user():
    ...

def endpoint(user=Depends(get_current_user)):
    ...
```

**이게 FastAPI의 진짜 핵심임.**

- 인증
- DB 세션
- 권한 체크
- 공통 전처리

👉 **"이 함수 실행하려면 이 조건부터 만족해"를 선언적으로 표현**

---

## 4️⃣ FastAPI를 잘 못 쓰고 있다는 신호 🚨

아래 중 하나라도 많으면 ❌

- ❌ 라우터 함수가 100줄 넘음
- ❌ 라우터 안에서 DB 쿼리 직접 함
- ❌ 인증/권한 로직이 라우터마다 복붙됨
- ❌ `response_model` 안 씀
- ❌ `dict`로 응답 막 반환함

👉 **이 상태면 Flask처럼 쓰고 있는 것**

---

## 5️⃣ FastAPI를 "맞게" 쓰는 기본 규칙 5개

### 규칙 1️⃣ 라우터는 얇게

```python
# ❌ 나쁜 예: 라우터에 비즈니스 로직
@router.post("/users")
def create_user(user: UserCreate):
    if not user.email:
        raise HTTPException(400)
    hashed = hash_password(user.password)
    db_user = User(email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    return db_user

# ⭕ 좋은 예: 라우터는 조립만
@router.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    service: UserService = Depends(get_user_service)
):
    return service.create_user(user)
```

**라우터 = HTTP 담당**  
**서비스 = 비즈니스 로직**

---

### 규칙 2️⃣ request / response 모델은 무조건 만든다

```python
@router.post("/users", response_model=UserResponse)
def create_user(user: UserCreate) -> UserResponse:
    ...
```

- 내부 구현 바뀌어도 API 계약은 유지됨
- Swagger 문서 자동 생성
- 타입 안전성 보장

---

### 규칙 3️⃣ 공통 로직은 Depends로 위로 올린다

```python
# ❌ 나쁜 예: 매번 복붙
@router.get("/diaries")
def get_diaries():
    token = request.headers.get("Authorization")
    user = verify_token(token)
    if not user:
        raise HTTPException(401)
    ...

# ⭕ 좋은 예: Depends 사용
@router.get("/diaries")
def get_diaries(user: User = Depends(get_current_user)):
    ...
```

---

### 규칙 4️⃣ FastAPI는 "조립기"다

**FastAPI가 직접:**

- 비즈니스 판단 ❌
- 데이터 설계 ❌

**FastAPI는:**

- 입력 검증 ✅
- 의존성 조립 ✅
- 실행 흐름 연결 ✅

만 담당

---

### 규칙 5️⃣ 타입이 곧 문서다

```python
@router.post("/diaries", response_model=DiaryResponse)
async def create_diary(
    request: DiaryCreate,
    user: User = Depends(get_current_user),
    service: DiaryService = Depends(get_diary_service)
) -> DiaryResponse:
    """
    음식 일기를 생성합니다.

    - **photo_url**: 음식 사진 URL
    - **memo**: 메모 (선택)
    """
    return await service.create(request, user)
```

- Swagger는 부산물임
- **목적은 안 깨지는 API 계약**

---

## 6️⃣ 가장 무난한 FastAPI 프로젝트 구조

(정답은 없지만 이게 제일 사고 안 남)

```
app/
 ├─ main.py          # app 생성, router 등록
 ├─ routers/         # HTTP 라우터
 ├─ schemas/         # Pydantic 모델
 ├─ services/        # 비즈니스 로직
 ├─ repositories/    # DB 접근
 ├─ deps/            # Depends 모음 (get_db, get_current_user 등)
 └─ core/            # settings, config
```

👉 **핵심은 역할 분리**

- **FastAPI는** `routers` + `deps`
- **진짜 로직은** `services`

---

## 7️⃣ FastAPI를 쓰는 "올바른 마음가짐"

| ❌ 잘못된 생각          | ⭕ 올바른 생각            |
| ----------------------- | ------------------------- |
| "FastAPI 문법을 외우자" | "타입으로 API를 설계하자" |
| "비동기라서 좋다"       | "구조가 강제돼서 좋다"    |
| "Flask보다 빠르다"      | "계약이 깨지지 않는다"    |

---

## 8️⃣ 지금 당장 해보면 좋은 체크리스트 ✅

네 코드에서:

- [ ] `response_model` 없는 엔드포인트 찾기
- [ ] 인증/DB 로직이 라우터에 있으면 `Depends`로 빼기
- [ ] 라우터에서 비즈니스 판단 제거하기
- [ ] `dict` 반환을 Pydantic 모델로 바꾸기
- [ ] 100줄 넘는 라우터 함수 분리하기

---

## 9️⃣ Python을 왜 쓰는가 (FastAPI 전제 지식)

### Python의 3가지 강점

#### 1. 생산성

```python
# Python: 직관적
users = [u for u in all_users if u.is_active]

# Java: 장황함
List<User> users = allUsers.stream()
    .filter(User::isActive)
    .collect(Collectors.toList());
```

#### 2. AI/ML 생태계

```python
# AI 통합이 이렇게 간단
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "음식 이미지 분석해줘"}]
)
```

- OpenAI, Anthropic, Google AI 등 모든 주요 AI 벤더가 Python SDK 우선 지원
- **AI 통합이 필수인 현대 앱에서 Python은 선택이 아닌 필수**

#### 3. 풍부한 라이브러리

```bash
pip install requests        # HTTP 클라이언트
pip install pillow          # 이미지 처리
pip install boto3           # AWS SDK
pip install sqlalchemy      # ORM
```

거의 모든 기능에 대한 검증된 라이브러리가 존재

---

## 🔟 FastAPI vs 다른 프레임워크

### Flask vs FastAPI

```python
# Flask: 모든 걸 수동으로
@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    if not data.get('email'):
        return {'error': 'email required'}, 400
    # ... 검증 로직 더 많음
    return jsonify(user), 201

# FastAPI: 타입만 선언
@router.post("/users", response_model=UserResponse)
def create_user(user: UserCreate):
    return service.create_user(user)
```

| 특징      | Flask     | FastAPI   |
| --------- | --------- | --------- |
| 검증      | 수동      | 자동      |
| 문서      | 별도 작업 | 자동 생성 |
| 비동기    | 제한적    | 네이티브  |
| 타입 안전 | ❌        | ✅        |
| 성능      | 느림      | 빠름      |

---

### Django vs FastAPI

| 특징     | Django      | FastAPI  |
| -------- | ----------- | -------- |
| 목적     | 전통적 웹앱 | API 특화 |
| ORM      | 강제        | 선택     |
| Admin    | 기본 제공   | 없음     |
| 학습곡선 | 높음        | 낮음     |
| 성능     | 느림        | 빠름     |

**선택 기준:**

- 관리자 페이지 필요 → Django
- RESTful API만 필요 → FastAPI

---

## 1️⃣1️⃣ FastAPI 성능이 왜 좋은가?

### 비동기 I/O 덕분

```python
# 동기 방식 (Flask, Django)
def get_data():
    response1 = requests.get("api1")  # 1초 대기 (블로킹)
    response2 = requests.get("api2")  # 1초 대기 (블로킹)
    return [response1, response2]
# 총 2초

# 비동기 방식 (FastAPI)
async def get_data():
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            client.get("api1"),
            client.get("api2")
        )
    return results
# 총 1초 (병렬 실행)
```

### 벤치마크

[TechEmpower 벤치마크](https://www.techempower.com/benchmarks/)에 따르면:

> "FastAPI applications running under Uvicorn as **one of the fastest Python frameworks available**, only below Starlette and Uvicorn themselves (used internally by FastAPI)."
> — [FastAPI 공식 문서](https://fastapi.tiangolo.com/)

```
상대적 성능 비교 (Python 프레임워크):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Starlette/Uvicorn  ████████████████████  (최상위)
FastAPI            ███████████████████   (Starlette 바로 아래)
Flask              ██████████
Django             ████████
```

**FastAPI ≈ Node.js/Go 수준 성능 (공식 문서 명시)**

---

## 1️⃣2️⃣ 언제 FastAPI를 써야 하는가?

### ✅ FastAPI가 적합한 경우

- **RESTful API 구축** (React, Vue 등 SPA와 연동)
- **AI/ML 모델 서빙** (OpenAI, LangChain 통합)
- **마이크로서비스** (빠른 개발 + 높은 성능)
- **스타트업 MVP** (자동 문서화로 협업 용이)
- **실시간 요구사항** (WebSocket 지원)

---

### ❌ FastAPI가 적합하지 않은 경우

- **서버 사이드 렌더링 웹사이트** → Django/Flask
- **관리자 페이지가 필수** → Django
- **매우 단순한 스크립트** → 프레임워크 불필요
- **팀 전체가 Python 경험 전무** → 학습 비용 고려

---

## 1️⃣3️⃣ 실전 예제: 제대로 된 FastAPI 구조

### 파일 구조

```
app/
├── main.py
├── deps/
│   └── auth.py              # get_current_user
├── routers/
│   └── diaries.py           # 라우터 (얇게)
├── schemas/
│   └── diary.py             # Pydantic 모델
├── services/
│   └── diary_service.py     # 비즈니스 로직
└── repositories/
    └── diary_repository.py  # DB 접근
```

---

### 1. Schema (계약 정의)

```python
# app/schemas/diary.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DiaryCreate(BaseModel):
    photo_url: str
    memo: str | None = None

class DiaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2 문법

    id: int
    food_name: str
    location: str | None
    created_at: datetime
```

---

### 2. Dependency (공통 로직)

```python
# app/deps/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    user = await verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return user
```

---

### 3. Service (비즈니스 로직)

```python
# app/services/diary_service.py
from app.schemas.diary import DiaryCreate, DiaryResponse

class DiaryService:
    def __init__(self, repository: DiaryRepository):
        self.repository = repository

    async def create(
        self,
        data: DiaryCreate,
        user: User
    ) -> DiaryResponse:
        # 비즈니스 로직
        if not data.photo_url:
            raise ValueError("사진은 필수입니다")

        # AI 분석 (예시)
        food_name = await analyze_food_image(data.photo_url)

        # DB 저장
        diary = await self.repository.create(
            user_id=user.id,
            photo_url=data.photo_url,
            food_name=food_name,
            memo=data.memo
        )

        return DiaryResponse.model_validate(diary)  # Pydantic v2 문법
```

---

### 4. Router (조립만)

```python
# app/routers/diaries.py
from fastapi import APIRouter, Depends
from app.deps.auth import get_current_user
from app.schemas.diary import DiaryCreate, DiaryResponse
from app.services.diary_service import DiaryService

router = APIRouter(prefix="/diaries", tags=["Diaries"])

@router.post("", response_model=DiaryResponse)
async def create_diary(
    data: DiaryCreate,
    user: User = Depends(get_current_user),
    service: DiaryService = Depends(get_diary_service)
) -> DiaryResponse:
    """음식 일기를 생성합니다."""
    return await service.create(data, user)

@router.get("/{diary_id}", response_model=DiaryResponse)
async def get_diary(
    diary_id: int,
    user: User = Depends(get_current_user),
    service: DiaryService = Depends(get_diary_service)
) -> DiaryResponse:
    """음식 일기를 조회합니다."""
    return await service.get_by_id(diary_id, user)
```

**라우터 특징:**

- 20줄 이내로 간결
- 비즈니스 로직 없음
- 타입 안전 (response_model 명시)
- Depends로 의존성 주입

---

### 5. Main (앱 조립)

```python
# app/main.py
from fastapi import FastAPI
from app.routers import diaries

app = FastAPI(
    title="FoodDiary API",
    description="음식 일기 서비스",
    version="1.0.0"
)

app.include_router(diaries.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

---

## 1️⃣4️⃣ 핵심 정리

### FastAPI를 한 문장으로

> **"타입 힌트로 API 계약을 정의하면, 검증/문서/에러처리가 자동으로 따라온다"**

### 기억할 3가지

1. **타입 = 계약서**: Pydantic 모델로 입출력 정의
2. **Depends = 공통 로직**: 인증/DB/권한은 Depends로
3. **라우터는 얇게**: 조립만 하고 로직은 Service로

### 지금 바로 시작하기

```bash
# 설치 (표준 의존성 포함 - 공식 권장)
pip install "fastapi[standard]"

# 실행 (최신 방식)
fastapi dev app/main.py

# 또는 기존 방식
uvicorn app.main:app --reload

# 문서 확인
open http://localhost:8000/docs
```

**5분이면 첫 API를 만들 수 있습니다.**

---

## 1️⃣5️⃣ 다음 단계

### 이 문서를 읽었다면

- ✅ FastAPI를 **왜** 쓰는지 이해
- ✅ FastAPI를 **어떻게** 쓰는지 감각 습득
- ✅ 올바른 **구조**를 잡을 수 있음

---

## 참고 자료

### 공식 문서

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/) - 이 문서의 주요 출처
- [FastAPI Features](https://fastapi.tiangolo.com/features/) - 핵심 기능 설명
- [Pydantic 공식 문서](https://docs.pydantic.dev/) - 데이터 검증 라이브러리

### 벤치마크

- [TechEmpower 벤치마크](https://www.techempower.com/benchmarks/)
- [FastAPI Benchmarks](https://fastapi.tiangolo.com/benchmarks/) - 공식 벤치마크 페이지

### 공식 수치 출처 (FastAPI 공식 문서)

| 주장                         | 출처                                                 | 비고          |
| ---------------------------- | ---------------------------------------------------- | ------------- |
| "200% ~ 300% 개발 속도 향상" | [FastAPI 메인 페이지](https://fastapi.tiangolo.com/) | \*추정치      |
| "40% 버그 감소"              | [FastAPI 메인 페이지](https://fastapi.tiangolo.com/) | \*추정치      |
| "Node.js, Go 수준 성능"      | [FastAPI 메인 페이지](https://fastapi.tiangolo.com/) | 벤치마크 기반 |

> **참고**: \*가 붙은 수치는 FastAPI 제작팀의 내부 추정치입니다.

---

## 확인 질문 🤔

이 문서를 제대로 이해했는지 스스로 점검:

**Q: "FastAPI에서 타입 힌트가 왜 중요한지 한 문장으로 말해보세요"**

<details>
<summary>정답 보기</summary>

**A: "타입 힌트가 API 계약이 되어, 검증/문서/에러처리가 자동으로 생성되기 때문"**

또는

**A: "타입을 쓰는 순간 FastAPI가 API 스펙으로 인식하고 모든 부수 작업을 자동화하기 때문"**

</details>
