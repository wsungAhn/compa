# 설계 — platform_product_ids (외부 상품 식별자 저장) — 2026-08-09

- 작성: 2026-08-09 PDT · Mac Studio (`mac.lan`)
- Tier: **2** (`review-tiers.md` — 새 테이블+새 데이터 흐름 도입)
- 감사 라운드: 아직 시작 안 함(이 세션은 초안 작성까지 — 착수 전 Codex 핸드오프
  이전에 적대 감사 라운드가 선행돼야 함, `review-tiers.md` 기준)
- 대상 파일(1단계 기준): `backend/alembic/versions/`(신규 마이그레이션),
  `backend/app/models/`(신규 모델 `platform_product_id.py`)

> PRD `docs/PRD-2026-08-07.md`의 "식별자 폐기 실측" 절(2026-08-09 추가분)의 후속.
> **아주 쉽게 쓴다** — 이 문서를 처음 읽는 사람도 "뭘, 왜, 어떻게" 순서로 끝까지
> 따라갈 수 있게 목표로 한다.

---

## 0. 이 문서가 뭘 위한 것인가 (한 문단 요약)

지금 compa는 "이 한국 상품과 저 일본 상품이 같은 물건인가?"를 **이름을 보고
추측**해서 판단한다(번역 → 비슷한 단어 세기 → 애매하면 Claude에게 물어봄).
이 방식은 느리고, 틀리기 쉽고, LLM 호출이 필요해서 이번 크레딧 전소 사고의
원인 중 하나였다. 그런데 실제로는 **각 사이트가 이미 "이 상품의 진짜 번호"를
알려주고 있는데 compa가 그걸 무시하고 버리고 있었다**. 이 설계는 그 번호를
저장하는 작은 테이블 하나를 만들어서, "이름 추측" 대신 "번호 대조"로 상품을
연결하자는 것이다.

**비유**: 지금 방식은 사람 이름만 보고 "이 사람이 그 사람 맞나?"를 판단하는
것과 같다(동명이인 있으면 틀림). 이 설계는 주민등록번호(=상품 식별자)를 저장해서
대조하자는 것 — 훨씬 정확하고, 컴퓨터가 즉시 판단 가능하다(사람이 고민할 필요 없음).

---

## 1. 문제를 아주 구체적인 예시로

Tatcha라는 브랜드의 "The Dewy Skin Cream"이라는 화장품이 있다고 하자.

- **일본 Rakuten**에서 이 상품을 검색하면 API가 이렇게 응답한다:
  ```json
  {"itemName": "タチャ デューイースキンクリーム", "itemCode": "shop123:10000456", "itemPrice": 8200}
  ```
  `itemCode`가 이 상품의 고유 번호다. **이 번호는 이름이 바뀌어도(할인 이름이
  붙거나 오타가 나도) 안 바뀐다.**
- **미국 Amazon**에서 같은 상품을 검색하면 이런 링크가 온다:
  ```
  https://www.amazon.com/dp/B08XYZ1234?tag=...
  ```
  `B08XYZ1234`가 ASIN(Amazon Standard Identification Number) — 아마존 안에서
  이 상품의 고유 번호다.
- **브랜드 공홈(Shopify)**에서는 상품 목록 API(`products.json`)가 이렇게 준다:
  ```json
  {"id": 7891234567, "handle": "the-dewy-skin-cream", "title": "The Dewy Skin Cream"}
  ```
  `id`와 `handle` 둘 다 이 상품의 고유 번호/별칭이다.

**지금 compa 코드는 이 셋을 전부 읽고도 버린다.** 이름(`itemName`, `title`)만
저장하고 번호는 저장 안 한다 — 그래서 "이 세 개가 같은 상품이다"를 알아낼
방법이 이름 비교밖에 안 남는다.

**만약 이 번호들을 저장해뒀다면**: 다음에 Rakuten을 다시 수집할 때
`itemCode=shop123:10000456`가 그대로 다시 오니까, "저번에 저장한 그 상품이네"를
번호 하나 비교로 즉시 알 수 있다. 지금은 그것도 이름을 다시 비교해서 판단한다.

---

## 2. 선행조사

*(CLAUDE.md 규정: Tier 2+ 설계는 이 섹션이 필수. `scripts/design_lint.py`가
존재 여부를 검사한다.)*

