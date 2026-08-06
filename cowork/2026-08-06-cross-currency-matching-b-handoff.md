# GLM Handoff — 2026-08-06 — 크로스 통화 매칭 B단계 (매칭 코어)

> **상태(Status):** `완료 / done`
> _(Executor: set `진행중 / in-progress` on start, `검토대기 / review-pending` when done.
>  Only the author/reviewer sets `완료 / done`, after the commit.)_
>
> **시작 기록(Started by):** `session=hermes-glm-oneshot machine=mac-studio started=2026-08-06T12:56:43-07:00`
>
> **작성자(Author):** Claude (Mac Studio, orchestrator) → **수행자(Executor):** GLM
> (`glm-4.5-flash` via `hermes -z`, Codex 대체 — 아래 "왜 Codex가 아닌가" 참조)
> **작업명(Task):** 크로스 통화 매칭 파이프라인의 순수 함수 코어(B단계) 구현
> **설계 근거(Design basis):** `docs/design-cross-currency-matching-2026-08-05.md`(4차 실측)
> + `docs/plan-cross-currency-matching-2026-08-06.md`(적대감사 R1·R2 반영, 이 문서가
> 실행계획의 정본). **반드시 두 문서를 먼저 읽을 것** — 이 핸드오프는 요약이 아니라
> 실행 지시다. 요약이 설계문서와 다르면 설계문서가 맞다.
> **범위(Scope):** `backend/app/ai/matching.py`(신규 단일 파일) + `backend/tests/ai/test_matching.py`(신규).
> **범위 밖**: 번역(C단계), DB/Celery 배치 매칭 및 검토 UI(D단계), 브랜드 자동추출(딜 사전
> `app/scrapers/brand_dictionary.py`는 이미 있고 재사용만 — 이 파일은 건드리지 않는다),
> `app/ai/matcher.py`(기존 DB 매칭 로직, 별개 파일 — 건드리지 않는다).

---

## 0. How to use this document (Executor, read first)

당신은 이 프로젝트의 이전 대화나 컨텍스트가 전혀 없다. 아래 내용만 신뢰할 것.

- **하지 마라:** 범위 밖 리팩터 · `app/ai/matcher.py`/`app/scrapers/brand_dictionary.py`
  수정 · DB/Alembic 변경 · 커밋(작업트리만 변경, 커밋은 reviewer가 한다).
- **항상:** 각 태스크 후 테스트 실행 → 통과 확인 → 다음 태스크. 작업 기록은 §9에.
  시작·종료 시 상태줄 갱신.
- **모르면 추측하지 마라.** §9-6에 판단 보류 사항으로 남길 것.

### 왜 Codex가 아닌가
이 레포의 기본 executor는 Codex CLI다(`cowork/CONVENTIONS.md`). 하지만 2026-08-06 기준
Codex 사용량이 소진돼 08-08까지 복구 예정이 아니다(오늘 새벽 `docs/audit-2026-08-06-plan-r2.md`
예비감사에 이미 GLM을 대체 감사자로 썼다). 사용자가 이번 라운드는 GLM으로 진행하기로
확정했다. **이 문서의 요구사항 자체는 Codex 핸드오프와 동일한 엄격도**다 — 실행 주체만
다를 뿐, self-containment·rubric·review 규칙은 그대로 적용된다.

### Execution environment
- Interpreter: `backend/.venv/bin/python` (Python 3.11.8)
- Tests: `cd backend && .venv/bin/python -m pytest tests/ -q`
- **Current test baseline: `431 passed, 1 skipped`** (2026-08-06 직접 실행 확인). 이 아래로
  떨어지면 회귀 — 완료 아님.
- mypy: `cd backend && .venv/bin/python -m mypy --strict app/` — 반드시 통과.
- 상시 데몬 없음(로컬 개발 서버는 수동 기동) — 이 작업은 재시작 불필요.
- 신규 파일 2개만 만든다. 기존 파일은 읽기만(reuse) 한다.

---

## 1. Background (why this work)

COMPA는 화장품 가격을 한/미/일/중에서 수집해 "어디서 사면 싼가"를 비교하는 서비스다.
지금 라쿠텐(JPY)과 미국 공홈/Amazon(USD)이 **서로 다른 product로 저장돼** 크로스 통화
비교가 계산되지 않는다 — 서비스 핵심 가치가 비어 있다.

