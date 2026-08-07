# 독립 감사 보고서: 크로스 통화 매칭 D단계 설계 (2026-08-06)

## 감사 개요

- **감사 대상**: `design-cross-currency-matching-d-stage-2026-08-06.md` 설계문서
- **감사 기간**: 2026-08-06
- **감사자**: 독립 감사자 (맥락 없음)
- **감사 방법**: 설계문서 분석 + B/C단계 산출물 코드 검토
- **참고 파일**: 
  - `app/ai/matching.py` (evaluate_match 함수)
  - `app/ai/translator.py` (translate_for_matching 함수)
  - `app/models/product.py`, `app/models/sale_event.py`

## 감사 결과 요약

**전반적 평가**: 설계는 논리적으로 타당하지만, 동시성 제어, 트랜잭션 안전성, 데이터 무결성 측면에서 심각한 결함이 존재합니다. 특히 병합 과정에서 발생할 수 있는 경쟁 상황과 고아 선별 쿼리의 누락 케이스가 가장 큰 위험 요소입니다.

---

## 심각한 결함 (Critical)

### 1. 동시성 문제: `product_match_candidates` 유니크 제약의 허점

**위험도**: 🔴 **Critical**
**근거**: 
- 설계는 `orphan_product_id`에 유니크 제약을 걸어 "같은 orphan에 대한 중복 후보 생성을 방지"한다고 명시
- 하지만 **동일한 orphan을 두 Celery worker가 동시에 스캔하는 경우**를 고려하지 않음
- 실제 시나리오: 
  1. Worker A: `orphan X`를 발견하고 `product_match_candidates`에 `pending` 상태로 삽입 시작
  2. Worker B: 동일한 `orphan X`를 발견하고 삽입 시도 (유니크 제약으로 실패)
  3. Worker B: "이미 후보가 있다"고 판단하고 **스캔을 건너뜀**
  4. 결과: Worker A의 매칭 결과가 Worker B에 의해 **영구히 가려짐**

**영향**: 
- 매칭 품질 저하 (높은 점수의 후보가 낮은 젠포에 의해 덮어씌워짐)
- 데이터 무결성 손상
- 디버깅이 매우 어려움 (로그에 두 worker의 경쟁 흔적만 남음)

**대안**: 
- `INSERT ... ON CONFLICT (orphan_product_id) DO NOTHING` 패턴 사용
- 후보 생성 전에 `SELECT`로 기존 상태 확인 (race condition 여전히 존재)
- 더 나은 방법: `INSERT` 시도 → 실패 시 `UPDATE`로 상태 갱신 (멱등성 보장)

### 2. 트랜잭션/락 문제: `_merge_products`의 원자성 결여

**위험도**: 🔴 **Critical**
**근거**: 
- `_merge_products` 함수는 두 개의 독립적인 작업을 수행:
  1. `SaleEvent.product_id` 재할당 (UPDATE 쿼리)
  2. `orphan_product`의 `deleted_at` 설정 (UPDATE 쿼리)
- 이 두 작업 사이에 **트랜잭션 경계가 명확하지 않음**
- 동일한 `canonical_product`를 대상으로 여러 `_merge_products`가 동시에 실행될 경우:

**시나리오**:
```
Worker A: orphan X → canonical Y (SaleEvent 재할당 중)
Worker B: orphan Z → canonical Y (SaleEvent 재할당 중)
```
- 결과: 두 worker가 동시에 `sale_events` 테이블의 `product_id`를 업데이트
- DB 락 메커니즘에 따라 **일부 업데이트가 실패하거나 부분적 상태** 발생 가능

**영향**: 
- `SaleEvent`가 두 개의 다른 `Product`에 동시에 속하는 데이터 불일치
- 비즈니스 로직 오작동 (comparison API에서 중복된 가격 정보 표시)
- 데이터 복구가 매우 어려움

**대안**: 
- `_merge_products` 전체를 단일 트랜잭션으로 감싸기
- `SELECT ... FOR UPDATE`로 `canonical_product`에 행 락 걸기
- 병합 작업 전에 `canonical_product`의 `deleted_at`이 NULL인지 재확인

### 3. 고아 선별 쿼리의 누락 케이스

**위험도**: 🔴 **Critical**
**근거**: 
- 고아 선별 쿼리: `WHERE name_en IS NULL AND name_jp IS NOT NULL AND brand IS NOT NULL`
- **`name_kr`이 NULL이면서 `name_jp`가 있는 경우**를 고려하지 않음
- **`name_cn`이 NULL이면서 `name_jp`가 있는 경우**를 고려하지 않음

