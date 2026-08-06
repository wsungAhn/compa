# 설계 — 가격 위치 + 세일 캘린더 추천 (2026-08-05)

> **핵심 가치 재정의(사용자)**: 국제 비교만이 아니라, **사용자가 주로 쓰는
> 통화·사이트 기준으로 "지금 이 가격이 최대 할인에서 얼마나 떨어져 있는가",
> 그리고 "반복되는 정기 세일까지 얼마나 남았는가"** 를 검색 시점에 알려주는 것.

## 배경 — 현행 엔진은 우리 데이터로 절대 작동하지 않는다

`api/products.py:_build_recommendation`은 세 분기로 판단한다.

| 분기 | 필요 데이터 | 실제 데이터(2026-08-05 실측) |
|---|---|---|
| `active_surprise` | `event_type='surprise'` + `start~end` 기간 | `end_date` **0건**, `event_type` 전부 **None** |
| `active_regular` | 기간 내 regular 이벤트 + `discount_rate` | 위와 동일 |
| `upcoming` | **미래** `start_date`를 가진 regular 이벤트 | `start_date`가 전부 수집일(오늘) 또는 None |

스크래핑으로는 "다음 블랙프라이데이 시작일" 같은 미래 일정이 오지 않는다. 오는 것은
**오늘 시점의 가격**뿐이다. 그래서 위젯은 언제나 마지막 폴백("할인 이력이 충분하지
않습니다")만 출력한다. 기능이 없는 게 아니라 **닿을 수 없는 입력을 기다리고 있다.**

## 선행조사

### ① 레포 내 검색

| 이미 있는 것 | 재사용 여부 |
|---|---|
| `_build_recommendation` + `Recommendation` 스키마 | 스키마는 확장, 판단 로직은 교체 |
| `WaitBuyWidget.tsx` (verdict/reason/D-day/예상할인율 표시) | **그대로 재사용** — 필드 계약이 같으면 프론트 수정 불필요 |
| `ai/classifier.py:_KNOWN_REGULAR_EVENTS` (블프·프라임데이·11.11·6.18 월 매핑) | **세일 캘린더의 씨앗** — 월만 있고 날짜·주기가 없어 D-day를 못 낸다 |
| `core/fx.py:convert()` | 통화 환산에 그대로 사용 |
| `sale_events.created_at` | **가격 시계열의 사실상 유일한 축** (start_date는 신뢰 불가) |

### ② 외부

가격 추적 제품(카멜카멜카멜·Keepa)의 표준 관례를 따른다 — **관측 가격 시계열의
최저/중앙/최고 대비 현재 위치**를 보여주고, 미래 일정은 **알려진 세일 달력**으로
채운다. 둘 다 LLM 없이 계산되는 결정적 지표다(Deterministic First).

### ③ 결론

판단 근거를 `discount_rate`·`start_date`(못 얻는 것)에서 **`created_at` 기준 가격
시계열 + 큐레이트된 세일 캘린더**(둘 다 확실히 가진 것)로 옮긴다.

## 설계

### 1. 세일 캘린더 (`app/core/sale_calendar.py`)

연 1회 이상 반복되는 세일을 **규칙으로 열거**한다(고정일 또는 "11월 넷째 목요일
다음날" 같은 규칙). 스크래핑 대상이 아니다.

```
SALES = [
  ("Black Friday", 11월 넷째 금요일, 국가 US/GLOBAL, 기대할인 큼),
  ("Cyber Monday", 그 다음 월요일),
  ("Amazon Prime Day", 7월 중순 — 연도별 변동 → 월 단위 근사),
  ("11.11", 11/11, CN), ("6.18", 6/18, CN),
  ("Sephora Savings Event", 4월·11월), ...
]
```

`next_sale(today, country)` → `(이름, 날짜, D-day)`.

### 2. 가격 위치 (`app/core/price_position.py`)

플랫폼별 `sale_price` 시계열(= `created_at` 순 관측치)에서:

- `observed_min` / `observed_max` / `current`
- `position_pct` = 최저가 대비 몇 % 비싼가 → **"최대 할인에서 얼마나 떨어져 있나"**
- `off_list_pct` = 정가(`original_price`) 대비 할인율 — 오늘 당장 계산 가능
- `history_days` = 관측 기간. **얕으면 얕다고 말한다**(부풀리지 않음)

### 3. 추천 판단 (교체)

```
정가 대비 할인 중 & 관측 최저 근접(≤2%)  → buy_now  "역대 최저 수준"
관측 최저 대비 +10% 이상 & 다음 세일 D-60 이내 → wait  "{세일}까지 D-N"
그 외                                     → good_deal
관측 3일 미만                              → good_deal + "이력 N일" 명시
```

기존 `Recommendation` 필드(verdict/reason/next_event_name/days_until_next/
expected_discount)를 유지하고 가격 위치 필드를 **추가**한다 → 프론트 무수정 동작.

### 4. 사용자 통화

`comparison` API의 `preferred`(플랫폼명)에 더해 **`currency` 파라미터**를 받는다.
지정 시 모든 대안 가격을 그 통화로 환산해 정렬한다. 사용자는 "내 통화"만 고르면
되고 플랫폼을 몰라도 된다.

## 범위 밖 (다음 레이어)

- 관측 이력에서 세일 주기를 **자동 추출**(캘린더에 없는 브랜드 자체 세일). 최소 몇
  달치 시계열이 쌓인 뒤에 의미가 있다
- 크로스 통화 비교의 전제인 **제품 매칭**(현재 Rakuten JP와 US 상품이 다른 product로
  갈린다 — `matcher.py`가 brand에 의존하는데 Rakuten이 brand를 안 채운다)
- 환율 실시간 조회(현재 정적 테이블)
