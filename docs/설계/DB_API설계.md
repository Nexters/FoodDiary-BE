# **현재 서비스 플로우 요약 (분석 중심)**

```
1. 유저가 앱 실행
2. 날짜 선택
3. 사진 업로드 (여러 장 가능)
4. 사진 여러장이 동시에 백엔드로 넘어감
5. 사진을 시간대별로 분류해서 그룹을 만들어야함. 여기서 만들어진 그룹이 하나의 다이어리
5. 사진마다 → 분석 API 호출

5. 분석 결과:
    - 음식 카테고리
    - 음식점 이름
    - 주소
    - 키워드
    - 메뉴 이름
6. 유저는 결과를 선택/확정
7. 최종 결과 → 다이어리로 저장
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

📌 사진 여러 장을 **파일로 직접 업로드**하고 **AI 분석까지 완료**하여 반환

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

### **Response**

```json
{
  "results": [
    {
      "photo_id": 19,
      "diary_id": 2,
      "time_type": "dinner",
      "image_url": "data/photos/22a85dba-9ad1-4c87-9fa8-26cd5aefe096.JPG",
      "analysis": {
        "food_category": "일식",
        "restaurant_candidates": [
          {
            "name": "화목순대국",
            "confidence": 0.8,
            "address": "서울 영등포구 여의도동 44-14"
          },
          {
            "name": "여수해물낙지",
            "confidence": 0.8,
            "address": "서울 영등포구 여의도동 45-19"
          }
        ],
        "menu_candidates": [
          { "name": "라멘", "price": null, "confidence": null }
        ],
        "keywords": ["국물", "따뜻한", "일본"]
      }
    },
    {
      "photo_id": 20,
      "diary_id": 2,
      "time_type": "dinner",
      "image_url": "data/photos/abc123.JPG",
      "analysis": {
        "food_category": "한식",
        "restaurant_candidates": [...],
        "menu_candidates": [...],
        "keywords": ["고기", "직화", "소스"]
      }
    }
  ]
}
```

---

### **🔧 서버 내부 처리 순서 (상세)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POST /photos/batch-upload 전체 흐름                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  1단계: 파일 저장 + DB 저장 (순차 처리)                                 ║  │
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
│  ║   │                                                                 │ ║  │
│  ║   │ 4. 파일 저장                                                    │ ║  │
│  ║   │    └─ data/photos/{uuid}.jpg                                    │ ║  │
│  ║   │                                                                 │ ║  │
│  ║   │ 5. Photo 레코드 생성                                            │ ║  │
│  ║   │    └─ diary_id, image_url, taken_at, taken_location             │ ║  │
│  ║   └─────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                    │                                        │
│                                    ▼                                        │
│  ╔═══════════════════════════════════════════════════════════════════════╗  │
│  ║  2단계: LLM 분석 (병렬 처리) - DB 접근 없이                            ║  │
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
│  ║  2-2단계: 분석 결과 DB 저장 (순차 처리)                                ║  │
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
│  ║  3단계: DiaryAnalysis 집계                                             ║  │
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
│  ║  4단계: 응답 반환                                                      ║  │
│  ╠═══════════════════════════════════════════════════════════════════════╣  │
│  ║                                                                       ║  │
│  ║   각 Photo + 분석결과를 PhotoUploadResult로 변환하여 반환              ║  │
│  ║                                                                       ║  │
│  ║   {                                                                   ║  │
│  ║     "results": [                                                      ║  │
│  ║       { photo_id, diary_id, time_type, image_url, analysis }          ║  │
│  ║     ]                                                                 ║  │
│  ║   }                                                                   ║  │
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

### **🤖 분석 처리 아키텍처 (2가지 방식)**

#### **1안: 동기 + 내부 병렬 처리 ✅ 현재 구현됨 (MVP)**

> 업로드 API에서 분석까지 전부 수행하되, LLM 호출을 병렬로 처리

```
┌─────────────┐     POST /photos/batch-upload      ┌─────────────┐
│   Frontend  │ ─────────────────────────────────▶ │   Backend   │
└─────────────┘                                    └─────────────┘
                                                         │
                                                         ▼
                                                  ┌─────────────┐
                                                  │ 1. 파일 저장 │
                                                  │ 2. EXIF 파싱│
                                                  │ 3. Diary 생성│
                                                  └──────┬──────┘
                                                         │
                                          ┌──────────────┼──────────────┐
                                          ▼              ▼              ▼
                                     ┌────────┐    ┌────────┐    ┌────────┐
                                     │Photo 1 │    │Photo 2 │    │Photo 3 │
                                     │LLM 분석│    │LLM 분석│    │LLM 분석│
                                     │(Gemini)│    │(Gemini)│    │(Gemini)│
                                     │Kakao   │    │Kakao   │    │Kakao   │
                                     └────┬───┘    └────┬───┘    └────┬───┘
                                          │             │             │
                                          └──────────┬──┴─────────────┘
                                                     │ asyncio.gather() 병렬 실행
                                                     ▼
                                          ┌─────────────────────┐
                                          │ 분석 결과 DB 저장    │
                                          │ (순차 - 충돌 방지)   │
                                          └──────────┬──────────┘
                                                     ▼
                                              DiaryAnalysis 집계
                                                     │
       ◀─────────────────────────────────────────────┘
       응답 (5-10초): 업로드 + 분석 결과 모두 포함
