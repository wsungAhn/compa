# 스크래퍼 현황

## 플랫폼별 상태

| 플랫폼 | 국가 | 방식 | 상태 | 쿼리 언어 |
|--------|------|------|------|----------|
| 네이버쇼핑 | KR | httpx + Naver Search API | ✅ 정상 | 한국어 |
| 올리브영 | KR | Playwright (Chrome) | ⚠️ 403 차단 | 한국어 |
| 쿠팡 | KR | httpx + BeautifulSoup | ⚠️ 403 차단 | 한국어 |
| Sephora | US | Playwright (Chrome) | ✅ 정상 | 영어 |
| Amazon US | US | httpx + BeautifulSoup | ⚠️ 503 차단 | 영어 |
| Rakuten | JP | httpx + Rakuten API | ✅ 정상 | 일본어 |

## 다국어 쿼리 번역

`collector.py`에서 `deep-translator` 라이브러리로 자동 번역.
어떤 언어로 입력해도 각 플랫폼에 맞는 언어로 변환 후 수집.

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