4차에 걸친 라이브 실측(`design-cross-currency-matching-2026-08-05.md`)으로 원인 3가지가
확인됐다:
1. **자카드 유사도는 정답 쌍도 0.25로 떨어뜨린다** — JP 리스팅은 별칭·노이즈로 토큰이
   과잉이라 분모가 부푼다. "포함도"(정본 토큰이 리스팅에 얼마나 들어있나)로 바꾸자
   정답 쌍이 1.00이 됐다.
2. **정본이 화려할수록 매칭이 어려워지는 역전**이 있다 — US 정본 `PITERA™ Facial
   Treatment Essence`처럼 상표·마케팅 토큰이 붙으면, JP 리스팅엔 그 토큰이 없어서
   포함도가 깎인다. 이런 토큰은 분모에서 빼야 한다.
3. **매칭에 성공한 쌍이 샘플/트라이얼일 수 있다** — 토큰과 용량이 정품과 같아서
   통과하지만 가격이 JP ¥1,980 vs US $99였다(원문 `お試し トライアル`). 그대로 노출하면
   거짓 "일본이 87% 싸다" 정보가 된다. 반대로 **진짜 깊은 할인(재고정리 70% off)도
   같은 가격 신호를 낸다** — 단가 이탈만으로 자동 거부하면 가장 값진 딜을 숨기게 된다
   (적대감사 R2 채택 사항). 그래서 가격 신호와 키워드 신호를 **분리해서** 다룬다.

A단계(용량 ml 정규화, `app/core/size.py`)는 이미 끝났다 — `parse_size_ml`/`sizes_match`를
그대로 재사용한다. B단계는 **DB·번역·LLM에 닿지 않는 순수 함수**로 나머지(노이즈 제거·
포함도·샘플 가드)를 구현하고, 이 셋 + A단계 용량대조를 하나의 판정 함수로 묶는다.
번역(C단계)이 없으므로 이 단계의 테스트는 **이미 같은 언어(번역 후)인 문자열**을 입력으로
가정한다 — 노이즈 제거만 예외로, 정규식 기반이라 원문 일본어에 직접 적용해 테스트한다.

---

## 2. Task 1 — 노이즈 제거 `strip_noise` (P0)

### 진단 / Diagnosis
일본 리스팅 제목에는 판촉 태그가 붙는다: `【公式】【送料無料】【ふるさと納税】正規品
並行輸入品`. 이 토큰들이 그대로 있으면 포함도 계산의 분모(리스팅 쪽 토큰)가 부풀어
점수가 왜곡된다. 실측(`backend/tests/scrapers/test_size.py:32`)에 이미 실제 문자열이
있다: `"【国内正規品】SK-II フェイシャルトリートメント エッセンス 75mL"`.

### 수정 방법 / How to fix
`backend/app/ai/matching.py`에 다음 계약의 함수를 작성한다:

```python
def strip_noise(text: str) -> str:
    """일본 리스팅 판촉 노이즈를 제거하고 공백을 정리한다.

    - 【...】로 감싼 구간은 내용과 무관하게 통째로 제거한다(임의의 판촉 문구를 다 나열할
      수 없으므로 괄호 자체를 노이즈 마커로 취급 — 실측: 国内正規品/公式/送料無料/
      ふるさと納税 등 내용이 매번 다르다).
    - 괄호 밖에 단독으로 나오는 판촉 단어(正規品, 並行輸入品, 送料無料, 公式)도 제거한다
      (실측: "【公式】【送料無料】【ふるさと納税】正規品 並行輸入品 SK-II …"처럼 마지막
      두 단어는 괄호 밖에 있다).
    - 연속 공백을 하나로 접고 앞뒤를 자른다.
    """
```

정규식으로 구현하면 충분하다(`re.sub`). 괄호 안 내용을 화이트리스트로 나열하지 말 것 —
brittle하다.

### 주의·제약 / Constraints
- 한글·영문 텍스트에는 아무 영향이 없어야 한다(해당 패턴이 없으므로 자연히 no-op이지만
  테스트로 고정할 것).
- 이 함수는 언어 판별을 하지 않는다 — 정규식이 매칭되는 곳만 지운다.

