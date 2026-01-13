# 코드 컨벤션

## 자동 적용

- **VSCode 저장 시** 자동 포맷팅 (Ruff + Black)
- import 순서도 자동 정렬

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
ruff check app/       # 린트 검사
ruff check app/ --fix # 자동 수정
```
