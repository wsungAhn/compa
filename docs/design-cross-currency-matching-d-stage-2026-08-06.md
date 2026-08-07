# 설계 — 크로스 통화 매칭 D단계 (배치 매칭 + 검토 UI, 2026-08-06)

> B단계(`app/ai/matching.py` — 순수 매칭 코어)·C단계(`app/ai/translator.py` — 번역 계층)는
> 랜딩 완료(`38b44f9`, `29cbc9d`). 이 문서는 그 둘을 조립해 실제로 product_id를 합치는
> 마지막 단계를 설계한다.

## 선행조사

### ① 레포 내 검색 (Explore 서브에이전트, 2026-08-06)

| 확인한 것 | 상태 |
|---|---|
| `SaleEvent`(`app/models/sale_event.py`) | `product_id`(FK)·`needs_review`(bool)·`size_ml`(Float)·`currency`·`confidence` **전부 이미 있다** — 새 컬럼 불필요 |
| `Product`(`app/models/product.py`) | `name_kr/en/jp/cn`·`brand`·`category`·`deleted_at`. 국가별 매칭 후보를 담는 별도 테이블 없음 |
| `app/api/admin.py` | **존재하지 않는다.** `docs/plan-cross-currency-matching-2026-08-06.md:120-121`이 "이미 있는 `require_admin` 게이트를 재사용한다"고 전제하는데 **사실이 아니다** — 과거에 있었다가 삭제된 흔적(`.pyc`만 잔존)만 있다. 실제 정본 패턴은 `app/api/feedback.py:17-24`의 `_is_authorized_feedback_secret`(HMAC 헤더 시크릿) — 이 문서는 그걸 재사용한다. **plan.md D절의 이 전제는 이 문서로 정정한다.** |
| `app/tasks/classify.py` | Celery 태스크 정본 패턴: `def f(): return asyncio.run(_f())` → `f = celery.task(f)`, `async def _f()`는 `AsyncSessionLocal()` 열고 매퍼 루프에 `try/except: continue`(개별 실패가 배치를 안 죽임), 루프 끝에 `db.commit()` 한 번 |
| `app/api/comparison.py` | `product_id` 하나를 전제로 국가별 최신가를 모아 `app/core/fx.py:convert()`로 환산 — **매칭이 끝나면 이 파일은 무수정으로 작동한다**(같은 product_id 아래 여러 통화 SaleEvent가 이미 모이므로) |
| `app/tasks/__init__.py` | `include=[...]` 리스트에 새 태스크 모듈 등록 + `beat_schedule`에 crontab 추가하는 패턴 |
| `alembic` head | `d1e2f3a4b5c6` — 새 마이그레이션은 여기서 이어진다 |

### ② 외부 선행작업
없음 — 이 저장소 내부(B/C단계 산출물 + 기존 admin 패턴)를 조립하는 작업이라 외부
조사 대상이 아니다.

### ③ 결론
새로 만들 것: 매칭 후보를 보관할 작은 테이블 하나(검토 큐 자체가 이걸 필요로 한다 —
"애매함"을 어딘가에 적어둬야 검토 UI가 보여줄 게 있다), Celery 태스크 하나,
`admin.py`(신규, `feedback.py` 패턴 재사용). `comparison.py`는 건드리지 않는다.

---

## 적대감사 R1 반영 (`docs/audit-2026-08-06-d-stage-r1.md`, GLM 독립감사)

> 이 감사자의 특성(이 세션 R1·R2에서 반복 확인): 시나리오의 산수는 종종 틀리지만
> 손가락이 가리키는 지점은 대체로 맞다. "제안"이 아니라 "어디를 봤는지"를 읽고
> 직접 검증했다.

