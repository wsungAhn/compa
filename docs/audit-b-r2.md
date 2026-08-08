# 감사 B r2 — 일일 수집 스코프 설계 (codex gpt-5.5)

- 일시: 2026-08-08 09:3x PDT · 대상: `docs/design-daily-collect-brand-sweep-2026-08-07.md`
- 감사자: `codex exec -m gpt-5.5`

| 심각도 | 건수 | 반영 | 기각 |
|---|---:|---:|---:|
| P0 | 0 | — | — |
| P1 | 2 | 2 | 0 |
| P2 | 2 | 2 | 0 |
| P3 | 2 | 2 | 0 |

**전건 반영. P1 두 건 모두 r1 반영이 만든 자체 모순이다** — 감사가 없었으면 구현자가
그 모순을 임의로 해석했을 것이다.

## P1-1 — Path A와 `persist_scraped` 계약 불일치

r1에서 호출부에 엄격 매처(`_find_exact_for_sweep`)를 넣으면서 §4.3 헬퍼는
`create_missing` 플래그를 그대로 뒀다. **매칭이 두 곳에 존재**하게 돼, 구현자가 헬퍼
안에서 다시 `get_or_create_product`/`find_matching_product`를 부르면 r1이 막은 LLM
팬아웃·오매칭이 그대로 되살아난다.

**반영**: 헬퍼를 `persist_events_for_product(db, product, platform, events) -> int`로
축소 — **저장만** 하고 매칭은 호출부에서 끝낸다. `create_missing` 플래그 삭제.
"상품명으로 묶기"는 순수 함수로 분리해 두 호출부가 공유.

## P1-2 — 반환값 계약 충돌

§4.3은 `-> tuple[set[uuid], int]`(product_id 집합, skipped), §4.4는 "실제 insert 건수".
서로 다른 계약이 한 문서에 있었다.

**반영**: 헬퍼 반환값을 **insert된 행 수(int)** 하나로 통일. §4.4의 "insert가 1건 이상인
상품 수"가 이 값 위에서 계산된다.

## P2-1 — platform 행 누락 시 조용히 0건

`_get_platform`이 `None`이면 `_collect_platform:265-267`이 조용히 return한다.
**리뷰어 실측**: 공홈 26개 전부 platform 행 보유 → 현재는 발화하지 않는다.
그래도 조용한 실패 모드이므로 §4.3.1 신설 — `fail` 계수 + warning + 스모크 선행조건.
T13 신설.

## P2-2 — 기존 동작 제거가 명시적으로 승인되지 않았다

브랜드 스윕 전용으로 바꾸면 `name_kr` 4개에 대한 Sephora/Amazon/Rakuten 일일 갱신이
사라진다(116콜 → 0). **반영**: §4.2.0 신설 — 의도된 제거임을 명시하고 근거 기재
(4개 중 2개는 `name_kr`에 영어가 든 오염 행, 검색 경로 자체는 사용자 검색·
`run_collection_slow`로 유지, 재도입은 §7-1 선행). T11로 고정.

## P3 2건

- 테스트 수 stale("신규 6케이스" → 실제 14) → 정정
- `limit=250` 경계 관측 부재 → `len(products) == 250`이면 warning, T12 신설

## 리뷰어 소견

r1이 P1을 고치면서 **새 P1 두 개를 만들었다.** 한 곳(호출부)만 고치고 짝이 되는
계약(헬퍼 시그니처·반환값)을 안 맞춘 탓이다. `feedback_fix_pattern_not_instance`의
변형 — 인스턴스가 아니라 **계약의 양쪽**을 봐야 했다. 다음 라운드에서 같은 실수를
반복하지 않으려면, 시그니처를 바꿀 때 그 함수의 **모든 호출부와 반환값 소비처**를
같은 편집에서 확인해야 한다.
