# 스크래퍼 현황

## 플랫폼별 상태

| 플랫폼 | 국가 | 방식 | 상태 | 쿼리 언어 |
|--------|------|------|------|----------|
| 네이버쇼핑 | KR | httpx + Naver Search API | ⚠️ 서비스 종료 예고 (아래 참조) | 한국어 |
| 올리브영 | KR | Playwright (Chrome) | ❌ 차단 (firecrawl 스텔스로도 실패, 08-05 재확인) | 한국어 |
| Sephora | US | Playwright (Chrome) | ✅ 정상 (08-05 라이브 확인) | 영어 |
| Ulta | US | httpx | ❌ 차단 (JS 셸만 반환, firecrawl도 차단) | 영어 |
| Amazon US | US | PA API 5.0 + HTML fallback | ✅ 정상 (08-05 셀렉터 수정, 키 없이 폴백 동작) | 영어 |
| Rakuten | JP | httpx + Rakuten API | ✅ 정상 (08-05 2026 엔드포인트 전환) | 일본어 |
| @cosme | JP | Playwright (Chrome) | ✅ 구현 완료 | 일본어 |
| Tmall | CN | Playwright (Chrome) | ✅ 구현 완료 | 중국어 |
| 小红书 | CN | Playwright (Chrome) | ✅ 구현 완료 | 중국어 |
| Instagram | GLOBAL | Instagram Graph API | ✅ 구현 완료 (토큰 필요) | - |
| TikTok | GLOBAL | TikTok Research API | ✅ 구현 완료 (키 필요) | - |

## 다국어 쿼리 번역

`collector.py`에서 `deep-translator` 라이브러리로 자동 번역.
어떤 언어로 입력해도 각 플랫폼에 맞는 언어로 변환 후 수집.

## 네이버 검색 API 종료 → NAVER API HUB 이관 (2026-06-29 공지, 2026-08-05 확인)

네이버 개발자센터가 **Search API·Search Trend·Shopping Insight 서비스 종료 및
NAVER API HUB(네이버 클라우드 플랫폼) 이관**을 공지했다.

이관 후 계약 (`guide.ncloud-docs.com/docs/apihub-migration`):

| 항목 | 기존 (Developers) | NAVER API HUB |
|------|------------------|---------------|
| 도메인 | `openapi.naver.com` | `naverapihub.apigw.ntruss.com` |
| 경로 | `/v1/search/news.json` | `/search/v1/news` |
| 인증 헤더 | `X-Naver-Client-Id` / `X-Naver-Client-Secret` | `X-NCP-APIGW-API-KEY-ID` / `X-NCP-APIGW-API-KEY` |
| 키 | 기존 키 **사용 불가** | NCP 콘솔에서 신규 발급 |
| 한도 | 일 25,000건 | 검색 통합 월 775,000건 · 50 RPS/키 (한시 무료) |

> **핵심 리스크: 쇼핑 검색이 이관 대상에 없다.** API HUB 검색 카테고리는 뉴스·블로그·
> 이미지·웹문서·백과사전·지식iN·지역·카페글뿐이다("쇼핑 인사이트"는 클릭 트렌드
> 데이터이지 상품 가격이 아니다). 2026-08-05 실측: `/search/v1/shop`·`/search/v1/shopping`
> → **404**, 대조군 `/search/v1/news` → 401(존재). 구 `openapi.naver.com/v1/search/shop.json`
> 은 아직 401(살아있음)이지만 종료 예고 대상이다. 같은 질문이 ncloud 포럼에도
> 올라와 있으나(2026-07-23, topic/616) 답변 없음.
>
> 즉 **한국 가격 데이터 소스를 재설계해야 한다** — 종료일 확인 후 (a) 종료 전까지 구 API
> 유지 (b) 쇼핑 스크래핑(403 이력 있음, firecrawl 스텔스 필요) (c) 쿠팡 파트너스 등
> 대체 소스 중 선택. 이 결정 전까지 네이버 라인은 키가 있어도 수명이 유한하다.

## Rakuten API 인증 (2026 신규)

```python
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
# 구 엔드포인트 app.rakuten.co.jp 는 폐기됨

params = {
    "applicationId": settings.rakuten_app_id,   # UUID 형식
    "accessKey": settings.rakuten_access_key,    # pk_ 로 시작
    "keyword": query,
}
headers = {
    "Referer": "https://wsungahn.github.io",
    "Origin": "https://wsungahn.github.io",
}
# Referer/Origin 없으면 REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING 에러
```

등록 포털: `webservice.rakuten.co.jp` (= `developer.rakuten.com`으로 통합)
Allowed websites 입력 시 `https://` 없이 도메인만: `wsungahn.github.io`

## Sephora 수집 방식

CSS 셀렉터 대신 네트워크 응답 인터셉션 사용.
```python
async def handle_response(resp):
    if "/api/v2/catalog/search/" in resp.url and resp.status == 200:
        api_data["products"] = (await resp.json()).get("products", [])

page.on("response", handle_response)
await page.goto(url, wait_until="domcontentloaded", timeout=30000)
await page.wait_for_timeout(8000)
```

## 차단된 플랫폼 해결 방향

| 플랫폼 | 현재 상태 | 해결 방향 |
|--------|----------|----------|
| 올리브영 | 403 봇 차단 | 공식 파트너 API 협의 또는 제외 |
| 쿠팡 | 403 봇 차단 | Coupang Partners API 연동 |
| Amazon US | 503 봇 차단 | Amazon PA API (affiliate 계정 필요) |

## 캐시 정책

- TTL: 24시간 (플랫폼 단위)
- 이미 수집된 플랫폼은 스킵, 누락된 플랫폼만 재수집
- 정규 제품명: 유저 입력 쿼리 → `product.name_kr`로 저장
- 스크래퍼 반환 상품명 → `sale_event.scraped_name`에 보존
- 기획세트 감지: "세트", "set", "kit", "duo", "bundle", "기획" 등 → `is_bundle=True`

## 활성 스크래퍼 (2026-08-05 기준)

`ENABLED_SCRAPERS` 기본값 = `Sephora,Amazon US,Rakuten` — 라이브 실측으로 살아있는
것만 켠다. 네이버쇼핑(API 종료)·올리브영·Ulta·아모레몰은 전부 차단/종료 확인됐다.

**조용한 실패 금지**: 스크래퍼가 아무것도 못 받았을 때 빈 리스트를 반환하면
"할인이 없다"로 읽혀 고장이 숨는다. 파싱 결과가 0건이면 `confidence=0` 이벤트에
원인을 담아 반환할 것(Ulta가 이 방식으로 몇 달간 죽은 채 방치됐다). 수집기는
이름이 빈 이벤트를 저장하지 않는다 — 셀렉터가 깨졌다는 신호이지 상품이 아니다.
