# 설계 — 브랜드 공홈(Shopify) 소스 (2026-08-05)

> **범위**: 럭셔리 화장품 브랜드 공식몰에서 할인 이벤트를 구조화 데이터로 수집.
> 이번 레이어는 **Shopify 표준 `/products.json`을 쓰는 브랜드 4곳**까지만.

## 배경

메인 시장이 미국인데, 리테일 소스는 계속 좁아지고 있다 — Ulta 차단, 올리브영
차단, 네이버 종료, Amazon은 HTML 폴백(마크업 바뀌면 또 깨진다). 사용자가 지목한
"메이저 럭셔리 브랜드 공홈 이벤트"가 대안이 되는지 실측했다.

## 선행조사

### ① 레포 내 검색

`app/scrapers/brands/` 전수 확인(도구: `pathlib` 스캔).

| 기존 | 방식 | 실측 결과 |
|---|---|---|
| `skii.py` | firecrawl + LLM 추출, `PROMO_URL=/our-products/category/value-gift-sets` | ❌ 0건 — 공홈이 Shopify로 이전하며 URL이 `/collections/…`로 바뀜 |
| `tatcha.py` | 동일 패턴 | ❌ 대상 URL 404 |
| `laprairie.py`·`lamer_kr.py`·`chantecaille_kr.py` | 동일 패턴 | 미검증 (La Mer 계열 도메인은 403) |
| `firecrawl_base.py` | 동적 URL 지원 베이스 | 살아있음, 다만 LLM 추출 의존 |

즉 **공홈 수집 자체는 이미 시도됐고 URL 드리프트로 죽어 있었다.**

### ② 외부 — 라이브 실측 (2026-08-05)

에스티로더 계열(La Mer·Estée Lauder·Clinique)은 403(Akamai)으로 HTML 접근 불가.
반면 Shopify 기반 브랜드는 표준 `/products.json`이 열려 있다:

| 브랜드 | `/products.json` | 비고 |
|---|---|---|
| SK-II | ✅ | `price=205.00` |
| **Tatcha** | ✅ | `price=75.00`, **`compare_at_price=103.00`** → 할인 27% |
| La Prairie | ✅ | `price=3015.00` |
| Glossier | ✅ | 샘플 품목 다수 |
| Drunk Elephant | ❌ 410 | Shopify지만 엔드포인트 비활성 |
| Charlotte Tilbury·Augustinus Bader | ❌ 404 | Shopify 아님 |

핵심은 **`compare_at_price`**다. 지금까지 할인 여부는 HTML에서 추론하거나 LLM에
맡겼는데, 이 필드는 정가를 값으로 준다 — 추론 없이 `original_price`를 채운다.

### ③ 결론

firecrawl+LLM 추출 대신 **Shopify 공식 JSON**을 쓴다. 차단이 없고(봇 판정 대상이
아님), 스키마가 고정이라 마크업 드리프트에 안 깨지고, LLM 호출이 0이다
(Deterministic First). 새 프레임워크가 아니라 `BaseScraper` 서브클래스 하나 +
브랜드별 3줄짜리 서브클래스다.

## 설계

`app/scrapers/brands/shopify.py`

- `parse_products(payload, query, brand, base_url)` — 순수 함수. variants 중
  최저가를 택하고, `compare_at_price > price`일 때만 `original_price`·
  `discount_rate`를 채운다
- `ShopifyBrandScraper(BaseScraper)` — `DOMAIN`/`BRAND`/`PLATFORM_NAME`만 정의하면
  되는 베이스. 실패·빈 응답은 `confidence=0` 이벤트로 표면화(조용한 실패 금지)
- 브랜드 서브클래스 4종: SK-II·Tatcha·La Prairie·Glossier

`products.json`은 검색이 아니라 카탈로그이므로 쿼리 토큰으로 필터한다
(`FirecrawlBaseScraper`의 기존 필터와 같은 정책).

## 범위 밖 (다음 레이어)

- 죽은 브랜드 스크래퍼 5종 삭제 — 이 소스가 데이터를 채운 뒤 별도 커밋
  (Delete, Don't Deprecate)
- 403 브랜드(에스티로더 계열) 대응
- 페이지네이션(250건 초과 카탈로그)