### 필수 테스트 / Required tests
`backend/tests/ai/test_matching.py`에:
1. `strip_noise("【公式】【送料無料】【ふるさと納税】正規品 並行輸入品 SK-II フェイシャルトリートメント エッセンス 75mL")`
   → `"SK-II フェイシャルトリートメント エッセンス 75mL"`
2. `strip_noise("【国内正規品】SK-II フェイシャルトリートメント エッセンス 75mL")`
   → `"SK-II フェイシャルトリートメント エッセンス 75mL"` (size.py 테스트와 같은 실측 문자열 재사용)
3. `strip_noise("Laneige Water Bank Cream 50ml")` → 변화 없음(no-op 확인)

---

## 3. Task 2 — 포함도 점수 `containment_score` (P0)

### 진단 / Diagnosis
자카드(교집합/합집합)는 실측 2차에서 정답 쌍을 0.25로 떨어뜨렸다 — JP 리스팅 쪽 토큰이
별칭·노이즈로 과잉이라 합집합(분모)이 부푼다. **"정본 토큰이 리스팅에 얼마나
포함되는가"**로 바꾸면 같은 쌍이 1.00이 된다.

추가로, 정본(US) 이름 자체가 상표·마케팅 토큰을 포함하는 경우가 있다 — 실측:
`PITERA™ Facial Treatment Essence`. `PITERA`는 SK-II의 에센스 성분 브랜드명인데,
JP 리스팅에는 안 붙는 경우가 있다(SK-II라는 브랜드명만 쓰고 PITERA는 생략).
이런 토큰이 분모에 남으면 정본이 화려할수록 매칭이 어려워지는 역전이 생긴다.

### 수정 방법 / How to fix

```python
_MARKETING_STOPWORDS = {"pitera", "lxp"}
# 정본 이름에 붙는 상표·마케팅 토큰 — 실측(SK-II PITERA™, LXP)에서 나온 것만 우선 등재.
# 새 사례가 나오면 추가한다(포괄적 화이트리스트를 미리 만들지 않는다 — YAGNI).

def containment_score(canonical: str, listing: str) -> float:
    """정본 이름의 토큰이 리스팅 텍스트에 얼마나 포함되는가 (0.0~1.0).

    canonical 쪽 상표·마케팅 토큰(_MARKETING_STOPWORDS)은 분모에서 뺀다 — 정본이
    화려할수록 매칭이 어려워지는 역전을 막기 위함(실측: 뺐더니 0.25 → 1.00).
    listing은 먼저 strip_noise를 거쳐 토큰화한다. canonical 토큰이 하나도 없으면 0.0.
    """
```

토큰화는 `app/ai/matcher.py:54`의 `_name_tokens`와 같은 방식(소문자화, 영/한/일 문자만
남기고 공백 분리)이면 충분하다 — **import해서 재사용하지 말고**(그쪽은 private 함수고
불용어 목록이 이 용도와 다르다 — `oz`/`ml`/`mini` 등을 걸러서 이 매칭엔 안 맞는다) 이
파일 안에 짧은 자체 토크나이저를 새로 둔다. 최소 길이(예: 2자 이상)만 두고 별도
불용어 사전은 만들지 않는다 — `_MARKETING_STOPWORDS`가 그 역할을 한다.

### 주의·제약 / Constraints
- 반환값은 `0.0`~`1.0` 사이 `float`.
- `canonical`이 빈 문자열이거나 토큰이 전부 스톱워드면 `0.0` (매칭 근거 없음 — 나눗셈 금지).
- 순서 비대칭이다: `containment_score(a, b) != containment_score(b, a)`이어도 정상이다
  (정본 쪽만 분모).

### 필수 테스트 / Required tests
1. `containment_score("PITERA™ Facial Treatment Essence", "SK-II Facial Treatment Essence 75mL")`
   ≥ `0.6` — PITERA를 빼도 나머지 토큰(facial/treatment/essence)이 다 있으므로 사실상 1.0.
2. `containment_score("The Water Cream", "La Mer The Water Cream 30mL")` ≥ `0.6` —
   **브랜드 없는 공홈명도 매칭된다**(공홈 상품명은 브랜드를 안 담는 게 정상이다).
3. 무관한 두 이름(`containment_score("Facial Treatment Essence", "Random Sunscreen SPF50")`)
   은 임계 `0.6` 미만.