**레포 내 검색:** `grep`으로 `app/**/*.py`와 `alembic/versions/*.py` 전체에서
`external_id`, `platform_id`(기존 것 확인용), `sku`, `SKU`, `gtin`, `GTIN`,
`upc`, `UPC`, `ean`, `EAN`, `asin`, `ASIN`, `item_code`, `itemCode` 검색.
**결과: 없음.** `Product` 모델(`app/models/product.py`)에는 4개 언어 이름
컬럼(`name_kr`/`name_en`/`name_jp`/`name_cn`)만 있고 외부 식별자 컬럼이 하나도
없다. `ProductMatchCandidate` 테이블은 있지만 이건 "애매한 매칭 후보를 사람이
검토하는 큐"이지 식별자 저장소가 아니다(용도가 다름 — 재사용 불가, 새로 만들어야
함). Sephora 스크래퍼(`app/scrapers/us/sephora.py:77`)가 `currentSku`를 읽고
있긴 한데 가격 파싱에만 쓰고 저장은 안 한다 — 이것도 "식별자를 받고 버리는" 같은
패턴의 증거.

**외부 선행작업:** 아래 4건을 확인했다(전부 확인일 2026-08-09). "최근 커밋일"은
이 넷이 오픈소스 저장소가 아니라 API 공식 문서/국제 표준이라 해당 없음 — 대신
문서 최종 확인일을 적었다.

