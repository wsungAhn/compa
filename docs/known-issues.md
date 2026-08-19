# 알려진 기술 제약 및 해결 방향 (2026-08-19 전면 갱신 — 이전판은 5월 WSL 초기 상태로 대부분 해소됨)

## 프로덕션 배포 환경

프로덕션은 **Mac Studio(launchd)**에서 상시 가동 중이다(WSL/Docker 기반 아님).
자세한 내용은 `ops/README.md` 참고. 이 문서 아래의 "개발 환경" 절은 **로컬
WSL 개발 환경**에만 해당하고 프로덕션과 무관하다.

### 로컬 WSL 개발 환경 — Docker 데몬 자동 시작 안 됨
WSL 재부팅 시 Docker CE 데몬이 자동으로 시작되지 않아 DB 연결 실패.

**증상:** uvicorn 시작 시 `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)`

**해결:** `start.bat`에 `sudo service docker start` 포함 + passwordless sudo:
```bash
echo "compa ALL=(ALL) NOPASSWD: /usr/sbin/service docker start" | sudo tee /etc/sudoers.d/docker-start
```

### Playwright + Ubuntu 26.04 (WSL 로컬 환경)
번들 Chromium이 Ubuntu 26.04-x64를 지원하지 않는다. Google Chrome을 직접
설치해 `executable_path="/usr/bin/google-chrome-stable"`로 지정해야 한다
(모든 Playwright 스크래퍼 공통). Mac 프로덕션에서는 이 문제 없음(시스템
Chrome 채널 사용).

---

## 차단된/제한된 스크래퍼 (2026-08-19 재확인)

### 올리브영 / 쿠팡 (403)
강력한 봇 차단, `SKIP_SCRAPERS`로 제외 상태 유지. 미해결.
해결 방향: 공식 파트너 API 협의 또는 firecrawl 스텔스 경로 검토.

### Amazon US
- **PA-API 경로**: 코드는 이미 구현됨(`backend/app/scrapers/us/amazon.py`
  `parse_paapi_response`, ASIN 필드 직접 추출까지 완료 — 2026-08-19
  `platform_product_ids` 작업 중 구현). 단 **`AMAZON_ACCESS_KEY`/`AMAZON_SECRET_KEY`
  가 프로덕션 `.env`에 비어 있어 미사용 상태**(이건 어소시에이트 태그
  `AMAZON_PARTNER_TAG`와는 별개 키 — 태그는 2026-08-19 설정 완료, PA-API
  키는 아직).
- **HTML 폴백 경로**: 여전히 봇 차단 위험 있음(구현은 돼 있으나 신뢰도
  낮음, `confidence=0.8`로 낮춰서 처리 중).
- 해결: Amazon PA-API 정식 신청(제휴 계정 승인 + 일정 매출 실적 요구되는
  경우 있음) 후 키 발급.

### Rakuten
정상 작동. `RAKUTEN_AFFILIATE_ID` 설정 완료, `platform_product_ids`
(2026-08-19) 이후 itemCode 기록도 시작. 단 itemCode는 셀러종속이라
신규상품 자동확정 판단에는 미사용(설계 v5 §3-2 참고).

### 소셜 수집기(Instagram/Facebook/TikTok/Naver 블로그) — 4개 전부 자격증명 없음
`app/social/*.py` 4개 수집기 코드는 전부 존재하지만, 2026-08-19 확인 결과
프로덕션 `.env`에 관련 토큰/키가 **전부 비어 있어** 전 기간 산출 0건이었다
(코드 버그 아님 — 방어적 조기 리턴). 상세 원인·소스별 재개 조건은
`docs/PRD-2026-08-07.md` US-006 절 참고(Naver는 결제수단 대기, Instagram/
TikTok은 사업자등록 필요).

---

## 성능

### 검색 응답 지연
Celery 비동기 태스크(`collect_fast`/`collect_on_demand`, `app/scrapers/collector.py`)
로 이미 전환됨 — 5월 당시 "동기 블로킹" 문제는 해소. 다만 최초 검색 시
수집 자체는 여전히 수 초~수십 초 걸릴 수 있음(플랫폼 수만큼 병렬 스크래핑,
`asyncio.gather` 사용).

### 프론트 번들 크기
`npm run build` 시 690KB+ 단일 JS 청크 경고(vite). 기능엔 영향 없음.
코드스플리팅(`dynamic import()`)은 아직 미적용 — 우선순위 낮은 기술부채.

---

## AI 파이프라인

`app/ai/`에 `extractor.py`/`classifier.py`/`matcher.py`/`matching.py`/
`pipeline.py`/`translator.py`/`local_client.py` 전부 구현 완료(5월 당시
"matcher.py 미구현" 기록은 낡음). Claude API(`claude-sonnet-4-6`, 프롬프트
캐싱) 기본, `USE_LOCAL_AI=true`로 Ollama 로컬 전환 가능. **정기 루프에서
LLM 호출 금지 원칙**(2026-08-09 크레딧 전소 사고 이후 확정, PRD §7)이
전 파이프라인에 적용돼 있음 — 새 AI 호출 추가 시 반드시 유인 트리거+재시도
상한+명시적 실패 상태 전이 요건을 지킬 것.

---

## 데이터 정합성

### SaleEvent 중복 방지
5월판 "미구현" 기록은 낡음 — `collector.py`의 `persist_events_for_product`가
`pg_insert(SaleEvent).on_conflict_do_nothing()`으로 이미 처리 중.

### platform_product_ids (2026-08-19 신설)
Shopify/Rakuten/Amazon 세 소스의 외부 식별자를 저장해 이름 매칭보다 먼저
빠른 조회를 시도하는 테이블. 설계·구현 히스토리는
`docs/design-platform-product-ids-2026-08-09.md`(v5) 및 관련 감사 문서
(`docs/audit-platform-product-ids-*.md`) 참고.
