# Celery 태스크 전면 실패 수정 — asyncio 이벤트 루프와 커넥션 풀 불일치

- 작성: 2026-08-08 PDT · Mac Studio (`mac.lan`)
- Tier: **2** (`review-tiers.md:63` — persistence 계층 동작 변경, 전 태스크·API 영향)
- 대상 파일: `app/core/database.py`, `tests/core/test_database_event_loop.py`(신규)
- 워크트리: `.worktrees/collect-daily-scope` (브랜치 `design/collect-daily-scope`)
- 선행: 이 문서가 `design-daily-collect-brand-sweep-2026-08-07.md`보다 **먼저** 랜딩돼야 한다
  (수집 스코프를 고쳐도 태스크 자체가 실행되지 않는다 — §1 참조)

---

## 1. 문제

compa Celery 파이프라인이 **2026-08-05 19:15부터 사흘째 84% 실패** 중이다.

`worker.err.log` 전수 집계 (2026-08-08 04:15 기준):

| 태스크 | 성공 | 실패 | 성공률 |
|---|---:|---:|---:|
| `classify_pending` | 3 | 54 | 5% |
| `collect_slickdeals_signals` | 23 | 63 | 27% |
| `extract_social_posts` | 5 | 53 | 9% |
| `purge_expired_social_posts` | 0 | 44 | **0%** |
| `collect_reddit_signals` | 17 | 28 | 38% |
| `collect_social_for_products` | 0 | 10 | **0%** |
| `match_pending_products` (D단계) | 0 | 3 | **0%** |
| `collect_all_products` | 0 | 2 | **0%** |
| `run_collection_slow` | 0 | 2 | **0%** |
| **합계** | **48** | **259** | **16%** |

`another operation is in progress` 1,000회. 2026-08-07 12:00 worker 재시작 이후에도
계속되므로 stale 프로세스가 아니라 코드 결함이다.

**이것이 `design-daily-collect-brand-sweep-2026-08-07.md`의 선행 조건인 이유**:
`collect_all_products`가 0/2다. 수집 스코프를 아무리 정확히 고쳐도 태스크가 실행 자체를
못 한다.

## 2. 선행조사

- 레포 내 검색: `create_async_engine` **1곳**(`app/core/database.py:8`)뿐이고 `NullPool`·
  `poolclass`·`pool_size` 사용처 **없음**. `asyncio.run()` 호출지점은 **11곳**
  (`collect.py:14,43` `classify.py:15` `social_extract.py:11` `seed.py:11`
  `social_collect.py:14` `match_products.py:22` `reddit_signals.py:30,87,147`
  `scripts/refresh_sale_timing.py:125`) — 전부 같은 모듈 레벨 엔진을 공유한다.
  `alembic/env.py:33`은 `engine_from_config`로 별도 동기 엔진이라 무관
- 외부 선행작업: SQLAlchemy asyncio 문서가 "이벤트 루프를 넘나드는 커넥션 재사용 금지"를
  명시하고, 루프 수명이 짧은 컨텍스트(스크립트·워커)에 `NullPool`을 권고한다. Celery
  prefork + `asyncio.run()` 조합에서 이 오류가 나오는 것은 널리 알려진 패턴이다.
  **코드 채택 없음(설정 한 줄) — 라이선스·커밋일 검토 불요**
- 결론: **기존 의존성으로 해결.** SQLAlchemy가 이미 제공하는 `NullPool`을 지정한다.
  새 모듈·새 추상화·태스크별 배선 변경 없음

## 3. 근본 원인 (실물 재현)

모듈 레벨 엔진(`database.py:8`)이 기본 `AsyncAdaptedQueuePool`을 쓴다. Celery 태스크는
매번 `asyncio.run()`으로 **새 이벤트 루프**를 만든다. `asyncio.run()`이 끝나면 루프는
닫히지만 asyncpg 커넥션은 풀에 남고, 그 커넥션의 프로토콜 객체는 **닫힌 루프에 묶여
있다.** 다음 태스크가 그 커넥션을 체크아웃하면 터진다.

프로덕션과 동일 조건(같은 프로세스, 연속 `asyncio.run()`)으로 재현:

```
run #1: OK (426 products)
run #2: ❌ RuntimeError: Task ... attached to a different loop
run #3: ❌ InterfaceError: cannot perform operation: another operation is in progress
run #4: ❌ InterfaceError: cannot perform operation: another operation is in progress
```