```

**장점:**

- 구현 단순 (폴링 불필요)
- 응답에 분석 결과까지 포함 가능
- 프론트엔드 로직 단순

**단점:**

- 응답 대기 시간 5-10초 (사진 개수와 무관하게 병렬 처리)
- 사진이 매우 많으면 타임아웃 위험 (30초 제한)

**프론트 호출 흐름:**

```
1. POST /photos/batch-upload  ← 5-10초 대기 (로딩 스피너)
2. 응답 받으면 바로 결과 화면 표시
3. GET /diaries/{diary_id}/analysis  ← 후보 조회 (선택적)
4. POST /diaries/{diary_id}/confirm  ← 확정
```

**실제 서버 코드:**

```python
# app/services/photo_service.py

async def batch_upload_photos(db, user_id, target_date, files):
    photo_infos = []

    # ========================================
    # 1단계: 파일 저장 + DB 저장 (순차 처리)
    # ========================================
    for file in files:
        # 1. EXIF 파싱
        exif_data = extract_exif_data(file.file)

        # 2. 시간대 분류
        time_type = classify_time_type(exif_data["taken_at"])

        # 3. Diary upsert
        diary = await get_or_create_diary(db, user_id, target_date, time_type)

        # 4. 파일 저장
        image_url = await save_uploaded_file(file)

        # 5. Photo 생성
        photo = Photo(diary_id=diary.id, image_url=image_url, ...)
        db.add(photo)
        await db.commit()

        photo_infos.append((photo, diary.id, time_type))

    # ========================================
    # 2단계: LLM 분석 (병렬 처리) - DB 접근 없이
    # ========================================
    analysis_results = await asyncio.gather(
        *[
            analyze_photo_data(photo.image_url, photo.id, photo.taken_location)
            for photo, _, _ in photo_infos
        ],
        return_exceptions=True,  # 개별 실패해도 전체 진행
    )

    # ========================================
    # 2-2단계: 분석 결과 DB 저장 (순차 처리)
    # ========================================
    for result in analysis_results:
        if isinstance(result, AnalysisData):
            await save_photo_analysis(db, result)

    # ========================================
    # 3단계: DiaryAnalysis 집계
    # ========================================
    diary_ids = set(diary_id for _, diary_id, _ in photo_infos)
    for diary_id in diary_ids:
        await aggregate_photo_analysis_to_diary(db, diary_id)

    # ========================================
    # 4단계: 응답 반환
    # ========================================
    return [PhotoUploadResult(...) for ...]
```

---

#### **2안: 비동기 + 폴링 방식 (미구현 - 대용량 업로드 시 고려)**

> 업로드는 즉시 응답하고, 분석은 백그라운드에서 수행. 프론트에서 폴링으로 상태 확인

```
┌─────────────┐     POST /photos/batch-upload      ┌─────────────┐
│   Frontend  │ ─────────────────────────────────▶ │   Backend   │
└─────────────┘                                    └─────────────┘
       │                                                 │
       │         즉시 응답 (1-2초)                        │
       ◀─────────────────────────────────────────────────┤
       {created: [{photo_id, diary_id}]}                 │
       │                                                 │
       │                                          ┌──────▼──────┐
       │                                          │ Background  │
       │                                          │   Tasks     │
       │                                          └──────┬──────┘
       │                                                 │
       │                                   ┌─────────────┼─────────────┐
       │                                   ▼             ▼             ▼
       │                              ┌────────┐   ┌────────┐   ┌────────┐
       │                              │Photo 1 │   │Photo 2 │   │Photo 3 │
       │                              │LLM 분석│   │LLM 분석│   │LLM 분석│
       │                              └────────┘   └────────┘   └────────┘
       │
       │     GET /diaries/{date} (폴링)
       │─────────────────────────────────────────────────▶
       │
       ◀─────────────────────────────────────────────────
       analysis_status: "processing"
       │
       │     (2초 후 다시 폴링)
       │─────────────────────────────────────────────────▶
       │
       ◀─────────────────────────────────────────────────
       analysis_status: "done"  ← 분석 완료!
