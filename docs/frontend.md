# 프론트엔드 아키텍처

React 19 · TypeScript · Vite · Tailwind CSS v4 · Recharts

---

## 컴포넌트 구조

```
src/
├── App.tsx                  # 검색 → 결과 레이아웃, max-w-5xl
├── api/
│   └── client.ts            # searchProducts(q, collect), getProductEvents
├── components/
│   ├── SearchBar.tsx        # 검색창 + 자동완성
│   ├── SiteEventsGrid.tsx   # 플랫폼별 그리드 컨테이너
│   ├── SiteTimeline.tsx     # 플랫폼 카드 + Recharts 타임라인
│   ├── WaitBuyWidget.tsx    # 지금살지/기다릴지 추천 위젯
│   ├── PriceComparison.tsx  # 플랫폼 간 현재가 비교
│   ├── EventCard.tsx        # 개별 할인 이벤트 카드 (레거시)
│   └── SiteManager.tsx      # 플랫폼 노출 설정 (useSitePrefs)
└── hooks/
    └── useSitePrefs.ts      # localStorage 기반 플랫폼 필터
```

---

## SearchBar 동작 방식

```
사용자 타이핑 (debounce 300ms)
  → searchProducts(q, collect=false)   # DB only, 스크래퍼 미실행
  → 결과 없으면 "Enter를 눌러 검색" 힌트 표시

Enter 키 입력
  → searchProducts(q, collect=true)    # 실시간 스크래퍼 수집
  → "수집 중... (30초 정도 소요됩니다)" 메시지 표시
```

---

## SiteTimeline 카드 구성

각 플랫폼당 카드 하나. 그리드로 반응형 배치.

```
┌─────────────────────────────────┐
│ 🇰🇷 네이버쇼핑     ₩32,000  [구매] │  ← 헤더: 국기 + 플랫폼명 + 현재가 + 링크
│ ★ 최저가                         │  ← 최저가 뱃지 (통화별 그룹 내)
│ [Recharts AreaChart stepAfter]  │  ← 3년치 할인율 타임라인
│  0%──────△────────────────── 0% │
│         15%                      │
└─────────────────────────────────┘
```

**타임라인 데이터 변환 (`buildChartData`):**
- SaleEvent 배열 → 3년 전부터 오늘까지의 ChartPoint[]
- 할인 시작일: `discount = rate`, 종료일+1: `discount = 0` (stepAfter 보간)
- 진행 중인 이벤트는 종료 포인트 없음 (오늘까지 할인율 유지)

**주의사항:**
- `gradientId = grad-${platformName.replace(/\s+/g, '-')}` — ID 충돌 방지 필수
- `rel="noopener"` (noreferrer X) — Referer 헤더 유지로 쇼핑몰 403 방지
- `isAnimationActive={false}` — 성능 최적화

---

## 반응형 그리드

```css
/* index.css */
.platform-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
```

플랫폼 수에 따라 자동으로 컬럼 수 조정. 별도 breakpoint 설정 불필요.

---

## 구매 링크 정책

쇼핑몰은 Referer 헤더가 없으면 403 반환.
- ✅ `rel="noopener"` — 새 탭 보안 유지, Referer 헤더 전달
- ❌ `rel="noopener noreferrer"` — Referer 제거 → 403