**첫 건만 성공하고 이후 실패** — §1 표의 "일부만 성공"(prefork 프로세스당 첫 태스크는
신규 커넥션이라 통과) 분포와 정확히 일치한다.

## 4. 설계

```python
# app/core/database.py
from sqlalchemy.pool import NullPool

engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
```

`NullPool`은 세션마다 커넥션을 새로 열고 반납 시 닫는다. 풀에 남는 커넥션이 없으므로
루프를 넘나드는 재사용이 **구조적으로 불가능**하다.

검증 (같은 재현 스크립트에 `NullPool`만 적용):

```
run #1~#6: OK (426 products)  =>  6/6 성공
```

## 5. 설계 부채 트레이드오프 (Tier 2 워크플로 C)

**대가**: 커넥션 풀링을 API 경로에서도 잃는다. 실측:

| | 세션당 |
|---|---|
| 기본 풀(QueuePool) | 0.62 ms |
| NullPool | 6.16 ms |
| 차이 | **+5.53 ms** |

FastAPI `get_db`는 요청당 세션 1개라 **요청당 +5.5ms**다. 이 서비스는 응답시간이
스크래핑·외부 API에 지배되므로 무시할 수 있는 값으로 판단했다.

**검토했으나 채택하지 않은 대안**:

| 대안 | 왜 안 했나 |
|---|---|
| Celery 전용 엔진 분리 (API는 풀 유지) | 엔진이 2개가 되고 어느 세션이 어느 엔진인지 호출부가 알아야 한다. 5.5ms를 사려고 영구적 분기를 추가하는 거래 |
| 태스크마다 `await engine.dispose()` | 11개 호출지점 전부 수정해야 하고, 새 태스크를 추가할 때마다 잊으면 재발한다. 한 줄로 구조적으로 막는 쪽이 낫다 |
| `pool_pre_ping=True` | 죽은 루프 문제를 못 고친다. ping 자체가 같은 커넥션에서 나가므로 똑같이 터진다 |

**부채가 되는 조건**: API 트래픽이 늘어 +5.5ms나 PG `max_connections`가 문제가 되면
그때 Celery 전용 엔진으로 분리한다. 지금 나누면 근거 없는 추측 최적화다.

## 6. 테스트 계획 (Tier 2 워크플로 D)

`tests/core/test_database_event_loop.py` 신규.

| # | 케이스 | 방어하는 회귀 |
|---|---|---|
| T1 | 같은 프로세스에서 `asyncio.run()`을 **3회 연속** 호출해 세션 쿼리가 전부 성공 | **이 P0의 본질.** 1회만 돌리는 테스트는 이 버그를 절대 못 잡는다 |
| T2 | `engine.pool`이 `NullPool` 인스턴스 | 누가 풀을 되돌리면 즉시 실패 |

T1은 실제 DB가 필요하다. 기존 테스트 스위트가 DB 없이 도는 구조면 `pytest.mark.skipif`로
DB 미가용 시 스킵하되, **스킵을 통과로 보고하지 마라** — 스킵이면 그 사실을 명시할 것.

베이스라인: 484 passed, 1 skipped (2026-08-07 워크트리 실측).

## 7. 검증 절차 (Verification Before Done)

1. `PYTHONPATH=. <venv>/bin/python -m pytest tests/ -q` → 484+ passed
2. `PYTHONPATH=. <venv>/bin/python -m mypy --strict app/` → clean
3. 재현 스크립트 재실행 → `asyncio.run()` 6연속 전부 성공
4. **worker/beat 재시작** (사용자 승인됨, 2026-08-08) —
   `launchctl kickstart -k gui/$(id -u)/com.compa.worker` / `.beat`
5. 재시작 후 **최소 20분 관찰**하고 `worker.err.log`의 태스크별 성공/실패를 §1 표와
   같은 형식으로 재집계해 보고. `another operation is in progress`가 재시작 시각 이후로
   0건이어야 한다
   — 태스크가 안 떠서 실패가 0인 것과 구별할 것: 성공 건수가 실제로 증가해야 한다
     ([[feedback_zero_results_mean_broken_not_absent]])

## 8. 범위 밖

- `scripts/refresh_sale_timing.py:125` — 같은 엔진을 쓰지만 일회성 스크립트라 단일
  `asyncio.run()`이다. NullPool로 자동 해소되며 별도 수정 불요
- `alembic/env.py` — 별도 동기 엔진, 무관
- 수집 스코프 P0 — `design-daily-collect-brand-sweep-2026-08-07.md` 담당. 이 문서가
  먼저 랜딩된 뒤 진행