```

**장점:**

- 업로드 응답이 즉시 (1-2초)
- 타임아웃 위험 없음
- 대용량 처리에 유리

**단점:**

- 프론트에서 폴링 로직 필요
- 구현이 조금 더 복잡

**프론트 호출 흐름 (2안 적용 시):**

> ⚠️ 아래는 **미구현된 2안**의 흐름입니다. 현재 1안에서는 폴링이 필요 없습니다.

```
1. POST /photos/batch-upload  ← 즉시 응답 (분석은 백그라운드)
2. 화면에 "분석 중..." 표시
3. GET /diaries?date=... 폴링 (2초 간격)  ← 백그라운드 분석 완료 여부 확인
   - analysis_status: "processing" → 계속 폴링
   - analysis_status: "done" → 폴링 중단
4. GET /diaries/{diary_id}/analysis  ← 후보 조회
5. POST /diaries/{diary_id}/confirm  ← 확정
```

**서버 코드 예시 (2안):**

```python
from fastapi import BackgroundTasks

@router.post("/batch-upload")
async def batch_upload_photos(
    ...,
    background_tasks: BackgroundTasks
):
    # 1단계: 파일 저장 + Diary 생성
    photos = []
    for file in files:
        photo = await save_and_create_photo(file, ...)
        photos.append(photo)

    # 2단계: 백그라운드 작업 등록 (즉시 반환)
    for photo in photos:
        background_tasks.add_task(analyze_photo, photo.id)

    return {"created": [...]}  # 즉시 응답
```

---

### **🎯 권장 선택 기준**

| 상황                       | 권장 방식               |
| -------------------------- | ----------------------- |
| MVP / 초기 개발            | **1안** (동기 + 병렬)   |
| 사진 1-5장 업로드가 대부분 | **1안** (동기 + 병렬)   |
| 10장 이상 대량 업로드      | **2안** (비동기 + 폴링) |
| 서버 안정성 중요           | **2안** (비동기 + 폴링) |

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

## **📆 3. 다이어리 조회 (프론트 메인 API)**

### **GET /diaries**

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
        "photos": [
          {
            "photo_id": 101,
            "image_url": "...",
            "analysis_status": "done"
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
                "photos": [...]
            },
            {
                "diary_id": 9,
                "time_type": "dinner",
                "analysis_status": "done",
                "restaurant_name": "스시히로바",
                "category": "일식",
                "cover_photo_url": "...",
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
                "photos": [...]
            }
        ]
    }
}
```

> 📌 **응답 구조 설명**
>
> - 날짜별로 그룹핑된 딕셔너리 형태
> - 다이어리가 없는 날짜도 빈 배열로 포함 (프론트에서 "기록 없음" UI 처리 용이)
> - 기간 조회 시 최대 31일로 제한 권장 (성능 보장)

````

---

## **📆 4. 다이어리 분석 후보 조회 (선택 화면용)**

### **GET /diaries/{diary_id}/analysis**

> “이 식당 맞나요?” 화면에서만 사용

```jsx
{
    "restaurant_candidates": [
    { "name": "명동교자", "confidence": 0.92 }
    ],
    "category_candidates": ["한식"],
    "menu_candidates": ["칼국수", "만두"]
}
````

## **📆 5. 다이어리 확정 (유저 선택 저장)**

### **POST /diaries/{diary_id}/confirm**

```jsx
{
    "restaurant_name": "명동교자",
    "category": "한식"
}
```

- 최초 확정
- 재수정
- 덮어쓰기 전부 여기서

➡️ 별도 PUT / PATCH 필요 없음

## **🧠 프론트 실제 호출 흐름**

```jsx
1. 로그인
2. 메인 화면 진입 → GET /diaries?start_date=...&end_date=...  ← 일주일 조회
3. 사진 여러 장 선택
4. POST /photos/batch-upload
5. GET /diaries?date=...  ← 해당 날짜 다이어리 갱신
6. (필요시) GET /diaries/{diary_id}/analysis
7. POST /diaries/{diary_id}/confirm
8. GET /diaries?date=...  ← 확정 후 갱신
```