**실제 발생 가능 시나리오**:
1. 스크래핑 오류로 `name_en`은 실패했지만 `name_jp`는 성공한 경우
2. 다국어 스크래핑 로직의 버그로 특정 언어만 채워진 경우
3. 일본 전용 제품 (JP 이름만 있고 다른 국가 이름 없음)

**영향**: 
- **유효한 고아 상품이 매칭 대상에서 누락됨**
- 데이터 일관성 손실
- 매칭 커버리지 감소

**대안**: 
```sql
WHERE (name_en IS NULL OR name_kr IS NULL OR name_cn IS NULL) 
  AND name_jp IS NOT NULL 
  AND brand IS NOT NULL
```
- 또는 더 보수적인 접근: `name_jp IS NOT NULL AND brand IS NOT NULL` (다른 언어 상태 무관)

---

## 높은 우선순위 결함 (High)

### 4. 최고점 선택 로직의 오매칭 위험

**위험도**: 🟡 **High**
**근거**: 
- "후보 중 `containment_score`가 가장 높은 것 하나만 고른다"는 로직
- **동점 상황에서의 타이브레이크 로직이 없음**
- 설계에서 "동점·근소차 타이브레이크는 범위 밖"이라고 명시

**위험 시나리오**:
```
Candidate A: containment_score = 0.85 (needs_review)
Candidate B: containment_score = 0.85 (match)
```
- 결과: **Candidate A가 선택될 수 있음** (DB 조회 순서에 따라)
- `needs_review` 상태인 후보가 `match` 상태인 후보보다 먼저 조회될 경우

**영향**: 
- **잠재적 오매칭**: `needs_review` 상태의 후보가 자동으로 선택됨
- 검토 UI의 신뢰성 저하
- 관리자의 수동 검토 부담 증가

**대안**: 
- 상태 우선순위 도입: `match` > `needs_review` > `reject`
- 동점 시 `containment_score` 외의 추가 기준 적용 (예: 용량 일치 여부)
- 최소 2개 이상의 후보를 제시하여 관리자 선택 권한 부여

### 5. 멱등성 부재: admin.py의 approve/reject 로직

**위험도**: 🟡 **High**
**근거**: 
- 설계에서 "이미 `approved`/`rejected`인 행에 다시 호출하면 409(멱등성 깨는 재승인 방지)"라고 명시
- 하지만 **409 응답이 발생하더라도 상태 변경이 이미 일어났을 수 있음**

**문제점**:
1. **레이스 컨디션**: 
   - Client A: `approve` 호출 (status="approved"로 업데이트)
   - Client B: 동시에 `reject` 호출 (409 오류 발생)
   - 결과: 상태가 "approved"로 변경되었지만 Client B는 실패로 인식

2. **부분 실패 처리 없음**:
   - `UPDATE` 쿼리가 일부 행만 성공할 경우
   - 트랜잭션 롤백이 발생하지 않음

**영향**: 
- API 응답과 실제 DB 상태 불일치
- 클라이언트의 재시도 로직에서 예기치 않은 동작
- 데이터 무결성 문제

**대안**: 
- `UPDATE` 쿼리에서 `WHERE status = 'pending'` 조건 추가
- 영향받은 행 수를 반환하여 클라이언트에 상태 알림
- idempotent한 업데이트 패턴 사용 (`SET status = 'approved', decided_at = NOW() WHERE id = :id AND status = 'pending'`)

---

## 중간 우선순위 결함 (Medium)

### 6. B/C단계 산출물과의 연동 문제

**위험도**: 🟠 **Medium**
**근거**: 
- D단계 설계가 B/C단계 산출물을 올바르게 사용하고 있는지 검토 필요
- `evaluate_match`와 `translate_for_matching` 시그니처 대조 결과:

