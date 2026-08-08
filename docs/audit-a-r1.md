# 감사 A — 라운드 1 (`design-async-engine-pool-2026-08-08.md`)

- 일시: 2026-08-08 PDT · Mac Studio
- 감사자: `codex exec` (codex 0.141.0, 실제 CLI 호출 — subagent 대체 아님)
- 결과: **7건 (P0 0 · P1 3 · P2 3 · P3 1)** → 6건 반영, 1건 기각

지적은 위치만 신뢰하고 산수·사실관계는 전부 직접 재확인했다. 아래 "검증" 열이 그 기록이다.

## 판정표

| # | 심각도 | 지적 | 검증 (직접 실측) | 판정 |
|---|---|---|---|---|
| 1 | P1 | §5가 비용을 지연시간(+5.5ms)으로만 축소했다. NullPool은 **커넥션 상한을 제거**한다 | **타당.** `gather` 팬아웃 폭 29 실측(`get_enabled_scrapers()` 29, `SKIP_SCRAPERS` 0). QueuePool 상한 15/프로세스 → NullPool 무제한. worker 2 × 29 = **58**, PG `max_connections`=100 − reserved 3 = **97** 가용, 평시 8 사용 | **반영** — §5에 실측표 + 부채 트리거 3개(동시성 3↑ / 스크래퍼 40↑ / uvicorn workers 도입) 명시 |
| 2 | P1 | 문서가 `app/...`·`tests/...`로 적었으나 실제는 `backend/` 하위 | **타당.** 실제 경로 `backend/app/core/database.py` 확인 | **반영** — §7에 `cd backend` + venv 절대경로 고정 |
| 3 | P1 | T1이 DB 없으면 스킵 → CI에서 핵심 회귀 방어가 사라진다 | **타당.** `.github/workflows/ci.yml` 확인 — **postgres 서비스 없음**. CI에선 T1이 항상 스킵되고 T2만 남는 것이 사실 | **반영** — §6에 "완료 판정은 로컬 DB T1 `passed` 근거로만", 스킵 사유 문자열 명시. CI에 PG 붙이는 것은 별건(§8) |
| 4 | P2 | 원인 귀속에 공유 세션 동시사용 배제 근거가 없다 | **타당(부정 결과 확인).** `collect_on_demand:363`·`collect_fast:324`가 `gather` 팬아웃하지만 `_collect_platform:257`이 `async with AsyncSessionLocal()`로 **자기 세션을 연다**. 공유 세션 동시 사용 증거 없음 | **반영** — §3에 배제한 경합 가설로 기록 |
| 5 | P2 | "Celery 전용 엔진 분리" 기각이 성급하다. 분기를 `database.py`에 가두면 된다 | **절반만 타당.** sessionmaker를 나눠도 **11개 `asyncio.run()` 호출지점이 각자 옳은 것을 골라야** 하고, 새 태스크가 `AsyncSessionLocal`을 그냥 쓰면 P0가 조용히 재발한다 — 문서가 이미 기각한 `dispose()` 안과 동일한 실패 양식. 게다가 #1 실측으로 58 < 97 헤드룸 확인됨 | **기각** — 단 기각 근거를 실측 기반으로 §5에서 재작성 |
| 6 | P2 | 롤백 기준이 없다 | **타당.** 운영 재시작을 동반하는데 되돌릴 조건이 문서에 없었다 | **반영** — §7.1 신설 (커넥션 피크 80 이상 / `too many connections` 1건 이상 → 즉시 revert) |
| 7 | P3 | T1이 `SELECT 1`이면 ORM/commit 경로를 안 본다 | **타당.** 실패한 프로덕션 경로는 ORM 세션이다 | **반영** — §6에 ORM 쿼리 + `commit()` 포함 명시 |

## 독립 검증 — 설계 전제 재현

감사와 별개로 근본 원인과 처방을 직접 재현했다 (`/tmp/repro_pool.py`, 라이브 DB):

```
=== BEFORE (AsyncAdaptedQueuePool) ===
run #1: OK (303 products)
run #2: FAIL RuntimeError: Task ... attached to a different loop
run #3~#6: FAIL InterfaceError: another operation is in progress
=== AFTER (NullPool) ===
run #1~#6: OK (303 products)   => 6/6
```

문서 §3의 재현(1/4 성공)·§4의 처방(6/6)이 **재확인**됐다. 상품 수는 426 → 303으로
바뀌었는데, 이는 문서 §3 작성 시점 이후 DB 상태 변화이며 결론에 영향 없다.

## P0/P1 잔여

- 반영 후 P0 **0건**, P1 **0건** (3건 전부 반영 완료)
- 수렴 조건(P0/P1 0건 2회 연속) 충족까지 **1회 더** 필요 → 라운드 2 진행
