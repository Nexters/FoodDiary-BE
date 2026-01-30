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

| **필드**    | **설명**                         |
| ----------- | -------------------------------- |
| id          | PK                               |
| provider    | google / apple                   |
| email       |                                  |
| provider_id | OAuth Provider에서 제공해주는 id |

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
| photo_counts    | 다이어리에 포함된 사진의 수 (기본값: 0)                        |

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

![image.png](attachment:412d73f4-2f9d-4eaf-9728-79aa0dda9ba0:image.png)

# **FoodDiary API 설계**

## **✅ 1. 인증 (Authentication)**

### **POST /auth/login**

> Google 또는 Apple OAuth 로그인 (클라이언트에서 id_token 전송)

```
Request:
{
    "provider": "google", // or "apple"
    "id_token": "<OAuth ID token>"
}

Response:
{
    "user_id": "abc123",
    "access_token": "<JWT>"
    "is_first" = "flase" // or "true" 처음 로그인 한 사람인 경우
}
```

---

## **🖼️ 2. 사진 업로드 및 분석 (Photo Upload & Analysis)**

### **POST /photos/batch-upload**

📌 사진 여러 장을 **파일로 직접 업로드**

서버가:

- EXIF 파싱
- 시간대 기준 끼니 분류
- 다이어리 생성/연결
- Photo 레코드 생성

### **Request (multipart/form-data)**

```
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Form fields**

| **필드** | **타입** | **설명**      |
| -------- | -------- | ------------- |
| date     | string   | 2026-01-19    |
| photos[] | file     | 이미지 파일들 |

> EXIF에서 taken_at, GPS 추출

---

### **Response**

```
{
    "created": [
    {
        "photo_id": 101,
        "diary_id": 12,
        "time_type": "lunch"
    },
    {
        "photo_id": 102,
        "diary_id": 13,
        "time_type": "dinner"
    }
    ]
}
```

---

### **🔧 서버 내부 처리 순서 (중요)**

```
1. 이미지 파일 수신
2. 파일 저장 (ex: /data/photos/{uuid}.jpg)
3. EXIF 파싱 (taken_at, lat/lng)
4. 시간대 기준 끼니 분류
5. Diary upsert (user + date + time_type)
6. Photo insert
7. 분석 작업 enqueue
```

---

## **📆 3. 다이어리 조회 (프론트 메인 API)**

### **GET /diaries/{date}**

```
{
    "date": "2026-01-19",
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
```

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
```

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
2. 사진 여러 장 선택
3. POST /photos/batch-upload
4. GET /diaries/{date}  ← 화면 렌더
5. (필요시) GET /diaries/{diary_id}/analysis
6. POST /diaries/{diary_id}/confirm
7. GET /diaries/{date}  ← 갱신
```
