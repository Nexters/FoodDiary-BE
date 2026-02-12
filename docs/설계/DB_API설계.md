# **API 설계 변경사항 (2026-02-12)**

## **주요 변경사항**

### **1. 비동기 분석 처리 + FCM 푸시 도입**

기존: 동기 방식 (5-10초 대기)
→ 변경: 비동기 방식 (1-2초 즉시 응답 + FCM 푸시)

### **2. Diary 테이블에 analysis_status 필드 추가**

- `processing`: 분석 중
- `done`: 분석 완료
- `failed`: 분석 실패

### **3. API 엔드포인트 변경**

- `POST /photos/batch-upload`: 즉시 응답 (분석은 백그라운드)
- `GET /diaries/{diary_id}`: 새로 추가 (다이어리 ID로 단일 조회)
- `GET /diaries?date=...`: 기존 유지 (날짜 범위로 조회)

### **4. 프론트 호출 흐름**

```
1. POST /photos/batch-upload (즉시 응답)
2. 화면에 "분석 중..." 표시
3. FCM 푸시 수신 (diary_id 포함)
4. GET /diaries/{diary_id} 조회
5. 분석 결과 표시
```

---

# **현재 서비스 플로우 요약 (비동기 분석 + FCM 푸시)**

```
1. 유저가 앱 실행
2. 날짜 선택
3. 사진 업로드 (여러 장 가능)
4. POST /photos/batch-upload → 즉시 응답 (1-2초)
   └─ 사진을 시간대별로 분류 (EXIF 기반)
   └─ 시간대별 그룹 = 하나의 다이어리 (Diary 레코드 생성)
   └─ analysis_status: "processing" 상태로 반환

5. 백그라운드 분석 (비동기)
   └─ 사진마다 LLM 분석 API 호출 (병렬)
   └─ 분석 결과 DB 저장 (PhotoAnalysisResult)
   └─ DiaryAnalysis 집계 (중복 제거)

6. 분석 완료
   └─ Diary.analysis_status = "done" 업데이트
   └─ FCM 푸시 전송 (diary_id 포함)

7. 프론트에서 FCM 수신
   └─ GET /diaries/{diary_id} 호출
   └─ 분석 결과 표시:
       - 음식 카테고리
       - 음식점 이름 (후보)
       - 주소
       - 키워드
       - 메뉴 이름

8. 유저는 결과를 선택/확정
   └─ POST /diaries/{diary_id}/confirm

9. 최종 확정
   └─ Diary에 restaurant_name, category 저장
```

---

# **DB 구조 설계**

### **1.User**

- Google / Apple OAuth 기반
- 고유 user_id

| **필드**         | **설명**                         |
| ---------------- | -------------------------------- |
| id               | PK                               |
| provider         | google / apple                   |
| email            |                                  |
| provider_user_id | OAuth Provider에서 제공해주는 id |

---

### **2.Diary**

- 끼니별 **하나의 일기**
- 특정 날짜 + 유저 + 메모 등의 개념
- 사진이 하나만 올라갈 수도, 여러 개 올라갈 수도 있음
- 사진을 올리기 전에도 생성 가능

| **필드**        | **설명**                                                       |
| --------------- | -------------------------------------------------------------- |
| id              | PK                                                             |
| user_id         | 작성자                                                         |
| diary_date      | 2024-01-17 형태                                                |
| time_type       | 아침 / 점심 / 저녁 / 간식                                      |
| analysis_status | processing(분석중) / done(완료) / failed(실패)                 |
| restaurant_name | 유저가 최종 확정한 식당명                                      |
| category        | 유저가 최종 확정한 음식 카테고리                               |
| cover_photo_id  | 대표 썸네일 사진                                               |
| note            | 메모 (필요하면)                                                |
| tags            | 다이어리에 최종적으로 보여질 태그(일단 사진들의 음식명 리스트) |
| photo_count     | 다이어리에 포함된 사진의 수                                    |
| created_at      |                                                                |
| updated_at      |                                                                |
| deleted_at      |                                                                |

---

### **3.DiaryAnalysis**

- 다이어리 하나에 대한 추론 결과
- 아직 유저가 확정하지 않은 “AI 추정” 상태
- 후보 리스트 형태일 수 있음

| **필드**              | **설명** |
| --------------------- | -------- |
| diary_id              | PK, FK   |
| restaurant_candidates | JSON     |
| category_candidates   | JSON     |
| menu_candidates       | JSON     |
| created_at            |          |

---