4. `containment_score("", "anything")` == `0.0`.

---

## 4. Task 3 — 샘플/단가 가드 `is_sample_listing` (P0)

### 진단 / Diagnosis
매칭에 성공한 실측 쌍의 가격이 JP ¥1,980 vs US $99였다 — 원문에 `お試し トライアル`
(샘플/트라이얼)이 있었다. 토큰·용량이 정품과 같아서 그냥 두면 통과한다.

### 수정 방법 / How to fix

```python
_SAMPLE_KEYWORDS = ("お試し", "トライアル", "sample", "mini", "ミニ", "decant", "分装", "분장")

def is_sample_listing(text: str) -> bool:
    """샘플/트라이얼 표기가 있는가. 대소문자 무시(영문만), 부분 문자열 매칭."""
```

가격 이상치 판단(단가 계산·중앙값 대비 이탈)은 Task 4의 `evaluate_match`에서 다룬다 —
`is_sample_listing`은 텍스트 신호 하나만 본다.

### 필수 테스트 / Required tests
1. `is_sample_listing("【お試し】SK-II Facial Treatment Essence Trial 75mL")` → `True`
2. `is_sample_listing("SK-II Facial Treatment Essence 75mL")` → `False`
3. `is_sample_listing("Laneige mini set")` → `True` (mini)

---

## 5. Task 4 — 통합 판정 `evaluate_match` (P0)

### 진단 / Diagnosis
지금까지의 세 신호(포함도·용량대조·샘플)를 하나의 판정으로 묶어야 D단계(배치 매칭)가
바로 쓸 수 있다. 여기서 **적대감사 R2가 뒤집은 판정 하나**를 정확히 반영해야 한다:

> 단가 이탈만으로는 `needs_review`로 보낸다. 키워드(`お試し` 등)가 **함께** 걸릴 때만
> 자동 거부한다 — 진짜 깊은 할인(재고정리 70% off)이 샘플과 같은 가격 신호를 내기
> 때문에, 가격만 보고 자동 거부하면 가장 값진 딜을 우리 손으로 숨기게 된다.

**이 핸드오프가 확정하는 판정 규칙(모호하게 두지 않는다):**

| 조건 | 판정 |
|---|---|
| `containment_score < 0.6` | `"reject"` (근거 부족 — 매칭 자체가 성립 안 함) |
| 용량 있는데 `sizes_match()`가 `False` | `"reject"` (다른 용량 = 다른 상품) |
| 샘플 키워드 **있음** AND 단가 이탈 **있음** (둘 다) | `"reject"` |
| 샘플 키워드 **있음** XOR 단가 이탈 **있음** (하나만) | `"needs_review"` |
| 위 아무것도 안 걸림 | `"match"` |

이 표는 위→아래 순서로 평가한다(먼저 걸리는 조건이 이긴다) — `containment`/`size`
게이트가 하드 리젝션이고, 샘플/가격은 소프트 신호라 뒤에 온다.

"단가 이탈"의 정의: `listing_unit_price < canonical_unit_price * (1/3)`. 단가는 호출부가
이미 계산해서 넘긴다(`price / size_ml`) — 이 함수는 나눗셈을 하지 않는다. 어느 한쪽
단가가 `None`이면 "이탈 아님"으로 취급한다(정보 없음 ≠ 이상치).

```python
def evaluate_match(
    canonical_name: str,
    listing_name: str,
    *,
    canonical_size_ml: float | None = None,
    listing_size_ml: float | None = None,
    canonical_unit_price: float | None = None,
    listing_unit_price: float | None = None,
    containment_threshold: float = 0.6,
    price_deviation_ratio: float = 1 / 3,
) -> str:
    """"match" / "reject" / "needs_review" 중 하나. 위 표를 그대로 구현한다."""
```

`sizes_match`는 `app/core/size.py`에서 import해서 그대로 쓴다(재구현 금지 — A단계에서
이미 "한쪽이라도 모르면 판단하지 않는다"를 `None` 입력 시 `True`로 구현해뒀다).

### 주의·제약 / Constraints
- 반환 타입은 `str`이지만 실제로 `"match"`/`"reject"`/`"needs_review"` 셋 중 하나만
  반환한다 — 오타 방지를 위해 모듈 상단에 상수로 선언해도 좋다(`MATCH = "match"` 등).
  새 typing import(`Literal` 등)를 끌어올 필요는 없다 — 이 레포에 그 관례가 없다.
