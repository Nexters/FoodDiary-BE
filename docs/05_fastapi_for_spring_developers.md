# FastAPI for Spring Developers

> Spring Boot (Java/Kotlin) 개발자를 위한 FastAPI 빠른 적응 가이드

## 한줄 요약

**"Spring Boot랑 거의 똑같음. 문법만 다름."**

---

## 패키지 구조 비교

```
FastAPI (Python)              Spring Boot (Kotlin)
─────────────────────────────────────────────────────
app/                          src/main/kotlin/com/example/
├── main.py                   ├── Application.kt
├── routers/                  ├── controller/
├── services/                 ├── service/
├── schemas/                  ├── dto/
├── models/                   ├── entity/
└── core/                     └── config/
```

| FastAPI     | Spring        | 역할                  |
| ----------- | ------------- | --------------------- |
| `routers/`  | `controller/` | API 엔드포인트        |
| `services/` | `service/`    | 비즈니스 로직         |
| `schemas/`  | `dto/`        | Request/Response 객체 |
| `models/`   | `entity/`     | DB 테이블             |
| `core/`     | `config/`     | 설정, 공통 유틸       |

---

## 코드 비교

### 1. Controller (Router)

```kotlin
// Spring Boot (Kotlin)
@RestController
@RequestMapping("/diaries")
class DiaryController(
    private val diaryService: DiaryService
) {
    @PostMapping
    fun create(@RequestBody request: DiaryCreateRequest): DiaryResponse {
        return diaryService.create(request)
    }

    @GetMapping("/{id}")
    fun getById(@PathVariable id: Long): DiaryResponse {
        return diaryService.getById(id)
    }
}
```

```python
# FastAPI (Python)
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/diaries", tags=["Diaries"])

@router.post("")
async def create(
    request: DiaryCreateRequest,
    service: DiaryService = Depends(DiaryService)
) -> DiaryResponse:
    return await service.create(request)

@router.get("/{id}")
async def get_by_id(id: int) -> DiaryResponse:
    return await service.get_by_id(id)
```

**차이점:**

- `@RestController` → `APIRouter()`
- `@PostMapping` → `@router.post()`
- `@RequestBody` → 그냥 파라미터로 받으면 됨
- `@PathVariable` → 함수 파라미터에 같은 이름으로

---

### 2. DTO (Schema)

```kotlin
// Spring Boot (Kotlin)
data class DiaryCreateRequest(
    val photoUrl: String,
    val memo: String? = null
)

data class DiaryResponse(
    val id: Long,
    val foodName: String,
    val location: String?,
    val createdAt: LocalDateTime
)
```

```python
# FastAPI (Python)
from pydantic import BaseModel
from datetime import datetime

class DiaryCreateRequest(BaseModel):
    photo_url: str
    memo: str | None = None

class DiaryResponse(BaseModel):
    id: int
    food_name: str
    location: str | None
    created_at: datetime
```

**차이점:**

- `data class` → `BaseModel` 상속
- `camelCase` → `snake_case`
- `String?` → `str | None`
- 검증은 Pydantic이 자동으로 해줌

---

### 3. Service

```kotlin
// Spring Boot (Kotlin)
@Service
class DiaryService(
    private val diaryRepository: DiaryRepository
) {
    fun create(request: DiaryCreateRequest): DiaryResponse {
        val diary = Diary(
            photoUrl = request.photoUrl,
            memo = request.memo
        )
        val saved = diaryRepository.save(diary)
        return DiaryResponse.from(saved)
    }
}
```

```python
# FastAPI (Python)
class DiaryService:
    def __init__(self):
        pass  # 의존성 주입 (필요시)

    async def create(self, request: DiaryCreateRequest) -> DiaryResponse:
        # 비즈니스 로직
        return DiaryResponse(
            id=1,
            food_name="김치찌개",
            location="서울",
            created_at=datetime.now()
        )
```

**차이점:**

- `@Service` 어노테이션 없음
- 그냥 클래스로 만들면 됨
- `async/await` 사용 (비동기)

---

### 4. 의존성 주입 (DI)

```kotlin
// Spring: 생성자 주입 (자동)
@Service
class DiaryService(
    private val diaryRepository: DiaryRepository
)
```

```python
# FastAPI: Depends() 사용
from fastapi import Depends

@router.post("")
async def create(
    request: DiaryCreateRequest,
    service: DiaryService = Depends(DiaryService)  # 클래스 넘기기
) -> DiaryResponse:
    return await service.create(request)
```

---

### 5. 예외 처리

```kotlin
// Spring
@ResponseStatus(HttpStatus.NOT_FOUND)
class DiaryNotFoundException : RuntimeException("Diary not found")

// 사용
throw DiaryNotFoundException()
```

```python
# FastAPI
from fastapi import HTTPException

# 사용
raise HTTPException(status_code=404, detail="Diary not found")
```

---

## 자주 쓰는 패턴 비교

