# 코드 컨벤션

## 자동 적용

- **VSCode 저장 시** 자동 포맷팅 + import 정렬 + lint 자동 수정 (Ruff)
- 포맷터 / 린터 / import 정렬 모두 **Ruff 하나**로 통합 (Black, isort 미사용)

## 지켜야 할 것

| 규칙                   | 예시                                  |
| ---------------------- | ------------------------------------- |
| 함수/변수는 snake_case | `get_user()`, `user_name`             |
| 클래스는 PascalCase    | `UserService`, `DiaryResponse`        |
| 상수는 UPPER_CASE      | `MAX_FILE_SIZE`                       |
| **타입 힌트 필수**     | `def get_user(user_id: int) -> User:` |

## 타입 힌트 예시

```python
# ✅ 이렇게
def create_diary(
    user_id: int,
    photo_url: str,
    location: str | None = None,
) -> DiaryResponse:
    ...

# ❌ 이거 말고
def create_diary(user_id, photo_url, location=None):
    ...
```

## 수동 검사 (필요시)

```bash
ruff check app/        # 린트 검사
ruff check app/ --fix  # 린트 자동 수정 (import 정렬 포함)
ruff format app/       # 포맷팅
```
