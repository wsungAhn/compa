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

**배제한 경합 가설 (2026-08-08 감사 r1 — 부정 결과 기록)**: `another operation is in
progress`는 *같은 asyncpg 커넥션을 두 코루틴이 동시에 쓸 때*도 난다. 즉 공유
`AsyncSession`을 `asyncio.gather`로 태우는 코드가 있으면 NullPool은 그 경로를 못 고친다.
실물로 확인했다: `collect_on_demand`(`collector.py:363`)와 `collect_fast`(`:324`)가
`gather`로 팬아웃하지만, 팬아웃 대상 `_collect_platform`(`:257`)은 **자기 세션을 새로
연다**(`async with AsyncSessionLocal() as db`). 외부에서 받은 `db`는 gather 구간에서
사용되지 않는다. **공유 세션 동시 사용 증거 없음** → 루프 간 커넥션 재사용이 §1 실패의
원인이라는 귀속이 유지된다.

### 3.1 같은 계열의 잠복 쌍둥이 — `_BROWSER_SEMAPHORE` (감사 r3에서 발견)

"모듈 레벨 객체가 루프에 묶인다"는 이 버그의 본질은 DB 풀에만 있는 게 아니다.
`collector.py:102`에 **모듈 레벨 `asyncio.Semaphore(4)`**가 있고 `:283`에서
`async with`로 쓰인다. Python 3.11 실측:

```
run #1 (경합 있음, n=6): ok
run #2: FAIL RuntimeError: <Semaphore [locked]> is bound to a different event loop
run #3: FAIL RuntimeError: <Semaphore [locked]> is bound to a different event loop
```

**단 경합이 있을 때만 터진다.** `Semaphore.acquire()`는 비경합 경로에서 `_get_loop()`를
부르지 않아 루프에 묶이지 않는다(비경합 3회 연속은 3/3 성공 실측). 한 번 경합하면
루프에 묶이고 `[locked]` 상태로 영구 고착된다.

**지금은 발화하지 않는다**: 실측 `_BROWSER_SCRAPERS` 6개 중 **enabled와 교집합이 1개**
→ 동시 획득이 최대 1이라 4를 넘는 경합이 발생할 수 없다.

**발화 조건 (수치)**: enabled ∩ `_BROWSER_SCRAPERS` ≥ **5**. `enabled_scrapers=all`로
바꾸거나 브라우저 스크래퍼를 늘리면 그 순간 NullPool로 못 고치는 2차 장애가 열린다.

**이 문서 범위 밖**(대상 파일이 `collector.py`이고 현재 발화 불가) — §8에 후속으로
등록하고 핸드오프에 명시한다. "DB 풀이 §1의 원인"은 유지되나 **"루프 친화 전역 객체가
DB 풀뿐"이라는 뜻은 아니다.**

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

**더 큰 대가 — 커넥션 상한이 사라진다 (2026-08-08 감사 r1에서 누락 지적, 실측 후 반영)**:
지연시간만 보면 안 된다. `QueuePool`은 *프로세스당 동시 체크아웃 상한*(기본
`pool_size=5 + max_overflow=10 = 15`)을 갖지만 **`NullPool`에는 상한이 없다.** 동시성이
곧 PG 커넥션 수가 된다. 실측:

| 항목 | 실측값 | 근거 |
|---|---:|---|
| `gather` 팬아웃 폭 | **29** + 호출자 outer 세션 1 = **30** | `get_enabled_scrapers()` 29, `SKIP_SCRAPERS` 0 (`collector.py:363`). 호출자가 이미 세션을 열고 있다(`collector.py:333`) — 감사 r3 지적 반영해 보수적으로 30으로 센다 |
| Celery worker 동시성 | **2** | `ops/com.compa.worker.plist:13` `--concurrency=2` |
| API 프로세스 | **1** | `com.compa.api.plist` — uvicorn `--workers` 미지정 |
| PG `max_connections` | **100** | 라이브 측정 |
| `superuser_reserved_connections` | **3** | → 실사용 가능 **97** |
| 현재 평시 사용 | 8 (compa 3) | 라이브 측정 |

**변경 전 상한**: 15 × 3 프로세스 = 45.
**변경 후 최악**: worker 2 × 29 = **58** (동시성이 2라 이보다 커질 수 없다 — 가장 넓은
팬아웃이 29이므로 다른 beat 태스크가 겹쳐도 상한은 그대로다).
58 < 97이므로 **worker만 보면 헤드룸이 있다.** 단 현행 QueuePool이 29폭 팬아웃을 15개씩
파도로 끊어 처리하던 것이 NullPool에선 29개가 동시에 열린다 — 실병렬성이 올라가는
부수효과이자 이 항목의 위험이다.

### 5.1 API 프로세스도 29폭으로 연다 (감사 r2에서 발견 — r1 계산 누락)

