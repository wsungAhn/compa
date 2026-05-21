# 알려진 기술 제약 및 해결 방향

## 환경

### Playwright + Ubuntu 26.04
번들 Chromium이 Ubuntu 26.04-x64를 지원하지 않음.
Google Chrome을 직접 설치하여 사용:
```bash
# 설치 (root 권한)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install ./google-chrome-stable_current_amd64.deb -y
# 경로: /usr/bin/google-chrome-stable
```
모든 Playwright 스크래퍼에 적용 필요:
```python
browser = await pw.chromium.launch(
    headless=True,
    executable_path="/usr/bin/google-chrome-stable",
    args=["--no-sandbox", "--disable-dev-shm-usage"],
)
```

---

## 차단된 스크래퍼

### 올리브영 / 쿠팡 (403)
강력한 봇 차단. httpx와 Playwright 모두 차단됨.
현재는 에러 graceful handling으로 결과 없이 통과.
해결: 공식 파트너 API 협의 또는 서비스에서 제외.

### Amazon US (503)
강력한 봇 차단.
해결: Amazon Product Advertising API 연동 필요 (affiliate 계정 + PA API 신청).

---

## 성능

### 검색 응답 지연 (30~40초)
첫 검색 시 Playwright 수집이 동기적으로 실행됨.
현재: 검색 API가 수집 완료까지 블로킹.
해결: Celery 비동기 태스크로 전환. 기존 제품은 즉시 반환, 수집은 백그라운드 실행.

---

## AI 파이프라인

### Gemma via Ollama 미구현
원안에서는 정형 데이터 분류에 Gemma 4 2B (로컬) 사용 예정이었으나,
WSL 환경 설치 복잡도로 인해 Rule-based 분류기 + Claude API 폴백으로 대체.
소셜 비정형 데이터에만 Claude API 사용 중.

---

## 미구현 기능

| 기능 | 원안 위치 | 현황 |
|------|----------|------|
| matcher.py | `app/ai/` | 미구현 — deep-translator로 임시 대체 |
| Celery 태스크 | `app/tasks/` | 폴더만 존재, 코드 없음 |
| @cosme 스크래퍼 | `app/scrapers/jp/` | 미구현 |
| Ulta 스크래퍼 | `app/scrapers/us/` | 미구현 |
| 중국 스크래퍼 | `app/scrapers/cn/` | 미구현 |
| 소셜 수집 | `app/social/` | 미구현 |
| GitHub Actions CI/CD | `.github/` | 미구현 |
| 테스트 코드 | `backend/tests/` | 구조만 존재 |
| SaleEvent 중복 제거 | `app/scrapers/collector.py` `_save_events()` | 24h마다 동일 할인 정보 재수집 시 중복 레코드 누적. platform_id + product_id + start_date + event_name 조합으로 upsert 필요 |
