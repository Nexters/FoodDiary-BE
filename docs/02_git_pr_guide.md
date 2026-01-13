# Git & Pull Request 가이드

## 브랜치 전략

### 브랜치 구조

```
main (프로덕션)
 └── feat/feature-name (기능 개발)
 └── fix/bug-description (버그 수정)
 └── refactor/description (리팩토링)
```

### 규칙

- `main`: 항상 실행 가능한 상태 유지
- 기능 단위로 브랜치 생성 후 PR로 병합

### 브랜치 네이밍

```
feat/photo-upload          # 기능 개발
feat/place-inference       # 기능 개발
fix/image-analysis-error   # 버그 수정
refactor/service-layer     # 리팩토링
docs/api-documentation     # 문서 작업
chore/dependency-update    # 설정/의존성
```

---

## 커밋 컨벤션

### 형식

```
<type>: <subject>

[optional body]
```

### Type 종류

| Type       | 설명        | 예시                                  |
| ---------- | ----------- | ------------------------------------- |
| `feat`     | 새로운 기능 | `feat: 사진 업로드 API 구현`          |
| `fix`      | 버그 수정   | `fix: 이미지 분석 타임아웃 오류 해결` |
| `refactor` | 리팩토링    | `refactor: 서비스 레이어 구조 개선`   |
| `docs`     | 문서 수정   | `docs: API 문서 업데이트`             |
| `test`     | 테스트 코드 | `test: 다이어리 생성 테스트 추가`     |
| `chore`    | 빌드/설정   | `chore: Ruff 설정 추가`               |
| `style`    | 코드 포맷팅 | `style: Black 포맷팅 적용`            |

### 좋은 커밋 메시지 예시

```bash
# ✅ 좋은 예시
feat: 음식 사진 업로드 API 구현

- POST /photos 엔드포인트 추가
- 이미지 파일 검증 로직 구현
- S3 업로드 서비스 연동

# ✅ 좋은 예시
fix: 장소 추론 실패 시 예외 처리

추론 결과가 없을 때 500 에러 대신
빈 결과를 반환하도록 수정

# ❌ 나쁜 예시
update
수정
wip
asdf
```

### 커밋 단위

- **의미 있는 단위**로 커밋
- 하나의 커밋은 하나의 논리적 변경을 담음
- "동작하는 상태"를 유지하는 단위로 커밋

---

## Pull Request 규칙

### PR 제목

```
<type>: <간단한 요약> (최대 50자)
```

예시:

- `feat: 음식 사진 업로드 기능 추가`
- `fix: 이미지 분석 메모리 누수 해결`
- `refactor: 다이어리 서비스 구조 개선`

### PR 크기

- **권장**: 200~300줄 이내
- **최대**: 500줄을 넘지 않도록 노력
- 큰 기능은 작은 단위로 나누어 PR 생성

### PR 템플릿

```markdown
## 📌 개요

<!-- 이 PR의 목적을 간단히 설명해주세요. -->

- 음식 사진 업로드 API를 구현합니다

## ✅ 변경 사항

<!-- 주요 변경 내용을 bullet point로 정리해주세요. -->

- POST /photos 엔드포인트 추가
- 이미지 파일 타입 검증 로직 구현
- 이미지 업로드 서비스 연동

## 🛠️ 선택한 방식/기술 이유

<!-- 왜 이런 방식을 선택했는지 설명해주세요. -->

## 🧪 테스트 방법

<!-- 테스트할 수 있도록 재현 방법을 작성해주세요. -->

- POST /photos 엔드포인트에 이미지 파일 업로드
- 지원하지 않는 파일 형식 업로드 시 에러 확인

## 🔍 체크리스트

- [ ] 로컬에서 정상 동작 확인
- [ ] 타입 힌트 적용
- [ ] Ruff 린트 검사 통과

## 💬 논의 사항 (선택)

<!-- 리뷰어와 논의하고 싶은 사항 -->
```

---

## 코드 리뷰 원칙

### 리뷰어

- 코드 스타일보다 **의도와 구조**를 우선 리뷰
- 대안 제시는 가능하나 강요하지 않음
- 합의된 기준은 문서로 남김

### 리뷰 요청자

- PR 생성 전 **Self Review** 필수
- 불필요한 디버그 코드/주석 제거
- 테스트 방법 명시

### 피드백 예시

```markdown
💡 제안: 이 함수를 분리하면 테스트가 더 쉬워질 것 같습니다.

❓ 질문: 이 상수값의 의미가 궁금합니다.

✅ 좋은점: 에러 핸들링이 깔끔하게 처리되어 있네요!
```

---

## 자주 겪는 상황

### PR 범위가 너무 커진 경우

```bash
# 서브 브랜치로 분리
git checkout -b feat/photo-upload-validation
git cherry-pick commit-hash-1
git push origin feat/photo-upload-validation
```

### 커밋 정리 (PR 전)

```bash
# Interactive rebase로 커밋 정리
git rebase -i main

# squash: 커밋 합치기
# reword: 메시지 수정
# drop: 커밋 삭제
```

### Conflict 해결

```bash
git checkout main
git pull origin main
git checkout feat/photo-upload
git rebase main
# 충돌 해결 후
git add .
git rebase --continue
git push origin feat/photo-upload --force-with-lease
```

---

## 워크플로우 요약

```bash
# 1. 브랜치 생성
git checkout -b feat/photo-upload

# 2. 작업 및 커밋
git add .
git commit -m "feat: 사진 업로드 API 구현"

# 3. 푸시
git push origin feat/photo-upload

# 4. GitHub에서 PR 생성

# 5. 리뷰 후 머지

# 6. 정리
git checkout main
git pull origin main
git branch -d feat/photo-upload
```