### **4.Photo**

- 업로드한 사진 하나 = 하나의 Photo 레코드
- 사진 단위로 분석 결과를 독립적으로 가짐

| **필드**       | **설명**              |
| -------------- | --------------------- |
| id             | PK                    |
| diary_id       | 해당 사진이 속한 일기 |
| image_url      | S3 저장 주소          |
| taken_at       | EXIF 시간             |
| taken_location | GPS 좌표              |

---

### **5.PhotoAnalysisResult**

- 사진 하나에 대한 추론 결과
- 아직 유저가 확정하지 않은 “AI 추정” 상태
- 후보 리스트 형태일 수 있음

| **필드**                   | **설명**                             |
| -------------------------- | ------------------------------------ |
| photo_id                   | 어떤 사진에 대한 분석인지            |
| food_category              | AI 추정한 음식 카테고리 (한식, 일식) |
| restaurant_name_candidates | 추정된 음식점 이름들 (JSON)          |
| menu_candidates            | 추정된 메뉴 이름 + 가격 리스트       |
| keywords                   | 음식 키워드 추출 (육즙, 직화, 양념)  |
| raw_response               | 추론 응답 원문                       |

> ⚠️ 주의: 이건 확정된 정보가 아닌 “후보” 상태의 결과
> 프론트에서 최초에 폼에 채워진 응답의 형태로 제공한다 해도 그 옆에 “이 음식점이 아닌가요? 다른음식점 선택하기” 같은게 붙을 수 도 있기 때문에 있는게 나을듯

- AI가 실수했을 때 유저가 **수정할 수 있는 후보값이 있으면** UX 회복이 쉬움
- 후보값이 없으면 “다시 입력”해야 하는 부담이 커짐 → 이탈 가능성↑
  >

---

## **🧠 분석 API는 어떤 식으로 작동해야 할까?**

분석은 **사진 단위로 호출**되며 아래 모듈들을 활용:

| **분석 대상**    | **사용 기술**                       |
| ---------------- | ----------------------------------- |
| 음식점 위치 추정 | EXIF → Kakao Map (좌표 → 식당)      |
| 음식 키워드      | LLM 이미지 설명 요약 or caption     |
| 메뉴 추론        | LLM + Web Search (Google, Naver 등) |
| 시간대 분류      | EXIF 시간 → 식사 시간대 맵핑        |

---

## **🔐 인증 방식**

| **방식**     | **기술**                      |
| ------------ | ----------------------------- |
| Google Login | Firebase Auth or 자체 구현    |
| Apple Login  | 애플 OAuth (iOS 앱 연동 필요) |
| 인증 후      | Backend에서 JWT 발급 (Bearer) |

---

## **☑️ 정리: 스키마 설계 핵심 포인트**

- **사진 기준 분석 결과 저장 (후보)**: PhotoAnalysisResult
- **유저 확정 값만 다이어리에 반영**
- 다이어리는 끼니 기준으로 묶음
- 유저 입력을 최소화하고, 실패해도 UX가 이어지는 설계

