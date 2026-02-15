# 🧪 테스트 모드 API 가이드

프론트엔드 개발/테스트용 mock 데이터 API

---

## 🎯 빠른 참조 (Quick Reference)

### 테스트 시나리오별 날짜

| 테스트 목적      | 날짜                                        | 상태         | 내용                                 |
| ---------------- | ------------------------------------------- | ------------ | ------------------------------------ |
| **분석 중 상태** | `2026-01-19`                                | `processing` | 점심 1개 (분석 중) + 저녁 1개 (완료) |
| **분석 중 상태** | `2026-01-25`                                | `processing` | 점심 1개 (분석 중) + 저녁 1개 (완료) |
| **여러 끼니**    | `2026-01-01`                                | `done`       | 점심 + 저녁 2개                      |
| **하루 1끼**     | `2026-01-02`                                | `done`       | 아침 1개만                           |
| **빈 날짜**      | `2026-01-03`                                | -            | 다이어리 없음                        |
| **일주일 조회**  | `start_date=2026-01-01&end_date=2026-01-07` | -            | 다양한 패턴                          |

### Mock 데이터 패턴

```
끝자리 1, 4, 7 (1일, 4일, 7일, 10일...) → 점심 + 저녁 2개
끝자리 2, 5, 8 (2일, 5일, 8일, 11일...) → 아침 1개
끝자리 3, 6, 9, 0 (3일, 6일, 9일, 12일...) → 빈 날짜

⚠️ 예외: 19일, 25일 점심은 processing 상태
```

---

## 📋 API 목록

### 1. POST /photos/batch-upload?test_mode=true

**즉시 응답 (LLM 호출 없음)**

```bash
curl -X POST "http://localhost:8000/photos/batch-upload?test_mode=true" \
  -H "Authorization: Bearer $TOKEN" \
  -F "date=2026-01-20" \
  -F "photos=@photo1.jpg" \
  -F "photos=@photo2.jpg"
```

**응답:**

```json
{
  "results": [
    {
      "photo_id": 100,
      "diary_id": 20,
      "time_type": "breakfast",
      "image_url": "https://picsum.photos/seed/mock0/400/300",
      "analysis_status": "processing" // 항상 processing
    }
  ]
}
```

---

### 2. GET /diaries?date={날짜}&test_mode=true

**특정 날짜 조회**

```bash
# 분석 중 상태 테스트
curl "http://localhost:8000/diaries?date=2026-01-19&test_mode=true" \
  -H "Authorization: Bearer $TOKEN"

# 완료 상태 테스트
curl "http://localhost:8000/diaries?date=2026-01-01&test_mode=true" \
  -H "Authorization: Bearer $TOKEN"

# 빈 날짜 테스트
curl "http://localhost:8000/diaries?date=2026-01-03&test_mode=true" \
  -H "Authorization: Bearer $TOKEN"
```

**날짜 범위 조회**

```bash
curl "http://localhost:8000/diaries?start_date=2026-01-01&end_date=2026-01-31&test_mode=true" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 3. GET /diaries/{diary_id}?test_mode=true

**다이어리 상세 조회**

```bash
# 아무 ID나 입력 가능 (동적으로 생성됨)
curl "http://localhost:8000/diaries/123?test_mode=true" \
  -H "Authorization: Bearer $TOKEN"
```

---