**[수용] 후보 INSERT 경쟁 처리 없음** — 지적한 "worker B가 결과를 영구히 가림"이라는
결론은 틀렸다(유니크 제약 위반은 그 orphan을 못 갖는 것뿐, 다른 worker의 성공한
행을 지우지 않는다). 하지만 **`IntegrityError`를 명시적으로 처리 안 하면 배치
전체가 죽는다**는 진짜 갭은 있다. `matcher.py:325-332`의 `get_or_create_product`가
이미 같은 패턴(`try: flush / except IntegrityError: rollback + 재조회`)을 쓴다 —
새로 발명하지 않고 그대로 재사용. Task 아래 반영.

**[부분수용] `_merge_products` 트랜잭션** — 지적한 시나리오(orphan X→Y, orphan Z→Y가
동시에 `SaleEvent.product_id`를 건드림)는 실제로 안전하다(서로 다른 orphan의
`SaleEvent`는 겹치지 않는 집합이라 UPDATE 대상이 안 겹친다 — 감사자가 놓친 부분).
다만 **같은 canonical 행에 `name_jp`/`name_kr` 등을 backfill하는 부분**은 두 orphan이
동시에 같은 canonical을 대상으로 하면 lost-update가 날 수 있다(값이 틀려지진 않고
그냥 나중 커밋이 이기는 정도라 데이터 손상은 아니다) — 비용이 거의 없으므로
`SELECT ... FOR UPDATE`로 canonical 행에 락을 걸어 아예 막는다.

**[반려] 고아 선별 쿼리 누락 케이스** — 감사자가 필터 의도를 오해했다. `name_kr`/
`name_cn`이 NULL인 걸 "놓친 케이스"라고 지적했는데, 이 쿼리는 **JP 오브만** 고르려는
의도(문서에 이미 명시: "이번 라운드는 JP만")라 name_kr/name_cn 상태는 애초에
무관하다. 범위를 넓히자는 제안일 뿐 실제 결함이 아니다.

**[수용] 최고점 후보 선택 시 tie-break 없음** — 제시한 구체적 시나리오(동점인데
DB 조회 순서로 needs_review가 이김)는 희박하지만, **더 실질적인 문제**를 검증 중에
발견했다: 동점이 아니어도 `match` verdict 후보보다 점수가 살짝 높은 `needs_review`
후보가 있으면 그게 뽑히고, `needs_review`는 자동병합을 안 하니 정작 좋은 `match`
후보는 이번 배치에서 **후보 행 자체가 안 생겨** 완전히 누락된다(다음 배치가 다시
스캔하니 영구 손실은 아니지만 불필요한 지연). **해법**: 정렬 키를 점수 단독이 아니라
`(verdict 우선순위: match > needs_review, containment_score)`로 바꾼다 — match를
우선한다.

**[수용] admin 승인/거부의 TOCTOU 갭** — SELECT로 상태 확인 후 UPDATE하는 방식은
그 사이에 경쟁이 끼어들 창이 있다. **해법**: `UPDATE ... WHERE status='pending'`을
원자적으로 실행하고 영향받은 행 수(0이면 409)로 판정 — 표준 패턴, 새 인프라 불필요.

**[수용, 사소] `NOT IN` 서브쿼리** — `LEFT JOIN ... WHERE pmc.id IS NULL`이 일반적으로
더 안전하다(플래너 최적화 이슈 회피). 카탈로그 규모상(2,541건) 실측 성능차는 미미하지만
비용이 0이므로 그냥 바꾼다.

**[반려, 이번 라운드는] B/C단계 연동 재검토·통화변환 재확인** — 감사자가 지적한
매개변수 불일치는 실제로 없었다(직접 시그니처 대조 완료, 통화변환은 이미 §4-c에
명시돼 있었음). 구체적 결함 없이 "더 명확히 하라"는 수준이라 반려.

**[반려, YAGNI] 실패유형 분류·모니터링/알림** — 개인 프로젝트 v1 배치 태스크에
과설계. 실패 시 로그 남기는 것으로 충분(기존 `classify.py` 관례와 동일 수준).
필요해지면(`needs_review` 큐가 실제로 정체되면) 그때 추가 — plan.md의 "실패하면
어떻게 아나" 절이 이미 "큐가 길어지는 것 자체가 신호"라고 못박아뒀다.

