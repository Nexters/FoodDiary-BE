# 비동기 분석 + FCM 푸시 전환 작업 계획

**작성일:** 2026-02-12  
**목표:** 사진 업로드 즉시 응답 → 백그라운드 분석 → FCM 푸시 알림

---

## 🎯 왜 변경하나요?

| 기존 (동기)       | 변경 후 (비동기)   |
| ----------------- | ------------------ |
| 5-10초 대기 ⏱️    | 1-2초 즉시 응답 ⚡ |
| 타임아웃 위험 ⚠️  | 안정적 처리 ✅     |
| 서버 부하 높음 📈 | 부하 분산 📊       |

---

## 📐 전체 아키텍처

```
사진 업로드 → 즉시 응답 (processing)
    ↓
백그라운드 분석 (5-10초)
    ↓
DB 업데이트 (done/failed)
    ↓
FCM 푸시 (diary_id 전달)
    ↓
프론트: GET /diaries/{diary_id}
```

---

## 📋 작업 단계

### Phase 1: DB 스키마 변경 ⭐ **필수 선행**

#### 1.1 마이그레이션 스크립트

- 파일: `scripts/migrations/001_add_analysis_status.sql`
- 작업: `diaries` 테이블에 `analysis_status` 컬럼 추가
- 값: `'processing'`, `'done'`, `'failed'`
- 기본값: `'done'` (기존 데이터 호환)

#### 1.2 모델 업데이트

- 파일: `app/models/diary.py`
- 추가: `analysis_status: Mapped[str]` 필드

#### 1.3 init-db.sql 업데이트

- 파일: `scripts/init-db.sql`
- 새 DB 생성 시 `analysis_status` 포함

---

### Phase 2: 백그라운드 태스크 인프라

#### 2.1 백그라운드 서비스 생성

- 파일: `app/services/background_service.py` (신규)
- 함수: `analyze_photos_background(diary_id, user_id)`
- 기능:
  - 사진 조회
  - LLM 분석 (병렬)
  - 결과 저장
  - DiaryAnalysis 집계
  - 상태 업데이트 (`done` / `failed`)
  - FCM 푸시 전송

#### 2.2 photo_service.py 로직 분리

- 파일: `app/services/photo_service.py`
- 변경:
  - **유지**: 파일 저장 + Photo 레코드 생성
  - **제거**: LLM 분석 로직 (→ background_service.py로 이동)
  - **추가**: `analysis_status='processing'` 설정

---

### Phase 3: FCM 푸시 통합

#### 3.1 FCM 서비스 구현

- 파일: `app/services/fcm_service.py` (신규)
- 함수: `send_analysis_complete_push(user_id, diary_id)`
- 기능:
  - 디바이스 토큰 조회
  - FCM 메시지 전송
  - 만료 토큰 비활성화

#### 3.2 환경 설정

- 파일: `app/core/config.py`
- 추가: `FCM_ENABLED`, `FCM_CREDENTIALS_PATH`
- `.env`: Firebase 인증 정보 경로 설정

#### 3.3 의존성 추가

- `requirements.txt`: `firebase-admin` 추가

#### 3.4 앱 초기화

- 파일: `app/main.py`
- 추가: `lifespan` 이벤트에서 Firebase 초기화

---

### Phase 4: API 엔드포인트 수정

#### 4.1 배치 업로드 API 수정

- 파일: `app/routers/photos.py`
- 변경:
  - `BackgroundTasks` 의존성 추가
  - 백그라운드 태스크 등록
  - 즉시 응답 (`analysis_status: "processing"`)

#### 4.2 다이어리 단일 조회 API 추가

- 파일: `app/routers/diaries.py`
- 추가: `GET /diaries/{diary_id}` 엔드포인트
- 응답: 다이어리 상세 + analysis_status

#### 4.3 다이어리 목록 조회 수정

- 파일: `app/routers/diaries.py`
- 변경: 응답에 `analysis_status` 포함

---

### Phase 5: 스키마 업데이트

#### 5.1 PhotoUploadResult 수정

- 파일: `app/schemas/photo.py`
- 추가: `analysis_status: str`
- 변경: `analysis: Optional` (즉시 응답 시 None)

#### 5.2 DiaryResponse 수정

- 파일: `app/schemas/diary.py`
- 추가: `analysis_status: str`

---

### Phase 6: 테스트

#### 6.1 단위 테스트

- 파일: `tests/services/test_background_service.py`
- 테스트: 백그라운드 분석 성공/실패 시나리오

#### 6.2 통합 테스트

- 파일: `tests/routers/test_photos_async.py`
- 테스트: 전체 플로우 (업로드 → 분석 → 조회)

#### 6.3 FCM 푸시 테스트

- 실제 디바이스로 푸시 수신 확인

---

## ✅ 체크리스트

### Phase 1: DB

- [ ] 마이그레이션 스크립트 작성
- [ ] 개발 DB 마이그레이션 실행
- [ ] 모델 업데이트
- [ ] init-db.sql 업데이트

### Phase 2: 백그라운드

- [ ] `background_service.py` 생성
- [ ] `photo_service.py` 로직 분리

### Phase 3: FCM

- [ ] `fcm_service.py` 구현
- [ ] 환경 설정 추가
- [ ] `firebase-admin` 설치
- [ ] Firebase 인증 파일 준비
- [ ] 앱 초기화 로직 추가

### Phase 4: API

- [ ] `POST /photos/batch-upload` 수정
- [ ] `GET /diaries/{diary_id}` 추가
- [ ] `GET /diaries` 응답 수정

### Phase 5: 스키마

- [ ] `PhotoUploadResult` 수정
- [ ] `DiaryResponse` 수정

### Phase 6: 테스트

- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성
- [ ] FCM 푸시 수동 테스트

---

## ⚠️ 주의사항

### 백그라운드 태스크

- FastAPI BackgroundTasks는 동시 실행 제한 없음 → **Phase 7 필요**
- 대용량 처리 시 Celery 고려
- 실패 시 재시도 로직 권장

### FCM 푸시

- Firebase 인증 파일 `.gitignore` 추가 필수
- 푸시 실패해도 분석 완료 상태 유지
- 프론트: 앱 재진입 시 목록 조회로도 확인 가능

### 성능

- 응답 시간 목표: 1-2초
- 백그라운드 분석: ??초
- DB 커넥션 풀 크기 확인 필요

---

## 📖 참고

- FastAPI BackgroundTasks: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Firebase Admin SDK: https://firebase.google.com/docs/admin/setup
- FCM 메시지 전송: https://firebase.google.com/docs/cloud-messaging/admin/send-messages

---

## 🔄 확장 계획 (Phase 7)

**문제:** 동시 사용자 100명 이상 시 부하 발생  
**해결:** Celery + Redis 도입 (별도 문서 참고: `백그라운드_태스크_확장성_설계.md`)