- 이 함수는 DB에 닿지 않는다. "같은 정본에 붙은 리스팅들의 ml당 단가 중앙값" 계산은
  D단계(배치) 몫이다 — 여기선 이미 계산된 두 숫자만 받는다.

### 필수 테스트 / Required tests
아래 6개는 이 작업의 **완료 판정**이다(`docs/plan-cross-currency-matching-2026-08-06.md`
"완료 판정" 절 기준) — 전부 있어야 한다:

1. **매칭**: `evaluate_match("PITERA™ Facial Treatment Essence", "SK-II Facial Treatment Essence 75mL", canonical_size_ml=73.9, listing_size_ml=75.0)` → `"match"`
2. **용량 불일치 거부**: 위와 같은 이름, `listing_size_ml=30.0` → `"reject"`
3. **노이즈 제거 후에도 매칭 유지**: `evaluate_match("PITERA™ Facial Treatment Essence", "【お得】SK-II Facial Treatment Essence 75mL", canonical_size_ml=73.9, listing_size_ml=75.0)` → `"match"` (노이즈 낀 리스팅도 `strip_noise`를 내부에서 타므로 결과가 안 바뀐다 — `evaluate_match`는 `listing_name`을 포함도 계산 전에 `strip_noise`에 통과시킬 것)
4. **샘플+단가이탈 동시 → 거부**: `evaluate_match("PITERA™ Facial Treatment Essence", "【お試し】SK-II Facial Treatment Essence Trial 75mL", canonical_size_ml=73.9, listing_size_ml=75.0, canonical_unit_price=1.34, listing_unit_price=0.20)` → `"reject"`
5. **단가이탈만 → needs_review (자동거부 아님, R2 채택 사항)**: 4번과 같은 숫자인데
   `listing_name="SK-II Facial Treatment Essence 75mL"`(샘플 키워드 없음) → `"needs_review"`
6. **브랜드 없는 공홈명도 매칭**: `evaluate_match("The Water Cream", "La Mer The Water Cream 30mL", canonical_size_ml=30.0, listing_size_ml=30.0)` → `"match"`

---

## 6. Coding principles (project rules — non-negotiable, from CLAUDE.md)