**Critical 3건 중 실제로 살아남은 건**: 없음(전부 반려 또는 High/Medium으로 재분류).
감사자의 "Critical" 라벨은 시나리오 자체가 틀렸을 때도 과장되는 경향이 있다(이 세션
R1·R2와 같은 패턴) — 라벨보다 "무엇을 지적했는가"를 봐야 한다는 교훈이 다시 확인됨.

---

## 문제: 지금 무슨 일이 일어나고 있나

`matcher.py:find_matching_product`(68~106번 줄)는 `brand`가 주어지고 후보가 정확히
하나면 `_same_product_evidence`로 토큰 겹침을 확인하는데, JP 리스팅 원문과 US
정본(`name_en`)은 스크립트가 달라 토큰이 절대 안 겹친다. 증거 부족으로 매칭이
실패하면 **새 Product 행이 생긴다**(`name_jp`만 채워지고 `name_en`은 비어 있음).
이게 지금 SK-II 같은 브랜드에 "US용 정본 행 여러 개 + JP 리스팅용 고아 행 여러 개"가
공존하는 이유다. **D단계는 이 고아 행들을 정본에 합친다.**

---

## 스키마: `product_match_candidates` (신규 테이블)

```python
class ProductMatchCandidate(Base):
    __tablename__ = "product_match_candidates"
    __table_args__ = (
        UniqueConstraint("orphan_product_id", name="uq_product_match_candidate_orphan"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    orphan_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    canonical_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Enum("pending", "approved", "rejected", name="match_candidate_status"), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(50))  # "auto" 또는 admin 식별자
```

`orphan_product_id`에 유니크 제약을 건다 — **오브 이미 후보 행이 있으면 재스캔하지
않는다**(status 무관). 이게 자연스러운 재시도 억제다: 거부된 쌍이 매 배치마다 다시
제안되는 걸 막고, 승인된 쌍은 이미 합쳐졌으니 orphan 자체가 소프트삭제돼 다음 쿼리에
안 걸린다. **거부된 쌍을 재검토하는 UI는 범위 밖**(필요해지면 그 행을 지우거나 상태를
리셋하면 된다 — 지금 만들지 않는다, YAGNI).

Alembic: `down_revision = "d1e2f3a4b5c6"`.

---

## Celery 태스크: `app/tasks/match_products.py` (신규)

`classify.py`와 동일한 골격(`match_pending_products(limit=50)` sync 진입점 →
`asyncio.run` → `AsyncSessionLocal`).

### 고아 행 선별
```sql
SELECT p.* FROM products p
LEFT JOIN product_match_candidates pmc ON p.id = pmc.orphan_product_id
WHERE p.name_en IS NULL AND p.name_jp IS NOT NULL AND p.deleted_at IS NULL
  AND p.brand IS NOT NULL AND pmc.id IS NULL
LIMIT :limit
```
(`NOT IN` 서브쿼리 대신 `LEFT JOIN` — 적대감사 R1 수용, 플래너 최적화 이슈 회피)
**이번 라운드는 JP만**(`name_jp` 채움 기준) — 원설계(`design-cross-currency-matching-
2026-08-05.md` "범위 밖")가 KR/CN을 다음 레이어로 미뤄뒀고, C단계의 라이브 실측도
JP만 검증했다. `brand IS NULL`인 고아는 건너뛴다(안전하게 후보를 좁힐 방법이 없다 —
전체 카탈로그 스캔은 비용·오매칭 위험 둘 다 크다).

### 매칭 알고리즘 (고아 1건당)

1. `translated = translate_for_matching(orphan.name_jp, "ja")` — `None`이면 **건너뛴다**
   (후보 행을 안 만듦 → 다음 배치에서 자연 재시도. 번역 서버 일시 다운 등 일과성
   실패를 영구 거부로 취급하지 않기 위함).
2. 같은 브랜드(대소문자 무시)의 정본 후보들을 가져온다: `Product.brand == orphan.brand`
   AND `name_en IS NOT NULL` AND `deleted_at IS NULL`.