| 기능         | Spring (Kotlin)             | FastAPI (Python)            |
| ------------ | --------------------------- | --------------------------- |
| GET 파라미터 | `@RequestParam`             | 함수 파라미터               |
| Path 변수    | `@PathVariable`             | 함수 파라미터               |
| Request Body | `@RequestBody`              | Pydantic 모델 파라미터      |
| 응답 상태    | `@ResponseStatus`           | `status_code=` 파라미터     |
| 유효성 검증  | `@Valid`                    | Pydantic 자동               |
| 환경변수     | `@Value`, `application.yml` | `pydantic-settings`, `.env` |

---

## 타입 비교

| Kotlin          | Python       |
| --------------- | ------------ |
| `String`        | `str`        |
| `Int`, `Long`   | `int`        |
| `Double`        | `float`      |
| `Boolean`       | `bool`       |
| `List<T>`       | `list[T]`    |
| `Map<K, V>`     | `dict[K, V]` |
| `T?` (nullable) | `T \| None`  |

---

## 실행 비교

```bash
# Spring Boot
./gradlew bootRun

# FastAPI
uvicorn app.main:app --reload
```

---

## API 문서

- **Spring**: Swagger 설정 필요
- **FastAPI**: 자동 생성! → `http://localhost:8000/docs`

---

## 빠른 시작: 첫 API 만들기

### 1. Router 파일 생성

```python
# app/routers/diaries.py
from datetime import datetime

from fastapi import APIRouter

from app.schemas.diary import DiaryCreate, DiaryResponse

router = APIRouter(prefix="/diaries", tags=["Diaries"])

@router.post("")
async def create_diary(request: DiaryCreate) -> DiaryResponse:
    # TODO: 비즈니스 로직
    return DiaryResponse(
        id=1,
        food_name="테스트",
        location=None,
        created_at=datetime.now()
    )

@router.get("/{diary_id}")
async def get_diary(diary_id: int) -> DiaryResponse:
    # TODO: 조회 로직
    return DiaryResponse(
        id=diary_id,
        food_name="테스트",
        location="서울",
        created_at=datetime.now()
    )
```

### 2. Schema 파일 생성

```python
# app/schemas/diary.py
from datetime import datetime
from pydantic import BaseModel

class DiaryCreate(BaseModel):
    photo_url: str
    memo: str | None = None

class DiaryResponse(BaseModel):
    id: int
    food_name: str
    location: str | None
    created_at: datetime
```

### 3. Router 등록

```python
# app/routers/__init__.py
from app.routers.diaries import router as diaries_router

# app/main.py
app.include_router(diaries_router)
```

### 4. 확인

```bash
uvicorn app.main:app --reload
# http://localhost:8000/docs 에서 확인
```

---

## 핵심 포인트

1. **Spring이랑 구조 똑같음** - 레이어 분리 동일
2. **어노테이션 대신 데코레이터** - `@GetMapping` → `@router.get()`
3. **Pydantic = DTO + Validation** - 알아서 검증해줌
4. **async/await** - 비동기 기본 (Spring WebFlux 느낌)
5. **타입 힌트 필수** - Kotlin처럼 타입 명시

---

## 자주 묻는 질문 (FAQ)

### Q1. Python에서 인터페이스는 안 쓰나요?

**A:** 써도 되는데, 보통 안 씁니다.

Python은 **덕 타이핑(Duck Typing)** 언어라서 인터페이스 없이도 잘 돌아갑니다.

```kotlin
// Kotlin: 인터페이스 필수
interface ImageAnalyzer {
    fun analyze(imageUrl: String): AnalysisResult
}

class OpenAIAnalyzer : ImageAnalyzer {
    override fun analyze(imageUrl: String): AnalysisResult { ... }
}

class GeminiAnalyzer : ImageAnalyzer {
    override fun analyze(imageUrl: String): AnalysisResult { ... }
}
```

```python
# Python: 그냥 같은 메서드 이름으로 구현
class OpenAIAnalyzer:
    def analyze(self, image_url: str) -> AnalysisResult:
        ...

class GeminiAnalyzer:
    def analyze(self, image_url: str) -> AnalysisResult:
        ...

# 둘 다 analyze()가 있으면 갈아끼우기 가능 (덕 타이핑)
```

**굳이 쓰고 싶다면:**

```python
from abc import ABC, abstractmethod

class ImageAnalyzer(ABC):
    @abstractmethod
    def analyze(self, image_url: str) -> AnalysisResult:
        pass

class OpenAIAnalyzer(ImageAnalyzer):
    def analyze(self, image_url: str) -> AnalysisResult:
        ...
```

**MVP에서는 추천하지 않음:**

- 2개월 프로젝트에서는 오버엔지니어링
- 외부 API 갈아끼울 일 거의 없음
- 필요하면 그때 리팩토링해도 늦지 않음

---

## 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Pydantic 공식 문서](https://docs.pydantic.dev/)