r1의 "API는 요청당 세션 1개(+5.5ms)"는 **틀렸다.** 실측으로 정정한다:

| API 경로 | 세션 폭 | 근거 |
|---|---:|---|
| 일반 조회 (`get_db`) | 1 | 요청당 1세션 — r1 서술 유효 |
| `collect_fast` 인라인 (`products.py:163`) | **0** | `FAST_SCRAPERS`가 **빈 집합**(`collector.py:87`) → `stale` 비어 즉시 `return []`. 팬아웃 없음 |
| **백그라운드 수집** (`products.py:174` → `_collect_in_background` → `collect_on_demand`) | **29** | `background_tasks.add_task`로 응답 후 API 프로세스 안에서 실행. `collector.py:363` 팬아웃 29 |

**단 이 29폭 경로는 정상 운영 경로가 아니다 (감사 r3에서 정정 — r2의 내 계산이 과장)**:
`products.py:174`는 **`except Exception:` 블록 안**에 있다. 정상 경로는 Celery
`run_collection_slow.delay(q)`로 나가고(`:167`), 백그라운드 팬아웃은 **Celery 디스패치가
실패했을 때만**(Redis 불통 등) 쓰이는 폴백이다.

그리고 이 조건은 worker 부하와 **동시에 성립할 수 없다**: Celery 디스패치가 실패하는
상황이면 worker도 태스크를 받지 못하므로 worker 쪽 58은 존재하지 않는다. r2가 쓴
"58 + 58 = 116"은 **양립 불가능한 두 상태를 더한 값**이었다. 철회한다.

**정정된 최악 계산**:

| 상태 | worker | API | 합계 |
|---|---:|---:|---:|
| 정상 운영 | 2 × 30 = **60** | 요청당 1 (`get_db`) + `collect_fast` 0 → 소수 | **~65** |
| Celery 불통(폴백) | **0** (태스크 미수신) | 서로 다른 쿼리 N건 × 30 | 30N |

정상 운영 ~65 < 97. 폴백 상태는 N ≥ 3이면 90으로 97에 근접하나 worker가 0이다.
**따라서 API를 NullPool로 올려도 재부팅 안전성이 깨지지 않는다** — r2가 세운 "API 재시작
게이트"는 잘못된 산식 위에 있었으므로 **철회한다.**

**부채 트리거 (수치로 고정)**: ① worker `--concurrency`를 3 이상
② `SCRAPERS` 레지스트리 40개 초과 ③ uvicorn `--workers` 도입
④ `FAST_SCRAPERS`가 비어있지 않게 되어 인라인 팬아웃이 살아나는 경우.
**그때가 Celery 전용 엔진 분리 시점이다.**

**검토했으나 채택하지 않은 대안**:

| 대안 | 왜 안 했나 |
|---|---|
| 프로세스 role/env로 `poolclass`만 분기 (`AsyncSessionLocal` 이름 유지) | **감사 r2 제안 — 이번 레이어에선 기각, 단 §5.1 게이트의 지정 해법으로 승격.** 기각 사유: ① 역할 판별에 `com.compa.worker.plist`에 env를 심어야 하는데 **프로덕션 설정 파일 수정은 이 세션 금지 범위** ② env가 안 실린 채 배포되면 워커가 조용히 QueuePool로 돌아가 이 P0가 **무증상 재발**한다(아래 `dispose()` 행과 같은 실패 양식) ③ 관찰 창 안에서는 73 < 97로 사는 것이 없다. **API 재시작 시점에 이 안을 채택한다** |
| Celery 전용 엔진 분리 (API는 풀 유지) | **감사 r1 재검토 후에도 기각.** "분기를 `database.py` 안에 가두면 된다"는 반론은 절반만 맞다 — `CelerySessionLocal`을 만들어도 **11개 `asyncio.run()` 호출지점이 각자 옳은 sessionmaker를 골라야** 하고(§2), 새 태스크가 `AsyncSessionLocal`을 그냥 쓰면 이 P0가 조용히 재발한다. 아래 `dispose()` 행과 같은 실패 양식이다. 게다가 위 실측대로 58 < 97로 헤드룸이 확인됐으므로 지금 분리해서 사는 것이 없다. 트리거(①②③) 도달 시 재검토 |
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

**T1 어서션 강도 (감사 r1 반영)**: `SELECT 1`은 체크아웃만 검증하고 ORM 트랜잭션 경로를
안 본다. 실패한 프로덕션 경로와 같아지도록 **`AsyncSessionLocal` + ORM 쿼리
(`select(Product).limit(1)`) + `commit()`**까지 한 회차에 포함한다.

**T1의 DB 의존성 — 스킵이 은폐가 되지 않게 (감사 r1 반영, r2에서 정정)**: T1은 실제
PG가 필요하고 `.github/workflows/ci.yml`에는 **postgres 서비스가 없다.**

