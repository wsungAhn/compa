# API 엔드포인트 명세

Base URL: `http://localhost:8000`

## GET /health
서버 상태 확인.
```json
{ "status": "ok", "version": "0.1.0" }
```

---

## GET /api/products/search

제품 검색. DB 조회 후 누락된 플랫폼은 실시간 수집 트리거.

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| q | string | ✅ | 검색어 (언어 무관) |
| lang | string | - | ko/en/ja/zh (기본 ko) |

```json
[
  { "id": "uuid", "name_kr": "설화수 윤조에센스", "name_en": "...", "brand": "설화수", "category": "base" }
]
```

---

## GET /api/products/{product_id}/events

3년치 할인 이력 + 구매 추천.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| years | int | 3 | 조회 기간 (1~5) |
| country | string | all | all / KR / US / JP / CN |

```json
{
  "product": { "id", "name_kr", "name_en", "brand", "category" },
  "events": [
    {
      "id", "event_name", "event_type",
      "platform_name", "platform_country",
      "sale_price", "original_price", "discount_rate", "currency",
      "scraped_name",
      "is_bundle",
      "start_date", "end_date",
      "confidence", "source_url"
    }
  ],
  "recommendation": {
    "verdict": "wait | buy_now | good_deal",
    "reason": "...",
    "next_event_name": null,
    "days_until_next": null,
    "expected_discount": null
  }
}
```

**추천 로직:**
1. 현재 진행 중인 돌발 할인 → `buy_now`
2. 현재 가격이 역대 최고 할인율 수준 → `buy_now`
3. 60일 이내 정기 행사 예정 → `wait` (D-day 포함)
4. 과거 할인 이력 있음 → `good_deal` (평균 할인율)
5. 이력 없음 → `good_deal` (판단 불가)

---

## GET /api/products/{product_id}/comparison

플랫폼 간 현재가 비교.

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| preferred | string | ✅ | 선호 플랫폼명 |
| platforms | string | - | 쉼표 구분 플랫폼 목록 (기본 전체) |

```json
{
  "preferred": { "platform_name": "Sephora", "sale_price": 38.0, "currency": "USD", "source_url": "..." },
  "alternatives": [
    { "platform_name": "Rakuten", "sale_price": 4200, "currency": "JPY", "saving_vs_preferred": 12.5 }
  ],
  "cheapest_platform": "Rakuten",
  "cheapest_saving_pct": 12.5
}
```
