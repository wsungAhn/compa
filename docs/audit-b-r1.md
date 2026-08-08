# 감사 B r1 — 일일 수집 스코프 설계 (codex gpt-5.5)

- 일시: 2026-08-08 09:1x PDT
- 대상: `docs/design-daily-collect-brand-sweep-2026-08-07.md`
- 감사자: `codex exec -m gpt-5.5` (subagent 대체 아님)

## 판정 요약

| 심각도 | 건수 | 반영 | 기각 |
|---|---:|---:|---:|
| P0 | 0 | — | — |
| P1 | 2 | 2 | 0 |
| P2 | 4 | 4 | 0 |
| P3 | 1 | 1 | 0 |

**전건 반영.** 리뷰어가 지적 7건을 전부 실물(코드·라이브 DB)로 재확인했고 오류는 없었다.

## P1-1 — `create_missing=False`가 "기존 상품만 갱신"을 보장하지 않는다

**지적**: `find_matching_product`는 exact match 실패 시 브랜드 후보 휴리스틱과
Claude fallback으로 넘어간다. 신규 카탈로그 상품이 기존 행에 잘못 붙을 수 있다.

**리뷰어 검증** (`backend/app/ai/matcher.py:109-183` 직접 판독):

| 단계 | 실제 동작 |
|---|---|
| 1 | country 컬럼 normalized exact |
| 2 | 브랜드 후보 **1개**면 `_same_product_evidence` 토큰 겹침 휴리스틱으로 매칭 |
| 3 | 브랜드 후보 **여럿** + `anthropic_api_key` 있으면 `_ask_claude_for_match` 호출 |

**지적보다 심각하다.** 오매칭뿐 아니라 **비용 문제**가 있다. DB 실측 Laneige 79 ·
Tatcha 68 · Beauty of Joseon 63개 → 카탈로그 2,388건 스윕 시 exact 불일치 대다수가
Stage 3로 떨어져 **일일 수집 1회에 Claude 호출 수천 건**이 나간다.

**반영**: §4.2.1 신설 — 스윕 전용 엄격 매처 `_find_exact_for_sweep`
(brand exact AND name_en normalized exact, 휴리스틱·LLM 없음). `find_matching_product`
자체는 건드리지 않는다(사용자 검색 경로엔 그 유연함이 맞다). T7·T8 신설.

## P1-2 — 브랜드 단위 try/except로는 실패를 못 센다

**지적**: `ShopifyBrandScraper.scrape()`가 HTTP/JSON 실패를 내부에서 삼키고
`confidence=0.0` sentinel을 반환한다. 403/500이어도 `ok=26 fail=0`으로 보고된다.

**리뷰어 검증** (`backend/app/scrapers/brands/shopify.py:134,146` 판독): 사실.
`except Exception` → `logger.warning` → `[ScrapedEvent(confidence=0.0, raw_text=...)]`.
빈 응답(엔드포인트 폐쇄)도 같은 형태. 배경 실측도 이를 뒷받침한다 — Drunk Elephant 410,
Fresh·YTTP 403으로 실제 닫힌 브랜드가 있다.

**반영**: §5.1 신설 — sentinel 판정 규칙(이벤트 1건이고 `confidence==0.0`, 또는
`confidence>0` 이벤트가 0건 → 실패). T5·T5b 신설.

## P2 4건 (전건 반영)

| 지적 | 리뷰어 확인 | 반영 |
|---|---|---|
| 수치가 낡음 (active=339, sale_events=156) | 라이브 DB로 확인 — 339/314/21/0, 156 | §1 갱신 + "분모가 계속 자란다" 명시 |
| 코드 경로 불일치 (`backend/` 누락, `app/scrapers/matcher.py` 부재) | 사실 | 헤더 대상 파일 정정 |
| "갱신된 상품 수" 의미 불명확 — 중복만 쌓여도 211 | 사실. `_save_events`는 반환값 없음 | §4.4 반환값을 **실제 insert된 상품 수**로 정의, T9 신설 |
| `?limit=250` 한 페이지, pagination 없음 | `shopify.py:21,113` 확인. 실측 최대 232로 지금은 미발화 | §4.2.2 신설 — "첫 250건"으로 범위 한정 |

## P3 1건

선행조건 문구가 stale(NullPool 머지됨) → "해결됨"으로 정정.

## 리뷰어 소견

감사가 **설계의 핵심 가정 하나를 무너뜨렸다.** 초안은 `find_matching_product`를
"기존 함수를 재사용하는 lazy solution"으로 제시했는데, 그 함수가 실은 LLM을 부르는
퍼지 매처였다. 재사용이 오히려 더 비싸고 위험한 경우였고, 새 함수를 쓰는 쪽이
단순·저렴·안전하다. **"기존 함수 재사용"이 항상 게으른 정답은 아니다 — 그 함수가
무엇을 하는지 읽고 나서 판단해야 한다.**