r1은 여기서 "그러니 CI에선 T1만 스킵된다"고 썼는데 **전제가 틀렸다.** r2 실측:

| 파일 | live PG 사용 | skip 가드 |
|---|---|---:|
| `tests/tasks/test_sale_windows.py` | `AsyncSessionLocal, engine` 직접 import | **0** |
| `tests/tasks/test_match_products.py` | `AsyncSessionLocal` | **0** |
| `tests/api/test_feedback.py` | `AsyncSessionLocal` | **0** |
| `tests/api/test_admin.py` | `AsyncSessionLocal` | **0** |
| `tests/tasks/test_reddit_retention.py` | `AsyncSessionLocal` | 1 |

**즉 이 스위트는 이미 live PG 없이는 통과할 수 없고, CI backend 잡은 현재 녹색일 수
없다.** 이는 이 설계 이전부터 있던 레포 상태이며 **범위 밖**이다(§8). 다만 "베이스라인
484 passed"가 **로컬(PG 있음) 수치**라는 점은 명시해 둔다.

따라서 T1의 방침:

- 스킵 조건은 `pytest.mark.skipif`로 두되 **스킵 사유 문자열에 "requires live PG"를 명시**
- **판정 술어는 collection time에 안전한 동기 함수여야 한다**(감사 r2). async 엔진을
  `skipif` 안에서 만들면 import 시점 부작용이 생긴다. 판정 헬퍼는 테스트 파일 안에
  둔다(새 모듈 만들지 않는다).
- **포트 열림 확인만으로는 부족하다**(감사 r3). 소켓 연결은 credential·스키마·
  마이그레이션 상태를 보지 않아, **DB 준비 문제로 인한 실패가 설계 변경의 실패로
  오인된다.** T1이 `select(Product).limit(1) + commit()`까지 하므로 판정도 **"그 쿼리가
  실제로 되는가"**여야 한다 — 모듈 로드 시 `asyncio.run()`으로 동일 쿼리를 1회 시도해
  성공한 경우에만 실행하고, 실패 사유(`OperationalError` 메시지 등)를 스킵 메시지에 담는다
- **구현 완료 판정은 로컬 DB에서 T1이 실제로 `passed`한 것을 근거로만 한다.**
  스킵 결과를 통과로 보고하지 않는다 ([[feedback_zero_results_mean_broken_not_absent]])

베이스라인: 484 passed, 1 skipped (2026-08-07 워크트리 실측).

## 7. 검증 절차 (Verification Before Done)

**모든 명령의 cwd는 워크트리의 `backend/`다** (감사 r1: 문서가 `app/...`·`tests/...`로
적어 레포 루트로 오해될 수 있었다. 실제 경로는 `backend/app/core/database.py`,
`backend/tests/core/test_database_event_loop.py`). venv는 워크트리에 없으므로 main의
것을 쓴다 — `/Users/Mung/dev/compa/backend/.venv/bin/python`.

```bash
cd /Users/Mung/dev/compa/.worktrees/collect-daily-scope/backend
VENV=/Users/Mung/dev/compa/backend/.venv/bin/python
```

1. `PYTHONPATH=. $VENV -m pytest tests/ -q` → 484+ passed
2. `PYTHONPATH=. $VENV -m mypy --strict app/` → clean
3. 재현 스크립트 재실행 → `asyncio.run()` 6연속 전부 성공
4. **worker/beat 재시작** (사용자 승인됨, 2026-08-08) —
   `launchctl kickstart -k gui/$(id -u)/com.compa.worker` / `.beat`
   **API는 재시작하지 않는다.** 이 변경은 전역(`database.py`)이라 API에도 적용되지만,
   재시작 전까지 API 프로세스는 구코드(QueuePool)를 물고 돈다 — 따라서 §5의 API
   latency(+5.5ms)·커넥션 영향은 **이번 관찰 창에서 검증되지 않는다**(감사 r2 지적).
   이는 의도된 것이다: §5.1 게이트가 해소되기 전에는 API를 NullPool로 올리면 안 된다.
   파일만 고치면 떠 있는 프로세스는 구코드를 계속 돌린다는 점을 역이용한 셈이나,
   **머신 재부팅이 이 가정을 깬다** — §5.1 게이트 참조