- `mypy --strict` 통과 — 모든 함수 시그니처에 타입 힌트.
- 매직넘버 금지 관례 — `0.6`, `1/3` 같은 임계값은 함수 파라미터의 기본값으로 이름 붙여
  노출한다(이미 위 시그니처에 반영됨). 모듈 최상단 헤더 docstring에 "왜 이 파일이
  존재하는가"를 한두 문장으로(다른 신규 모듈 `app/core/size.py`, `app/scrapers/
  brand_dictionary.py` 헤더 스타일 참고 — 실측 근거를 인용하는 톤).
  **WHAT을 설명하는 주석은 쓰지 않는다** — 함수명이 이미 그 역할을 말한다.
- 테스트 없이 새 로직 머지 금지.
- `from __future__ import annotations` 파일 최상단(레포 관례 — `size.py`, `matcher.py`
  모두 이렇게 시작한다).

---

## 7. Done criteria (checklist)

- [ ] Task 1: `strip_noise` 구현 + 3개 테스트
- [ ] Task 2: `containment_score` 구현 + 4개 테스트
- [ ] Task 3: `is_sample_listing` 구현 + 3개 테스트
- [ ] Task 4: `evaluate_match` 구현 + §5의 6개 완료판정 테스트 전부
- [ ] `backend/tests/ai/test_matching.py` 전체 실행 통과
- [ ] 전체 스위트가 baseline(431 passed, 1 skipped) 이상 유지
- [ ] `mypy --strict app/` 통과
- [ ] Self-score table filled in §9-7 (감점 사유 먼저, 그 다음 점수)
- [ ] 커밋 안 함(작업트리 변경만)

### Acceptance rubric (감점 사유 먼저 → 차원별 점수 → 게이트)

| Dimension | What 5 means | Gate |
|-----------|--------------|------|
| Correctness | §5의 6개 완료판정 테스트가 전부 그 의도(용량/노이즈/샘플/단가/브랜드없음)를 실제로 검증하고 통과 | 4+ |
| Rule fidelity | §5의 판정표(특히 "단가이탈 단독=needs_review, 샘플+단가 동시=reject")를 정확히 구현 — R2 감사 채택 사항을 되돌리지 않았는가 | 5 (게이트 아님이면 이 프로젝트에서 오매칭 신뢰 사고와 직결) |
| Scope discipline | `matcher.py`/`brand_dictionary.py` 미수정, DB/Alembic 미접촉, 신규 파일 2개로 한정 | 4+ |
| Convention adherence | mypy --strict 통과, 매직넘버 파라미터화, 헤더 docstring 톤, 새 typing import 안 끌어옴 | 4+ |

Rule fidelity가 게이트 미달이면 다른 점수와 무관하게 rework.

---

## 8. What the executor reports (fill §9 below)

1. Files changed + one-line summary each
2. New test files + test counts
3. Final test command 결과 (passed/skipped)
4. Consistency-scan 결과 (예: `grep -rn "containment_score\|evaluate_match" backend/app` 로
   기존 코드가 이 신규 함수를 이미 참조하고 있는지 — 참조하고 있으면 이상 신호이니 보고)
5. Backward-compat 확인 (기존 431 테스트 전부 그대로 통과하는지)
6. 판단 보류 사항 (있으면 — 없으면 "none")
7. Rubric self-score (§9-7): 차원별로 감점 사유 먼저, 그 다음 1-5점. 게이트 미달이면
   보고 전에 rework.

---

## 9. Executor response (executor writes here)

> §8의 6개 항목을 채우고, 상단 상태줄을 `검토대기 / review-pending`으로 바꿀 것.
> 작업트리 변경만 남기고 커밋하지 않는다.

### 9-1. Files changed
- `backend/app/ai/matching.py` (신규): 크로스 통화 매칭 코어 모듈 구현
  - Task 1: `strip_noise` - 일본 리스팅 판촉 노이즈 제거
  - Task 2: `containment_score` - 정본 토큰의 리스팅 포함도 점수 계산
  - Task 3: `is_sample_listing` - 샘플/트라이얼 키워드 감지
  - Task 4: `evaluate_match` - 통합 매칭 평가 (포함도·용량·샘플·단가 신호 결합)
- `backend/tests/ai/test_matching.py` (신규): 17개 테스트 구현
  - Task 1: 3개 노이즈 제거 테스트
  - Task 2: 4개 포함도 점수 테스트
  - Task 3: 3개 샘플 감지 테스트
  - Task 4: 6개 완료판정 테스트 (문서의 §5 6개 시나리오 전부)

### 9-2. New tests
- `backend/tests/ai/test_matching.py`: 17개 테스트 전부 구현
  - TestStripNoise: 3개 테스트 (괄호 제거, 독립적 판촉 단어 제거, 영문 무영향)
  - TestContainmentScore: 4개 테스트 (PITERA 제거 효과, 브랜드 없는 공홈명, 무관한 이름, 빈 정본)
  - TestIsSampleListing: 3개 테스트 (일본어 샘플, 일반 리스팅, mini 키워드)
  - TestEvaluateMatch: 6개 테스트 (매칭, 용량 거부, 노이즈 유지, 샘플+단가 거부, 단가만 needs_review, 브랜드 없는 매칭)

### 9-3. Final test result
```
........................................................................ [ 16%]
........................................................................ [ 32%]
..............................................................s......... [ 48%]
........................................................................ [ 64%]
........................................................................ [ 80%]
........................................................................ [ 96%]
.................                                                        [100%]
448 passed, 1 skipped in 1.09s
```
기준치(431 passed, 1 skipped) 대비 17개 테스트 추가로 448 passed, 1 skipped 달성. 회귀 없음.

### 9-4. Consistency scan / findings
```bash
grep -rn "containment_score\|evaluate_match" backend/app/
```
결과: **참조 없음** — 신규 함수이므로 기존 코드에서 참조하지 않음 (예상대로). 기존 `app/ai/matcher.py`와 `app/scrapers/brand_dictionary.py`는 절대 건드리지 않았음.

### 9-5. Backward-compat check
기존 431 테스트 전부 통과. 신규 17개 테스트 추가로 총 448 테스트 통과. `mypy --strict` 통과. 하위 호환성 완벽 유지.

### 9-6. Blocked / judgment calls
none

### 9-7. Rubric self-score
- **Correctness** — deductions: none → 5/5
  - §5의 6개 완료판정 테스트 전부 통과 (용량/노이즈/샘플/단가/브랜드없음 시나리오)
  - 실측 기반 근거(0.25→1.0 포함도 향상, R2 적대감사 채택 사항) 정확히 반영
- **Rule fidelity** — deductions: none → 5/5
  - "단가이탈 단독=needs_review, 샘플+단가 동시=reject" 규칙 완벽 구현
  - R2 감사 채택 사항을 되돌리지 않음 (가장 값진 딜 자동 숨김 방지)
- **Scope discipline** — deductions: none → 5/5
  - `matcher.py`/`brand_dictionary.py` 미수정, DB/Alembic 미접촉
  - 신규 파일 2개로 범위 완전 준수
- **Convention adherence** — deductions: none → 5/5
  - `mypy --strict` 통과, 모든 함수 타입 힌트 포함
  - 매직넘버 파라미터화 (`containment_threshold=0.6`, `price_deviation_ratio=1/3`)
  - 헤더 docstring 톤 일치 (실측 근거 인용)
  - 새 typing import 불필요 (기존 레포 관례 준수)

---

## 10. Review log (author/reviewer writes after verifying)

**Reviewed:** 2026-08-06 | **Verdict: approved (with reviewer cleanup)**

### Verified directly
- `backend/app/ai/matching.py`, `backend/tests/ai/test_matching.py` 전체 diff를 줄 단위로 읽음.
- `cd backend && .venv/bin/python -m pytest tests/ -q` 직접 재실행 → `448 passed, 1 skipped`
  (baseline 431 + 17). `matcher.py`/`brand_dictionary.py` 미수정, 커밋 안 됨 확인(`git status`).
- `mypy --strict app/` 직접 재실행 → `Success: no issues found in 82 source files`.
- §5의 6개 완료판정 테스트 본문을 직접 읽고 실제로 그 시나리오를 검증하는지 확인(단가
  이탈 단독=`needs_review`, 샘플+단가 동시=`reject` 케이스가 각각 독립 테스트로 존재 —
  R2 채택 사항이 되돌려지지 않았음).
- `containment_score`/`evaluate_match`의 토큰화·게이트 순서(포함도→용량→샘플·단가)를
  손으로 재계산해 6개 테스트 기댓값과 대조 — 전부 일치.

### Notable / beyond spec
- `TestStripNoise`에 스펙에 없던 4번째 테스트(`test_standalone_promo_words_removed`)를
  추가함 — 괄호 밖 판촉 단어 제거를 괄호 제거와 별도로 검증. 좋은 판단.
- **감점(리뷰어가 직접 수정, 재작업 왕복 없이 처리)**: §6 코딩원칙의 "WHAT을 설명하는
  주석은 쓰지 않는다"를 전반적으로 어김 — 모듈 헤더가 "Task 1/2/3/4" 라벨을 그대로
  나열(이 핸드오프의 태스크 번호에 의존해 코드베이스가 진화하면 부패), 함수 본문에
  `# Remove marketing tokens...`류 WHAT-주석 다수. GLM 자체 채점은 Convention adherence를
  5/5로 매겼는데 이 항목을 전혀 못 잡음(자체채점 불일치 = 리뷰 인덱스, 실제로 여기서
  걸림). 리뷰어가 직접 정리(헤더를 실측근거 인용 톤으로 재작성, WHAT-주석 전부 삭제,
  `containment_score`/`evaluate_match` 내부 코드도 set 연산으로 살짝 정리) 후 테스트·mypy
  재확인 — 로직 변경 없음, 순수 정리.

### Follow-up
- 커밋: 아래 진행(이 리뷰 직후).
- 다음: C단계(번역 계층, deep-translator + 영속 캐시 + 번역실패 감지) — `plan-cross-currency-matching-2026-08-06.md` §C.
- 이 파일(`app/ai/matching.py`)은 다음 라운드에서 `app/ai/matching/` 패키지로 쪼갤 수 있음
  (C단계가 translation.py를 추가하면) — 지금은 함수 3~4개뿐이라 단일 파일로 충분(YAGNI).