3. 고아의 대표 용량: 고아에 달린 `SaleEvent` 중 `size_ml IS NOT NULL`인 가장 최신 것
   하나(`ORDER BY created_at DESC LIMIT 1`). 없으면 `None`.
4. 각 후보에 대해:
   a. 후보에 달린 `SaleEvent.size_ml` distinct 값들을 가져온다(용량별로 다른 이벤트가
      같은 product_id에 쌓이는 게 A단계 설계다).
   b. 고아 대표 용량과 `sizes_match()`가 되는 후보 용량이 하나라도 있으면 그 값을
      `matched_size`로 쓴다. 둘 다 `None`이면(고아·후보 다 용량 미상) 사이즈 게이트를
      건너뛴다(A단계 `sizes_match`의 "모르면 거부하지 않는다" 철학과 동일). 후보 용량이
      있는데 하나도 안 맞으면 **이 후보는 탈락**(다음 후보로).
   c. 단가: 고아의 최신 SaleEvent 가격/용량, 후보의 `matched_size`에 해당하는 SaleEvent
      가격/용량(둘 다 있을 때만 계산, 통화가 다르면 `app/core/fx.py:convert`로 고아
      통화를 후보 통화로 맞춘 뒤 나눈다).
   d. `verdict = evaluate_match(candidate.name_en, translated, canonical_size_ml=matched_size,
      listing_size_ml=orphan_size, canonical_unit_price=..., listing_unit_price=...)`
   e. `verdict == "reject"`면 이 후보는 버린다.
5. 남은 후보 중(`match` 또는 `needs_review`) 하나를 고른다 — 정렬 키는
   **`(verdict 우선순위, containment_score)`**, verdict 우선순위는 `match` > `needs_review`
   (적대감사 R1 수용: 점수 단독 정렬이면 점수가 살짝 높은 `needs_review`가 더 좋은
   `match` 후보를 밀어내 이번 배치에서 그 `match` 후보의 행 자체가 안 생긴다 — 다음
   배치가 다시 스캔하니 영구 손실은 아니지만 불필요한 지연이다). 동률이면 먼저
   조회된 것 — 그 이상의 타이브레이크는 범위 밖(YAGNI, 실측상 SK-II 8개 정본이
   제품 종류가 달라 애초에 여러 개가 동시에 높은 점수를 받을 가능성이 낮다).
6. 최종 처리 — **`product_match_candidates` INSERT는 `IntegrityError`를 잡는다**
   (적대감사 R1 수용: 동시 실행되는 다른 worker가 같은 orphan을 먼저 처리했을 수
   있다. `matcher.py:325-332`의 `get_or_create_product`와 같은 패턴 —
   `try: db.add(row); await db.flush() / except IntegrityError: await db.rollback();
   continue`, 새 패턴 발명 안 함):
   - 후보가 없으면 아무것도 안 한다(행도 안 만듦 — 다음 배치가 다시 스캔).
   - 최고 후보의 verdict가 `"match"`면 → **즉시 병합**(`_merge_products`, 아래) +
     `product_match_candidates` 행을 `status="approved", decided_by="auto"`로 기록
     (증거 보존 — "정보를 버리지 말고 증거로 쌓아라").
   - `"needs_review"`면 → 병합하지 않고 `status="pending"` 행만 생성.