**`evaluate_match` 시그니처**:
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
) -> str
```

**D단계에서의 사용**:
```python
verdict = evaluate_match(
    candidate.name_en, 
    translated, 
    canonical_size_ml=matched_size,
    listing_size_ml=orphan_size,
    canonical_unit_price=...,
    listing_unit_price=...
)
```

**문제점**:
1. **매개변수 불일치**: D단계에서 `canonical_unit_price`와 `listing_unit_price`를 계산해서 전달하지만, 실제로는 통화 변환이 필요함
2. **용량 처리**: `sizes_match()`를 별도로 호출한 후에 `evaluate_match`에 다시 전달하는 중복 로직
3. **`translate_for_matching`의 실패 처리**: D단계에서 `None`을 반환하면 건너뛴다고 명시, 하지만 이 로직이 명확하지 않음

**영향**: 
- 의도치 않은 매칭 결과
- 코드 중복과 유지보수 어려움
- B/C단계 산출물의 재사용성 저하

**대안**: 
- D단계에서 통화 변환 로직 명확히 분리
- `evaluate_match` 호출 전에 필요한 모든 데이터를 정규화
- 번역 실패 시 로깅 강화

### 7. 고아 선별 쿼리의 성능 문제

**위험도**: 🟠 **Medium**
**근거**: 
- 고아 선별 쿼리: `SELECT * FROM products WHERE name_en IS NULL AND name_jp IS NOT NULL AND deleted_at IS NULL AND brand IS NOT NULL AND id NOT IN (SELECT orphan_product_id FROM product_match_candidates)`
- `NOT IN` 서브쿼리는 **대규모 데이터에서 성능 저하** 발생
- 인덱스가 있더라도 전체 테이블 스캔이 필요할 수 있음

**영향**: 
- 배치 작업 지연
- DB 부하 증가
- 확장성 저하

**대안**: 
- `LEFT JOIN` + `IS NULL` 패턴으로 변경:
  ```sql
  SELECT p.* FROM products p 
  LEFT JOIN product_match_candidates pmc ON p.id = pmc.orphan_product_id
  WHERE p.name_en IS NULL AND p.name_jp IS NOT NULL AND p.deleted_at IS NULL AND p.brand IS NOT NULL AND pmc.id IS NULL
  ```
- 별도 인덱스 생성 고려

---

## 낮은 우선순위 개선점 (Low)

### 8. 실패 처리 로직의 미비함

**위험도**: 🔵 **Low**
**근거**: 
- 번역 실패 시 "건너뛴다"고만 명시되어 있음
- **실패 이유에 대한 구분이 없음**:
  - 일시적 실패 (네트워크 문제)
  - 영구적 실패 (텍스트 이해 불가)
  - 품질 문제 (번역 결과가 의미 없음)

**영향**: 
- 모든 실패가 동일하게 처리되어 재시도 효율성 저하
- 문제 진단이 어려움

**대안**: 
- 실패 유형별 분류 (temporary, permanent, quality)
- 재시도 전략 차별화 (일시적 실패는 즉시 재시도, 영구적 실패는 영원히 건너뜀)
- 실패율 모니터링

### 9. 모니터링 및 알림 메커니즘 부재

**위험도**: 🔵 **Low**
**근거**: 
- 설계에 **모니터링이나 알림 메커니즘**이 전혀 없음
- 매칭 성공률, 실패율, 처리량 등 추적 불가

**영향**: 
- 운영 문제 조기 발견 불가
- 성능 저하 감지 어려움
- 사용자 경험 모니터링 불가

**대안**: 
- 매칭 성공률 지표 추적
- 이상 패턴 감지 (예: 특정 브랜드의 매칭 실패율 급증)
- 관리자 알림 시스템 도입

---

## 권장 조치 우선순위

1. **즉시 조치 (Critical)**:
   - 동시성 문제 해결 (INSERT ... ON CONFLICT 또는 락 메커니즘)
   - `_merge_products`의 트랜잭션 안전성 확보
   - 고아 선별 쿼리의 누락 케이스 보완

2. **단기 조치 (High)**:
   - 최고점 선택 로직의 타이브레이크 메커니즘 도입
   - admin.py의 멱등성 강화

3. **중기 조치 (Medium)**:
   - B/C단계 산출물과의 연동 개선
   - 고아 선별 쿼리 성능 최적화

4. **장기 조치 (Low)**:
   - 실패 처리 로직 강화
   - 모니터링 시스템 도입

---

## 결론

D단계 설계는 전반적인 아키텍처는 타당하지만, **동시성 제어와 데이터 무결성 측면에서 심각한 결함**이 존재합니다. 특히 병합 과정에서 발생할 수 있는 경쟁 상황과 고아 선별 로직의 누락이 가장 시급히 해결해야 할 문제입니다.

이러한 결함들은 **실제 운영 환경에서 데이터 불일치, 오매칭, 서비스 중단** 등 심각한 문제로 이어질 수 있습니다. 반드시 위에서 제시된 Critical 및 High 우선순위 조치를 먼저 구현한 후에 배치를 진행해야 합니다.