![DB 스키마 관계도](https://www.notion.so/image/attachment%3A412d73f4-2f9d-4eaf-9728-79aa0dda9ba0%3Aimage.png?table=block&id=2f7235c5-92d9-804b-8df6-d242661d9015&spaceId=ee272951-7e71-4526-84e4-d225bcd2403c&width=2000&userId=0d09d1b6-49c8-4b2a-a413-92f35f0f03b8&cache=v2)

# **FoodDiary API 설계**

## **✅ 1. 인증 (Authentication)**

### **POST /auth/login**

> Google 또는 Apple OAuth 로그인 (클라이언트에서 id_token 전송)

```json
Request:
{
    "provider": "google",  // or "apple"
    "id_token": "<OAuth ID token>"
}

Response:
{
    "id": "e435a643-a6c8-49ab-b14f-6dc4ae5af7be",
    "access_token": "<JWT>",
    "is_first": false  // true면 첫 로그인
}
```

---

### **POST /auth/dev/login** (개발 전용)

> DEBUG=true 환경에서만 작동하는 테스트 로그인

```json
Request:
{
    "email": "test@example.com"
}

Response:
{
    "id": "882fd7db-8dd7-4faf-ba7d-f11f92f3fb7c",
    "access_token": "<JWT>",
    "is_first": false
}
```

> ⚠️ 운영 환경에서는 비활성화됨 (403 Forbidden)

---

## **🖼️ 2. 사진 업로드 및 분석 (Photo Upload & Analysis)**

### **POST /photos/batch-upload**

📌 사진 여러 장을 **파일로 직접 업로드**하고 **즉시 응답**. AI 분석은 백그라운드에서 처리하며, 완료 시 FCM으로 알림

---

### **Request (multipart/form-data)**

```
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Form fields**

| **필드** | **타입** | **필수** | **설명**               |
| -------- | -------- | -------- | ---------------------- |
| date     | string   | ✅       | 대상 날짜 (YYYY-MM-DD) |
| photos   | file[]   | ✅       | 이미지 파일들 (다중)   |

---

### **Response (즉시 응답)**

```json
{
  "results": [
    {
      "photo_id": 19,
      "diary_id": 2,
      "time_type": "dinner",
      "image_url": "data/photos/22a85dba-9ad1-4c87-9fa8-26cd5aefe096.JPG",
      "analysis_status": "processing"
    },
    {
      "photo_id": 20,
      "diary_id": 2,
      "time_type": "dinner",
      "image_url": "data/photos/abc123.JPG",
      "analysis_status": "processing"
    }
  ]
}
```

> 📌 **응답 특징**
>
> - 즉시 응답 (1-2초 이내)
> - 파일 저장 및 Diary 생성만 완료된 상태
> - `analysis_status: "processing"` - AI 분석은 백그라운드에서 진행 중

---

### **FCM 푸시 알림 (분석 완료 시)**

분석이 완료되면 디바이스에 FCM 푸시를 전송:

```json
{
  "notification": {
    "title": "음식 일기 분석 완료",
    "body": "새로운 다이어리를 확인해보세요!"
  },
  "data": {
    "diary_id": "2",
    "action": "diary_analysis_complete"
  }
}
```

> 프론트에서는 `diary_id`를 받아 `GET /diaries/{diary_id}`로 조회

---

### **🔧 서버 내부 처리 순서 (비동기 방식)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POST /photos/batch-upload 전체 흐름                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  1단계: 파일 저장 + DB 저장 (순차 처리) → 즉시 응답                     ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   for each file in files:                                             ║  │
│  ║   ┌─────────────────────────────────────────────────────────────────┐ ║  │
│  ║   │ 1. EXIF 파싱                                                    │ ║  │
│  ║   │    └─ taken_at (촬영시간), latitude/longitude (GPS)             │ ║  │
│  ║   │                                                                 │ ║  │
│  ║   │ 2. 시간대 분류                                                  │ ║  │
│  ║   │    └─ taken_at → breakfast/lunch/dinner/snack                   │ ║  │
│  ║   │    ┌────────────────────────────────────────────────────────┐   │ ║  │
│  ║   │    │  05:00-10:00 → breakfast (아침)                        │   │ ║  │
│  ║   │    │  10:00-14:00 → lunch (점심)                            │   │ ║  │
│  ║   │    │  14:00-17:00 → snack (간식)                            │   │ ║  │
│  ║   │    │  17:00-22:00 → dinner (저녁)                           │   │ ║  │
│  ║   │    │  22:00-05:00 → snack (야식)                            │   │ ║  │
│  ║   │    └────────────────────────────────────────────────────────┘   │ ║  │
│  ║   │                                                                 │ ║  │
│  ║   │ 3. Diary upsert                                                 │ ║  │
│  ║   │    └─ (user_id + date + time_type) 기준으로 생성 또는 조회      │ ║  │
│  ║   │    └─ analysis_status: "processing" 설정                        │ ║  │
│  ║   │                                                                 │ ║  │
│  ║   │ 4. 파일 저장                                                    │ ║  │
│  ║   │    └─ data/photos/{uuid}.jpg                                    │ ║  │
│  ║   │                                                                 │ ║  │
│  ║   │ 5. Photo 레코드 생성                                            │ ║  │
│  ║   │    └─ diary_id, image_url, taken_at, taken_location             │ ║  │
│  ║   └─────────────────────────────────────────────────────────────────┘ ║  │
│  ║                                                                       ║  │
│  ║   6. 백그라운드 태스크 등록                                            ║  │
│  ║      └─ analyze_photos_task(diary_id)                                 ║  │
│  ║                                                                       ║  │
│  ║   7. 즉시 응답 반환 (1-2초)                                           ║  │
│  ║      └─ { photo_id, diary_id, image_url, analysis_status: "processing" } ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                             │
│                           클라이언트로 즉시 응답 ▲                           │
│  ═════════════════════════════════════════════════════════════════════════  │
│                           여기서부터 백그라운드 처리 ▼                       │
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  2단계: LLM 분석 (병렬 처리) - 백그라운드                              ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   asyncio.gather() 로 모든 사진 동시 분석                             ║  │
│  ║                                                                       ║  │
│  ║   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐              ║  │
│  ║   │   Photo 1    │   │   Photo 2    │   │   Photo 3    │              ║  │
│  ║   ├──────────────┤   ├──────────────┤   ├──────────────┤              ║  │
│  ║   │ Gemini API   │   │ Gemini API   │   │ Gemini API   │   병렬!     ║  │
│  ║   │ (이미지분석)  │   │ (이미지분석)  │   │ (이미지분석)  │              ║  │
│  ║   ├──────────────┤   ├──────────────┤   ├──────────────┤              ║  │
│  ║   │ Kakao Map    │   │ Kakao Map    │   │ Kakao Map    │   병렬!     ║  │
│  ║   │ (주변식당)    │   │ (주변식당)    │   │ (주변식당)    │              ║  │
│  ║   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘              ║  │
│  ║          │                  │                  │                      ║  │
│  ║          └──────────────────┼──────────────────┘                      ║  │
│  ║                             ▼                                         ║  │
│  ║                    분석 결과 수집 완료                                 ║  │
│  ║                     (AnalysisData[])                                  ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  3단계: 분석 결과 DB 저장 (순차 처리)                                  ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   for each result in analysis_results:                                ║  │
│  ║       PhotoAnalysisResult upsert (photo_id 기준)                      ║  │
│  ║                                                                       ║  │
│  ║   ※ DB 저장은 순차 실행 (동시 INSERT 시 충돌 방지)                     ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  4단계: DiaryAnalysis 집계                                             ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   같은 다이어리에 속한 모든 PhotoAnalysisResult를 집계                 ║  │
│  ║                                                                       ║  │
│  ║   Photo1 분석결과 ──┐                                                 ║  │
│  ║   Photo2 분석결과 ──┼──▶ 중복 제거 ──▶ DiaryAnalysis 저장             ║  │
│  ║   Photo3 분석결과 ──┘                                                 ║  │
│  ║                                                                       ║  │
│  ║   집계 항목:                                                          ║  │
│  ║   - restaurant_candidates: 모든 식당 후보 (이름 기준 중복 제거)        ║  │
│  ║   - category_candidates: 모든 카테고리 (중복 제거)                    ║  │
│  ║   - menu_candidates: 모든 메뉴 (이름 기준 중복 제거)                   ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  5단계: 상태 업데이트 + FCM 푸시                                       ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   1. Diary.analysis_status = "done" 업데이트                          ║  │
│  ║   2. FCM 푸시 전송                                                    ║  │
│  ║      └─ { diary_id, action: "diary_analysis_complete" }               ║  │
│  ║                                                                       ║  │
│  ║   ※ 실패 시: analysis_status = "failed"                               ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### **📊 데이터 흐름 다이어그램**

```
┌─────────────┐
│  사진 파일   │
│  (JPEG)     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│   EXIF 파싱      │
│ ┌──────────────┐ │
│ │ taken_at     │ │ ──▶ 시간대 분류 ──▶ time_type
│ │ GPS 좌표     │ │ ──▶ Kakao Map ──▶ 주변 식당
│ └──────────────┘ │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│     Diary        │◀───▶│  DiaryAnalysis   │
│ ┌──────────────┐ │     │ ┌──────────────┐ │
│ │ user_id      │ │     │ │ 식당 후보들   │ │
│ │ date         │ │     │ │ 카테고리 후보 │ │
│ │ time_type    │ │     │ │ 메뉴 후보들   │ │
│ └──────────────┘ │     │ └──────────────┘ │
└────────┬─────────┘     └──────────────────┘
         │                        ▲
         ▼                        │ 집계
┌──────────────────┐              │
│      Photo       │              │
│ ┌──────────────┐ │              │
│ │ image_url    │ │              │
│ │ taken_at     │ │              │
│ │ GPS 좌표     │ │              │
│ └──────────────┘ │              │
└────────┬─────────┘              │
         │                        │
         ▼                        │
┌──────────────────────┐          │
│ PhotoAnalysisResult  │──────────┘
│ ┌──────────────────┐ │
│ │ food_category    │ │ ◀── Gemini API (LLM)
│ │ menu_candidates  │ │ ◀── Gemini API (LLM)
│ │ keywords         │ │ ◀── Gemini API (LLM)
│ │ restaurant_cand. │ │ ◀── Kakao Map API
│ └──────────────────┘ │
└──────────────────────┘
```

---

### **🤖 LLM 분석 상세 (Gemini API)**

**프롬프트:**

```
이 음식 사진을 분석해주세요.

다음 정보를 JSON 형식으로 반환해주세요:
{
  "food_category": "한식/일식/중식/양식/기타 중 하나",
  "menus": ["추정되는 메뉴 이름들"],
  "keywords": ["음식 특징 키워드들 (예: 국물, 매운, 구운)"]
}

음식이 아닌 사진이면 food_category를 "기타"로 설정하세요.
```

**응답 예시:**

```json
{
  "food_category": "일식",
  "menus": ["라멘", "차슈"],
  "keywords": ["국물", "면", "고기", "따뜻한"]
}
```

---

### **📍 주변 식당 검색 (Kakao Map API)**

사진의 GPS 좌표가 있는 경우:

```
1. EXIF에서 GPS 추출: 37.5219, 126.9245
2. Kakao Map API 호출: 반경 500m 내 음식점 검색
3. 결과를 restaurant_candidates로 저장
```

**GPS가 없는 경우:**

- restaurant_candidates는 빈 배열 `[]`
- LLM 분석 결과만 사용

---

### **🤖 분석 처리 아키텍처 (비동기 + FCM 푸시) ✅ 현재 설계**

> 업로드는 즉시 응답하고, 분석은 백그라운드에서 수행. 완료 시 FCM으로 알림

```
┌─────────────┐     POST /photos/batch-upload      ┌─────────────┐
│   Frontend  │ ─────────────────────────────────▶ │   Backend   │
└─────────────┘                                    └─────────────┘
       │                                                 │
       │         즉시 응답 (1-2초)                        │
       ◀─────────────────────────────────────────────────┤
       {photo_id, diary_id, analysis_status: "processing"}
       │                                                 │
       │                                          ┌──────▼──────────┐
       │                                          │ Background      │
       │                                          │ Analysis Task   │
       │                                          └──────┬──────────┘
       │                                                 │
       │                                   ┌─────────────┼─────────────┐
       │                                   ▼             ▼             ▼
       │                              ┌────────┐   ┌────────┐   ┌────────┐
       │                              │Photo 1 │   │Photo 2 │   │Photo 3 │
       │                              │LLM 분석│   │LLM 분석│   │LLM 분석│
       │                              │(Gemini)│   │(Gemini)│   │(Gemini)│
       │                              │Kakao   │   │Kakao   │   │Kakao   │
       │                              └────┬───┘   └────┬───┘   └────┬───┘
       │                                   │            │            │
       │                                   └────────────┼────────────┘
       │                                                │
       │                                                ▼
       │                                     ┌─────────────────────┐
       │                                     │ DiaryAnalysis 집계   │
       │                                     │ analysis_status:     │
       │                                     │ "done" 업데이트      │
       │                                     └──────────┬──────────┘
       │                                                │
       │     FCM 푸시 (분석 완료)                        │
       ◀─────────────────────────────────────────────────┘
       {diary_id: 2, action: "diary_analysis_complete"}
       │
       │     GET /diaries/2  ← diary_id로 조회
       │─────────────────────────────────────────────────▶
       │
       ◀─────────────────────────────────────────────────
       {diary_id: 2, analysis_status: "done", ...}
```

**장점:**

- 즉시 응답 (1-2초) - 사용자 대기 시간 최소화
- 타임아웃 위험 없음
- FCM 푸시로 프론트에서 폴링 불필요
- 대용량 업로드에 유리

**단점:**

- FCM 인프라 필요
- 백그라운드 태스크 관리 필요

**프론트 호출 흐름:**

```
1. POST /photos/batch-upload  ← 즉시 응답 (1-2초)
   응답: { photo_id, diary_id, analysis_status: "processing" }

2. 화면에 "분석 중..." 표시 (또는 GET /diaries로 목록 조회)

3. FCM 푸시 수신 대기
   └─ { diary_id: 2, action: "diary_analysis_complete" }

4. GET /diaries/2  ← diary_id로 조회
   응답: { diary_id: 2, analysis_status: "done", restaurant_name, category, ... }

5. (필요시) GET /diaries/2/analysis  ← 후보 조회

6. POST /diaries/2/confirm  ← 확정
```

**서버 코드 예시:**

```python
from fastapi import BackgroundTasks

@router.post("/batch-upload")
async def batch_upload_photos(
    ...,
    background_tasks: BackgroundTasks
):
    # 1단계: 파일 저장 + Diary 생성
    photos = []
    diary_ids = set()

    for file in files:
        # EXIF 파싱, 파일 저장, Photo 레코드 생성
        photo = await save_and_create_photo(file, ...)
        photos.append(photo)
        diary_ids.add(photo.diary_id)

    # 2단계: 백그라운드 분석 태스크 등록
    for diary_id in diary_ids:
        background_tasks.add_task(
            analyze_and_notify,
            diary_id=diary_id,
            user_id=current_user.id
        )

    # 3단계: 즉시 응답
    return {
        "results": [
            {
                "photo_id": p.id,
                "diary_id": p.diary_id,
                "image_url": p.image_url,
                "analysis_status": "processing"
            }
            for p in photos
        ]
    }


async def analyze_and_notify(diary_id: int, user_id: str):
    """백그라운드 분석 + FCM 푸시"""
    try:
        # 1. 해당 다이어리의 모든 사진 분석 (병렬)
        photos = await get_diary_photos(diary_id)
        analysis_results = await asyncio.gather(
            *[analyze_photo(p) for p in photos]
        )

        # 2. 분석 결과 DB 저장
        for result in analysis_results:
            await save_photo_analysis(result)

        # 3. DiaryAnalysis 집계
        await aggregate_photo_analysis_to_diary(diary_id)

        # 4. Diary 상태 업데이트
        await update_diary_status(diary_id, "done")

        # 5. FCM 푸시 전송
        await send_fcm_push(
            user_id=user_id,
            data={
                "diary_id": str(diary_id),
                "action": "diary_analysis_complete"
            },
            notification={
                "title": "음식 일기 분석 완료",
                "body": "새로운 다이어리를 확인해보세요!"
            }
        )
    except Exception as e:
        # 실패 시 상태 업데이트
        await update_diary_status(diary_id, "failed")
        logger.error(f"Analysis failed for diary {diary_id}: {e}")
```

---

---

### **🔄 DiaryAnalysis 집계 로직 상세**

> 같은 다이어리에 속한 모든 PhotoAnalysisResult를 모아서 중복 제거 후 저장

**예시: diary_id=2에 사진 3장이 있는 경우**

```
Photo 1 (PhotoAnalysisResult)
├── food_category: "일식"
├── restaurant_candidates: [화목순대국, 여수해물낙지]
├── menu_candidates: [라멘]
└── keywords: [국물, 면]

Photo 2 (PhotoAnalysisResult)
├── food_category: "일식"
├── restaurant_candidates: [화목순대국, 무끼]  ← 화목순대국 중복!
├── menu_candidates: [사시미, 라멘]  ← 라멘 중복!
└── keywords: [회, 신선한]

Photo 3 (PhotoAnalysisResult)
├── food_category: "기타"
├── restaurant_candidates: [진주집]
├── menu_candidates: [파스타]
└── keywords: [크림, 치즈]

        ↓ aggregate_photo_analysis_to_diary()

DiaryAnalysis (diary_id=2)
├── category_candidates: ["일식", "기타"]  ← 중복 제거
├── restaurant_candidates: [화목순대국, 여수해물낙지, 무끼, 진주집]  ← 중복 제거
└── menu_candidates: [라멘, 사시미, 파스타]  ← 중복 제거
```

**실제 코드 (app/services/analysis_service.py):**

```python
async def aggregate_photo_analysis_to_diary(db, diary_id):
    # 1. 해당 다이어리의 모든 PhotoAnalysisResult 조회
    stmt = select(PhotoAnalysisResult).join(Photo).where(Photo.diary_id == diary_id)
    photo_results = await db.execute(stmt)

    # 2. 집계 (이름 기준 중복 제거)
    restaurant_candidates = []  # 식당 후보
    category_candidates = []    # 카테고리 후보
    menu_candidates = []        # 메뉴 후보

    seen_restaurants = set()
    seen_menus = set()

    for pr in photo_results:
        # 식당 중복 제거
        for rc in pr.restaurant_name_candidates or []:
            if rc["name"] not in seen_restaurants:
                seen_restaurants.add(rc["name"])
                restaurant_candidates.append(rc)

        # 카테고리 수집
        if pr.food_category:
            category_candidates.append(pr.food_category)

        # 메뉴 중복 제거
        for mc in pr.menu_candidates or []:
            if mc["name"] not in seen_menus:
                seen_menus.add(mc["name"])
                menu_candidates.append(mc["name"])

    # 3. DiaryAnalysis upsert
    # ...
```

---

## **📆 3. 다이어리 조회**

### **GET /diaries** (날짜 범위로 조회)

> 하루 또는 기간 단위로 다이어리 목록 조회. Query Parameter로 조회 범위 지정.

**Query Parameters**

| **파라미터** | **타입** | **필수** | **설명**                                                          |
| ------------ | -------- | -------- | ----------------------------------------------------------------- |
| date         | string   | 조건부   | 특정 날짜 조회 (YYYY-MM-DD). start_date/end_date와 함께 사용 불가 |
| start_date   | string   | 조건부   | 시작 날짜 (YYYY-MM-DD). end_date와 함께 사용                      |
| end_date     | string   | 조건부   | 종료 날짜 (YYYY-MM-DD). start_date와 함께 사용                    |

> ⚠️ `date` 또는 `start_date + end_date` 중 하나는 필수. 둘 다 없거나 둘 다 있으면 400 에러.

---

#### **예시 1: 하루 조회**

```
GET /diaries?date=2026-01-19
```

```json
{
  "2026-01-19": {
    "diaries": [
      {
        "diary_id": 12,
        "time_type": "lunch",
        "analysis_status": "processing",
        "restaurant_name": null,
        "category": null,
        "cover_photo_url": "...",
        "photo_count": 3,
        "photos": [
          {
            "photo_id": 101,
            "image_url": "..."
          }
        ]
      }
    ]
  }
}
```

---

#### **예시 2: 일주일 조회**

```
GET /diaries?start_date=2026-01-13&end_date=2026-01-19
```

```json
{
    "2026-01-13": {
        "diaries": [
            {
                "diary_id": 8,
                "time_type": "lunch",
                "analysis_status": "done",
                "restaurant_name": "명동교자",
                "category": "한식",
                "cover_photo_url": "...",
                "photo_count": 2,
                "photos": [...]
            },
            {
                "diary_id": 9,
                "time_type": "dinner",
                "analysis_status": "done",
                "restaurant_name": "스시히로바",
                "category": "일식",
                "cover_photo_url": "...",
                "photo_count": 4,
                "photos": [...]
            }
        ]
    },
    "2026-01-14": {
        "diaries": []
    },
    "2026-01-15": {
        "diaries": [
            {
                "diary_id": 10,
                "time_type": "breakfast",
                "analysis_status": "done",
                "restaurant_name": "투썸플레이스",
                "category": "카페",
                "cover_photo_url": "...",
                "photo_count": 1,
                "photos": [...]
            }
        ]
    },
    "2026-01-16": {
        "diaries": []
    },
    "2026-01-17": {
        "diaries": []
    },
    "2026-01-18": {
        "diaries": []
    },
    "2026-01-19": {
        "diaries": [
            {
                "diary_id": 12,
                "time_type": "lunch",
                "analysis_status": "processing",
                "restaurant_name": null,
                "category": null,
                "cover_photo_url": "...",
                "photo_count": 3,
                "photos": [...]
            }
        ]
    }
}
```

> 📌 **응답 구조 설명**
>
> - 날짜별로 그룹핑된 딕셔너리 형태
> - **analysis_status**: `processing` (분석 중) / `done` (완료) / `failed` (실패)
>   - `processing`: 프론트에서 "분석 중..." UI 표시
>   - `done`: 분석 완료 - restaurant_name, category 등 확정 데이터 사용 가능
>   - `failed`: 분석 실패 - 재시도 UI 제공
> - 다이어리가 없는 날짜도 빈 배열로 포함 (프론트에서 "기록 없음" UI 처리 용이)
> - 기간 조회 시 최대 31일로 제한 권장 (성능 보장)

---

### **GET /diaries/{diary_id}** (다이어리 ID로 조회)

> FCM 푸시로 받은 diary_id를 사용하여 특정 다이어리 상세 조회

**Path Parameters**

| **파라미터** | **타입** | **필수** | **설명**    |
| ------------ | -------- | -------- | ----------- |
| diary_id     | integer  | ✅       | 다이어리 ID |

---

#### **예시: 다이어리 상세 조회**

```
GET /diaries/12
```

```json
{
  "diary_id": 12,
  "user_id": "e435a643-a6c8-49ab-b14f-6dc4ae5af7be",
  "diary_date": "2026-01-19",
  "time_type": "lunch",
  "analysis_status": "done",
  "restaurant_name": "명동교자",
  "category": "한식",
  "cover_photo_url": "data/photos/abc123.JPG",
  "note": null,
  "tags": ["칼국수", "만두"],
  "photo_count": 3,
  "photos": [
    {
      "photo_id": 101,
      "image_url": "data/photos/abc123.JPG",
      "taken_at": "2026-01-19T12:30:00",
      "taken_location": {
        "latitude": 37.5219,
        "longitude": 126.9245
      }
    },
    {
      "photo_id": 102,
      "image_url": "data/photos/def456.JPG",
      "taken_at": "2026-01-19T12:32:00",
      "taken_location": null
    },
    {
      "photo_id": 103,
      "image_url": "data/photos/ghi789.JPG",
      "taken_at": "2026-01-19T12:35:00",
      "taken_location": null
    }
  ],
  "created_at": "2026-01-19T12:40:00",
  "updated_at": "2026-01-19T12:45:30"
}
```

> 📌 **사용 시나리오**
>
> 1. FCM 푸시로 `diary_id` 수신
> 2. `GET /diaries/{diary_id}`로 상세 조회
> 3. `analysis_status: "done"` 확인 후 데이터 표시

---

## **📆 4. 다이어리 분석 후보 조회 (선택 화면용)**

### **GET /diaries/{diary_id}/analysis**

> “이 식당 맞나요?” 화면에서만 사용

```json
{
  "restaurant_candidates": [
    { "name": "명동교자", "confidence": 0.92, "address": "서울 중구 명동..." }
  ],
  "category_candidates": ["한식"],
  "menu_candidates": ["칼국수", "만두"]
}
```

## **📆 5. 다이어리 확정 (유저 선택 저장)**

### **POST /diaries/{diary_id}/confirm**

```json
{
  "restaurant_name": "명동교자",
  "category": "한식"
}
```

- 최초 확정
- 재수정
- 덮어쓰기 전부 여기서

➡️ 별도 PUT / PATCH 필요 없음

## **🧠 프론트 실제 호출 흐름 (비동기 + FCM 방식)**

```
1. 로그인
   └─ POST /auth/login

2. 메인 화면 진입
   └─ GET /diaries?start_date=...&end_date=...  ← 일주일 조회
   └─ analysis_status: "processing" / "done" / "failed" 확인

3. 사진 여러 장 선택

4. 사진 업로드 (즉시 응답)
   └─ POST /photos/batch-upload
   └─ 응답: { photo_id, diary_id, analysis_status: "processing" }

5. 화면에 "분석 중..." 표시
   └─ GET /diaries?date=...  ← 목록 갱신 (선택적)
   └─ analysis_status: "processing" 표시

6. FCM 푸시 수신 (백그라운드 분석 완료)
   └─ 푸시 데이터: { diary_id: 2, action: "diary_analysis_complete" }

7. 다이어리 상세 조회
   └─ GET /diaries/2  ← diary_id로 조회
   └─ analysis_status: "done" 확인
   └─ 분석 결과 표시

8. (필요시) 후보 조회 - "이 식당 맞나요?" 화면
   └─ GET /diaries/2/analysis
   └─ restaurant_candidates, category_candidates, menu_candidates 표시

9. 최종 확정
   └─ POST /diaries/2/confirm
   └─ { restaurant_name, category }

10. 확정 후 목록 갱신
    └─ GET /diaries?date=...
    └─ 또는 GET /diaries/2 (단일 조회)
```

### **🔄 시나리오별 호출 패턴**

#### **시나리오 1: 분석 완료 전 목록 조회**

```
1. POST /photos/batch-upload
   → 응답: analysis_status: "processing"

2. GET /diaries?date=2026-01-19
   → 응답: analysis_status: "processing", restaurant_name: null

3. 프론트: "분석 중..." UI 표시
```

#### **시나리오 2: FCM 푸시 수신 후 조회**

```
1. FCM 푸시 수신
   → { diary_id: 2, action: "diary_analysis_complete" }

2. GET /diaries/2
   → 응답: analysis_status: "done", restaurant_name: "명동교자"

3. 프론트: 분석 결과 표시
```

#### **시나리오 3: 앱 재진입 시**

```
1. GET /diaries?start_date=...&end_date=...
   → 일주일 치 다이어리 조회

2. analysis_status 확인
   - "processing": "분석 중..." 표시
   - "done": 결과 표시
   - "failed": "재시도" 버튼 표시
```