5. 재시작 후 **최소 20분 관찰**하고 `worker.err.log`의 태스크별 성공/실패를 §1 표와
   같은 형식으로 재집계해 보고. `another operation is in progress`가 재시작 시각 이후로
   0건이어야 한다

   **관찰 창에 무엇이 실제로 뜨는가 (감사 r3 지적 — beat 주기 실측)**: 20분 창은
   태스크를 전부 못 본다. `beat_schedule`(`tasks/__init__.py:24`, Asia/Seoul) 기준:

   | 태스크 | 주기 | 20분 창 | 60분 창 |
   |---|---|:-:|:-:|
   | `collect_reddit_signals` | 매시 :05 | 조건부 | ✅ |
   | `classify_pending` | 매시 :15 | 조건부 | ✅ |
   | `collect_slickdeals_signals` | 매시 :25, :55 | 조건부 | ✅ |
   | `extract_social_posts` | 매시 :45 | 조건부 | ✅ |
   | `purge_expired_social_posts` | 매시 :50 | 조건부 | ✅ |
   | `collect_social_for_products` | 6h (:30) | ❌ | 조건부 |
   | `match_pending_products` | 6h (:40) | ❌ | 조건부 |
   | `collect_all_products` | 일 1회 03:00 KST | ❌ | ❌ |

   위 **매시 5종이 §1 실패 259건 중 242건(93%)**을 차지한다. 따라서 판정은
   **최소 1시간(정시 경계 1회 포함)** 관찰로 이 5종 전부를 확인하는 것을 기준으로 한다.
   6h·일간 태스크가 창에 안 들어오면 **"안 돌았다"가 아니라 "관찰 창 밖"**으로 쓰고
   다음 예정 시각을 명시한다 ([[feedback_zero_results_mean_broken_not_absent]])
   — 태스크가 안 떠서 실패가 0인 것과 구별할 것: 성공 건수가 실제로 증가해야 한다
     ([[feedback_zero_results_mean_broken_not_absent]])

### 7.1 롤백 기준 (감사 r1 지적 반영)

한 줄 변경이지만 운영 재시작을 동반하므로 되돌릴 조건과 방법을 미리 고정한다.

**같이 볼 지표** (§5의 커넥션 상한 제거가 실제로 문제가 되는지):

`count(*)` 1회는 순간값이라 피크를 못 잡는다(감사 r2). 관찰 창 20분 동안 **주기
샘플링해 최댓값**을 남긴다:

```bash
# 20분간 5초 간격으로 compa 커넥션 수를 샘플링 → 최댓값 기록
for i in $(seq 1 240); do
  psql -U compa -d compa -tAc \
    "select count(*) from pg_stat_activity where datname='compa'"
  sleep 5
done | sort -n | tail -1   # ← 이 값이 피크
grep -c "too many connections\|remaining connection slots" \
  /Users/Mung/dev/compa/ops/logs/*.err.log
```

**로그 집계는 반드시 재시작 시점 이후로 한정한다 (감사 r3)**. 기존 로그에 이미
`another operation is in progress`가 1,000건 있으므로 전체 grep은 **즉시 오탐**이다.
kickstart **직전에 바이트 오프셋을 저장**하고 그 이후만 센다:

```bash
LOG=/Users/Mung/dev/compa/ops/logs/worker.err.log
OFFSET=$(wc -c < "$LOG")          # ← kickstart 직전에 실행
# ... kickstart + 관찰 ...
tail -c +$((OFFSET+1)) "$LOG" | grep -c "another operation is in progress"
```

**즉시 롤백 조건 (하나라도 해당)**:
- `too many connections` 또는 `remaining connection slots` 로그 1건 이상
- compa 커넥션 피크가 **80 이상** (97 대비 안전마진 소진)
- API `p95` 체감 악화 — `api.err.log`에 타임아웃 신규 발생

**롤백 방법**: 이 커밋 1개를 revert(변경이 `poolclass=NullPool` 한 줄이라 부분 롤백
불요) 후 worker/beat/api kickstart. 백업 사본은 만들지 않는다 — git이 백업이다.

## 8. 범위 밖

- `scripts/refresh_sale_timing.py:125` — 같은 엔진을 쓰지만 일회성 스크립트라 단일
  `asyncio.run()`이다. NullPool로 자동 해소되며 별도 수정 불요
- `alembic/env.py` — 별도 동기 엔진, 무관
- 수집 스코프 P0 — `design-daily-collect-brand-sweep-2026-08-07.md` 담당. 이 문서가
  먼저 랜딩된 뒤 진행
- **CI에 postgres 서비스 추가** — §6 표대로 live PG 의존 테스트 4개가 skip 가드 없이
  존재해 CI backend 잡이 이미 녹색일 수 없다. 이 설계 이전부터의 상태이며 CI 워크플로
  변경은 별건이다. 핸드오프에 후속으로 남긴다
- **`_BROWSER_SEMAPHORE` 루프 고착** — §3.1. 같은 계열의 잠복 버그이나 대상 파일이
  `collector.py`이고 현재 발화 불가(enabled ∩ browser = 1 < 5)라 이 레이어에서 제외.
  `enabled_scrapers=all` 전환 전에 반드시 선행할 것. 핸드오프에 후속으로 등록
