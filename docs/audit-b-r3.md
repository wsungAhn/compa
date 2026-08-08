# 감사 B r3 — 일일 수집 스코프 설계 (codex gpt-5.5)

- 일시: 2026-08-08 09:4x PDT · 감사자: `codex exec -m gpt-5.5`

| 심각도 | 건수 | 반영 | 기각 |
|---|---:|---:|---:|
| P0 | 0 | — | — |
| P1 | 2 | 2 | 0 |
| P2 | 2 | 2 | 0 |
| P3 | 1 | 1 | 0 |

**전건 반영. 미수렴 3라운드째** — P0/P1 0건이 아직 한 번도 안 나왔다.

## P1-1 — "26개"는 설정에 달려 있고, 0개면 조용히 성공한다

`get_enabled_scrapers()`가 미존재·오타 이름을 조용히 무시하므로
`enabled ∩ BRAND_SCRAPERS`가 0이면 태스크가 **0콜·0저장으로 정상 종료**한다.

**리뷰어 실측**:

| 출처 | 값 | 결과 |
|---|---|---|
| 라이브 settings | `'Sephora,Amazon US,Rakuten,brands'` (config.py 기본값) | ∩ = 26 ✅ |
| `backend/.env` | `ENABLED_SCRAPERS` 없음 | 기본값 사용 → 정상 |
| `backend/.env.example` | `ENABLED_SCRAPERS=네이버쇼핑,Rakuten` | ⚠️ `brands` 없음 |

지금은 정상이나 `.env.example`이 함정이다 — 복사해서 `.env`를 만들면 브랜드 0개가 되고,
거기 적힌 `네이버쇼핑`은 API가 2026-07에 종료된 플랫폼이다.

**반영**: §4.2.-1 신설 — 대상 0개면 `logger.error` + 즉시 반환(성공 보고 금지),
`.env.example` 정정을 이번 범위에 포함, 스모크 선행조건 추가. T16 신설.

## P1-2 — 브랜드 예외를 잡으면 `rollback` 없이는 이후 전량 죽는다

DB 예외 후 SQLAlchemy 세션은 실패 상태로 고착된다. `except: continue`만 있으면
로그엔 "1개 실패"로 보이지만 실제로는 그 시점 이후 모든 브랜드의 저장이 연쇄 실패한다.

**반영**: §5.1.1 신설 — `await db.rollback()` 필수. **T4 강화**: "예외 후 다음 브랜드
진행"으로는 부족하고 **"DB 저장 예외 후 다음 브랜드의 저장이 실제로 성공"**까지 봐야
한다(rollback을 빼도 전자는 통과한다).

## P2-1 — dedup key 불일치로 용량 variant가 유실된다 (기존 버그)

**리뷰어 실측 확인**:

```
DB 유니크 인덱스 : ... COALESCE(size_ml, -1)      (d1e2f3a4b5c6_dedup_by_size.py)
_event_signature: (event_name, sale_price, original_price, start_date)   ← size_ml 없음
```

같은 상품·플랫폼·날짜에 **가격이 같은 다른 용량**이 오면 DB는 허용해야 하는데 precheck가
먼저 버린다. 공홈 스윕은 variant별 이벤트를 대량으로 밀어넣으므로 노출 빈도가 급증한다.

**반영**: 이번 범위에서 같이 고친다. 권장안은 **precheck 제거 +
`INSERT ... ON CONFLICT DO NOTHING RETURNING id`** — dedup 진실을 DB 한 곳에만 두면 두
정의가 다시 어긋날 수 없고, §4.4가 요구하는 실제 insert 수도 같은 쿼리로 나온다. T15 신설.

## P2-2 — `_find_exact_for_sweep`의 다중 후보 계약 부재

`Product`에 `(brand, name_en)` 유니크가 없어 같은 키의 행이 2개 이상 있을 수 있다.
**반영**: 0개→None, 1개→그것, 2개+→warning 후 None(skipped). `scalar_one_or_none()`으로
예외를 내지 않는다. T14 신설.

## P3 — 250 warning 구현 위치 불명확

`parse_products()` 이후엔 raw payload 길이가 안 남는다 → `scrape()`가
`parse_products()` 호출 **직전**에 남기도록 명시.

## 리뷰어 소견

r3의 P1 둘은 r1·r2와 성격이 다르다. r1·r2는 **설계 내부의 모순**이었는데, r3는
**설계가 기대는 외부 전제**(설정값·세션 상태 머신)를 건드린다. 매 라운드 새로운 층이
나오고 있어 "취향 논쟁 전환"은 아직 아니다 — 계속할 근거가 있다.

테스트가 6개 → 17개로 늘었다. 늘어난 11개 중 9개가 **"조용한 실패"를 잡는 것**이다
(0건인데 성공 보고, sentinel, rollback 누락, 다중 후보, dedup 유실, 경계 도달).
이 설계의 위험이 "틀리게 동작"이 아니라 "아무것도 안 하면서 정상으로 보임"에 몰려 있다.