| 이름 | URL | 라이선스/성격 | 최근 커밋일(해당 없음 — 확인일로 대체) | 채택 판단 |
|---|---|---|---|---|
| **GTIN/UPC/EAN/JAN 표준** | [GTIN vs UPC vs EAN vs ASIN 개요](https://www.bebolddigital.com/blog/gtin-vs-upc-vs-ean-vs-asin-understanding-barcode-basics) | 국제 바코드 표준(오픈 표준, 라이선스 없음 — 누구나 쓸 수 있는 공개 규격) | 확인일 2026-08-09 | **채택** — "같은 물건이면 같은 번호"라는 설계 원칙 자체를 이 표준에서 가져온다. 단, 화장품은 브랜드 공홈 상품에 바코드가 API로 노출 안 되는 경우가 많아 **보조 식별자**로만 쓴다(1순위 아님) |
| **가격추적 업계 관행(Apify 상용 스크레이퍼 사례)** | [Cross-Retailer Price Comparison](https://pagecrawl.io/blog/cross-retailer-price-comparison-product-monitoring), [GTIN 기반 매칭](https://www.minderest.com/blog/google-shopping-ean-upc-gtin-scraping) | 상용 SaaS, 코드 비공개(재사용 대상 아님 — 라이선스 확인 불필요, 코드를 안 가져오므로) | 확인일 2026-08-09 | **패턴만 참고, 코드 미채택** — 핵심 관행: "UPC/EAN/GTIN/MPN으로 먼저 대조하고, 그게 없을 때만 이름+브랜드 조합으로 대조하며, 그마저 애매하면 그때만 AI로 확인한다." 이 우선순위(식별자 → 이름 조합 → AI)를 그대로 채택 |
| **Shopify Storefront/Admin API의 SKU/variant id** | [ProductVariant - Storefront API](https://shopify.dev/docs/api/storefront/latest/objects/ProductVariant) | Shopify 공식 API 문서(무료 공개 사용, 라이선스 이슈 없음 — API 스펙일 뿐 코드가 아님) | 확인일 2026-08-09 | **채택** — `products.json` 응답의 `id`(숫자, 상품 고유)와 `handle`(URL용 별칭)을 그대로 저장. 우리가 이미 이 API를 부르고 있으니(스크래퍼 26개 브랜드) 추가 개발 없이 저장만 하면 됨 |
| **Rakuten Ichiba Item Search API의 itemCode** | [공식 문서](https://webservice.rakuten.co.jp/documentation/ichiba-item-search) | 공개 API 스펙, 라이선스 이슈 없음 | 확인일 2026-08-09 | **채택** — 문서에 `itemCode`가 검색 파라미터이자 응답 필드로 명시. 장기 안정성(번호가 안 바뀌는지)에 대한 공식 보증 문구는 못 찾았으나(문서에 명시 없음), 업계 표준 관행상 상품 고유 코드는 변하지 않는 게 일반적 — **채택하되 "값이 바뀌면 새 상품으로 오인식할 수 있다"는 리스크를 아래 "리스크" 절에 남긴다** |
| **Amazon ASIN** | 자체 지식(공식 문서 접근은 PA-API 키 필요, 이 세션에선 URL 패턴만 확인) | Amazon 공식 식별자 | 확인일 2026-08-09 | **채택** — `DetailPageURL` 응답에서 `/dp/ASIN코드` 패턴으로 정규식 추출 가능(이미 URL을 저장하고 있으니 추출만 추가) |

**결론:** 개선해서 채택한다. 새로 발명하지 않는다 — 업계가 이미 쓰는 순서
(식별자 우선 → 이름 조합 → 그래도 애매하면 사람 검토)를 그대로 가져오고, 우리
소스들이 이미 API 응답에 갖고 있는 필드(itemCode/ASIN/handle)를 저장하는 작은
테이블 하나만 새로 만든다. LLM은 이 설계에 등장하지 않는다(PRD의 "LLM 공급
정책" 절과 일치).

---

## 3. 무엇을 만드는가 — 테이블 하나

새 테이블 이름: `platform_product_ids`

| 컬럼 | 뜻 | 예시 값 |
|---|---|---|
| `id` | 이 행 자체의 번호(내부용, 신경 안 써도 됨) | (자동생성 UUID) |
| `product_id` | compa의 `products` 테이블 어느 행인지 (외래키) | (Tatcha Dewy Skin Cream의 UUID) |
| `platform_name` | 어느 사이트의 번호인지 | `"Rakuten"`, `"Amazon US"`, `"Tatcha 공홈"` |
| `external_id` | 그 사이트가 준 진짜 번호 | `"shop123:10000456"`, `"B08XYZ1234"`, `"7891234567"` |
| `created_at` | 언제 처음 저장했는지 | (자동) |

**유니크 제약**: `(platform_name, external_id)` 조합은 딱 한 번만 존재해야
한다 — 같은 사이트의 같은 번호가 두 상품에 붙으면 안 되니까.

**이 테이블이 생기면 뭐가 달라지나:**

| | 지금 | 이 테이블이 생긴 후 |
|---|---|---|
| Rakuten을 다시 수집할 때 | 상품 이름을 번역·정규화해서 기존 상품과 비교(느림, 가끔 틀림) | `external_id`가 일치하는 행이 있는지 딱 한 번 조회(빠름, 절대 안 틀림) |
| 신규 상품 발견 | 이름만 보고 신규인지 기존인지 애매하면 Claude에게 물어봄 | 번호가 새 번호면 100% 신규 확정, LLM 안 부름 |
| 매칭 실패로 인한 중복 생성 | 종종 발생(로그에 흔적 있음) | 애초에 발생 안 함(번호 기준이라 애매함이 없음) |

---

## 4. 구현 순서 — Working Skeleton First (한 번에 다 안 만든다)

**1단계 (제일 쉬움, 먼저)**: 테이블만 만든다(Alembic 마이그레이션). 아무 스크래퍼도
아직 안 건드림 — 그냥 그릇만 준비.

**2단계**: 스크래퍼 3곳(Shopify 공홈, Rakuten, Amazon) 중 **Shopify 공홈부터**
— 이미 산출량이 가장 많고(sale_events의 86%), API 응답에 `id`가 명확히 있어서
제일 쉽다. 스크래퍼가 상품을 저장할 때 `platform_product_ids`에도 한 줄 같이
쓰게 한다.

**3단계**: Rakuten, Amazon 순서로 같은 방식 추가.

**4단계(나중, 이 설계 범위 밖)**: 매칭 로직(`matcher.py`)이 이름 비교 전에
"이 external_id가 이미 저장돼 있나?"를 먼저 확인하도록 바꾼다. 이게 실제로
LLM 호출을 줄이는 부분인데, 1~3단계로 데이터가 어느 정도 쌓인 뒤에 손대는 게
순서에 맞다(데이터 없이 로직부터 바꾸면 테스트할 게 없음).

---

## 5. 리스크 (숨기지 않고 미리 적어둠)

- **번호가 언젠가 바뀔 수 있다**: 브랜드가 Shopify 상품을 삭제하고 새로 만들면
  `id`가 바뀐다. 이러면 "새 상품"으로 오인식 — 이름 비교보다는 훨씬 드문 일이지만
  0%는 아니다. 대응: 발생하면 그때 `ProductMatchCandidate` 큐로 사람이 병합하면
  됨(이미 있는 안전망).
- **Amazon ASIN 추출은 정규식 하나 추가**라 리스크 거의 없음.
- **이 설계는 매칭 로직 자체를 아직 안 바꾼다**(4단계는 범위 밖) — 그래서 이
  1~3단계만으로는 LLM 호출이 당장 줄지 않는다. "데이터를 쌓는 단계"라는 걸
  착수 전에 분명히 인지할 것 — 성과가 바로 안 보인다고 잘못됐다고 오해하지 말 것.

## 6. 완료 판정 (이걸 보면 "됐다"를 알 수 있음)

- `platform_product_ids` 테이블이 DB에 존재하고, `alembic upgrade head`가 에러 없이 통과
- Shopify 공홈 스윕 1회 실행 후, `select count(*) from platform_product_ids where platform_name like '%공홈%'`가 0보다 큼
- 같은 상품을 다시 스윕했을 때 `platform_product_ids` 행 수가 **늘지 않음**(중복 안 생김 — 유니크 제약이 지켜지는지 확인)