### 병합 `_merge_products(db, orphan, canonical) -> None`
이 태스크 모듈이 정의하고, `admin.py`의 승인 엔드포인트도 이걸 import해서 재사용한다
(병합 로직을 두 곳에 복제하지 않는다). **호출부가 `canonical`을 `SELECT ... FOR
UPDATE`로 잠근 뒤에 넘긴다**(적대감사 R1 수용 — 두 orphan이 동시에 같은 canonical의
`name_jp` 등을 backfill하면 lost-update가 날 수 있다. 데이터가 틀려지진 않지만
막는 비용이 거의 없다):
```python
async def _merge_products(db: AsyncSession, orphan: Product, canonical: Product) -> None:
    if orphan.name_jp and not canonical.name_jp:
        canonical.name_jp = orphan.name_jp
    if orphan.name_kr and not canonical.name_kr:
        canonical.name_kr = orphan.name_kr
    if orphan.name_cn and not canonical.name_cn:
        canonical.name_cn = orphan.name_cn
    await db.execute(
        update(SaleEvent).where(SaleEvent.product_id == orphan.id).values(product_id=canonical.id)
    )
    orphan.deleted_at = func.now()
```
`deleted_at`만 찍고 행은 지우지 않는다(Delete, Don't Deprecate와 무관 — 이건 데이터
행이지 코드 경로가 아니라 소프트삭제가 맞다, 복구 가능성을 열어둔다).

### Beat 등록
`app/tasks/__init__.py`의 `include`에 `"app.tasks.match_products"` 추가,
`beat_schedule`에 `"match-products-6h": {"task": "app.tasks.match_products.
match_pending_products", "schedule": crontab(minute=40, hour="*/6")}` — 실시간일 이유
없음(설계 확정 사항, plan.md §C "실행 시점: 배치"). 수집 주기(일간)보다 충분히
자주면 되므로 6시간(사용자 확정, 2026-08-06).

---

## `app/api/admin.py` (신규 파일)

`feedback.py`의 `_is_authorized_feedback_secret` 패턴을 그대로 재사용(새 인증 로직
발명 안 함).

- `GET /api/admin/product-matches?status=pending` — 후보 목록(양쪽 product의
  name_en/name_jp/brand/score를 조인해서 반환 — 검토자가 이름을 보고 판단해야 하므로)
- `POST /api/admin/product-matches/{id}/approve` — `_merge_products` 호출 +
  `status="approved", decided_at=now(), decided_by="admin"`
- `POST /api/admin/product-matches/{id}/reject` — `status="rejected", decided_at=now(),
  decided_by="admin"` (병합 없음)
- **원자적 상태 전이**(적대감사 R1 수용 — SELECT로 확인 후 UPDATE하면 그 사이에
  경쟁이 낄 창이 생긴다): `UPDATE product_match_candidates SET status=..., decided_at=now(),
  decided_by=... WHERE id=:id AND status='pending'`를 먼저 실행하고 **영향받은 행 수가
  0이면 409**(이미 처리됨). SELECT-then-UPDATE 대신 이 원자적 UPDATE 하나로 이미
  `approved`/`rejected`인 행 재호출을 막는다.

`main.py`에 `admin_router` 등록.

**프론트엔드 검토 UI는 범위 밖**(사용자 확정, 2026-08-06 — API까지만, 화면은 항목이
실제로 쌓이는 걸 보고 나서 별도 라운드로 붙인다. Working Skeleton First).

---

## 완료 판정

라쿠텐 JP 고아 상품이 실제로 US 정본에 병합되고(`SaleEvent.product_id` 재할당 확인),
`GET /api/products/{canonical_id}/comparison?currency=KRW`가 JPY·USD 두 통화의 가격을
한 응답에서 계산한다(코드 무수정 — comparison.py가 이미 이걸 한다). `product_match_
candidates`에 최소 1건 이상 자동 승인 또는 대기 행이 실측으로 생긴다.

## 실패하면 어떻게 아나
- 고아가 하나도 안 잡히면(`name_en IS NULL AND name_jp IS NOT NULL`인 행이 0건) →
  스크래핑 자체가 브랜드를 못 채우고 있는 것(이 필터 조건부터 재점검)
- 병합됐는데 `comparison.py` 응답에 두 통화가 안 뜨면 → `SaleEvent.product_id` 재할당이
  실제로 커밋됐는지 직접 쿼리로 확인(트랜잭션 롤백 의심)

## 범위 밖
- 한국·중국 리스팅(브랜드 사전은 이미 넓지만, C단계 라이브 검증은 JP만 함)
- 거부된 후보 재검토
- 프론트엔드 검토 화면(API까지만)
- 동점 후보 타이브레이크 고도화

