# compa 브랜드 아이덴티티 v1 (CP-001)

- 작성: 2026-09-23 PDT, Claude Opus 5.5, session=d0afc251 (mac-studio)
- 방법: `~/agent_hub/refs/compa-branding-prompt-chain.md` 8단계 체인 1→8 순차 실행. 앞 단계 결론을 다음 단계 입력으로 넘김.
- 입력 (Woosung 확정 2026-09-23):
  - **타깃**: 럭셔리 뷰티 애호가이면서 가격에 민감한 층. 럭셔리 감도는 원하고, 정가 구매는 망설이지만 거부하지는 않는다.
  - **느낌**: 미니멀 + 프리미엄
- 고정 입력 (레포에서): 럭셔리 화장품 세일 알리미 — 공식 세일 기간·할인율 알림, 다음 할인 시점 예측, 한·미·일·중 4개국 가격 이력 → "지금 살지 / 기다릴지". 수익 = 광고 + 인앱 구독 + 제휴(affiliate).

## Acceptance Rubric (작성 전 고정)

| 차원 | 5점 기준 |
|---|---|
| R1 타깃 적합성 | "망설이지만 거부하지 않는 럭셔리 애호가"에게 맞고, 딜/쿠폰 사이트처럼 보이지 않는다 |
| R2 미니멀+프리미엄 일관성 | 1~8단계 산출물 전부가 같은 톤. 장식·과시·긴급성 표현이 없다 |
| R3 실행가능성 | HEX·폰트(상업 사용 가능 라이선스)·Tailwind 토큰·이미지 프롬프트가 바로 쓸 수 있는 수준 |
| R4 차별화 | "일반 럭셔리 브랜드 복제"가 아니라 compa 고유의 핵심(타이밍)이 시각·언어 양쪽에 박혀 있다 |
| R5 내부 일관성 | 7단계 비평이 실제로 8단계와 최종안을 바꾼다 (형식적 비평 아님) |

게이트: 모든 차원 3점 이상 + 평균 3.5 이상. 채점은 별도 컨텍스트에서.

**채점 이력**: R1(Sonnet 별도 컨텍스트, 2026-09-23) — 4/4/3/4/3, 평균 3.6 PASS. 감점 5건(§4 최종 로고 불일치 · 제휴 이해상충 미처리 · 대비값 근거 · Clay 이중 액센트 · "최저가" 딜 문법) 전부 반영.

---

## 0. 핵심 한 줄 (전 단계 공통 축)

> **럭셔리엔 때가 있다.** compa는 싸게 사는 법이 아니라, **살 만한 때**를 알려준다.

이 타깃은 할인만 쫓는 사람이 아닙니다. 정가를 낼 수도 있지만 "지금 사면 손해 아닐까"에서 멈추는 사람입니다. 그래서 compa가 파는 건 할인율이 아니라 **확신**입니다: "지금 사도 됩니다" 또는 "3주만 기다리세요". 딜 사이트는 긴급함을 팔고, compa는 **차분함**을 팝니다. 이 대비가 모든 시각·언어 결정의 기준입니다.

이름 해석: **compa = compass(나침반)**. 사야 할 때를 가리키는 바늘. compare(비교)는 기능이고, compass는 약속입니다. 로고의 중심 모티프를 여기서 가져옵니다.

---

## 1. 브랜드 아이덴티티 설계

**브랜드 성격 5가지**
1. **안목** — 좋은 것을 알아보고, 과장하지 않는다
2. **차분한 확신** — 데이터로 말하고, 서두르게 만들지 않는다
3. **정직** — 기다리는 게 낫다면 "기다리세요"라고 말한다 (광고 수익보다 신뢰)
4. **절제** — 필요한 정보만. 한 화면에 결론 하나
5. **다정한 전문가** — 판단은 단호하게, 말투는 부드럽게

**말투**
- 짧은 평서문. 느낌표·"대박"·"역대급"·카운트다운 금지
- 결론 먼저, 근거는 한 줄: "지금 사도 좋습니다. 이 브랜드는 다음 세일까지 두 달 넘게 남았어요."
- 기다리라고 할 때도 이유와 시점을 같이: "기다리세요. 이 브랜드는 보통 11월 셋째 주에 20% 할인합니다."
- 영어: calm, precise, lowercase 친화. 예) *"Worth it — now."* / *"Wait. It usually drops in November."*

**미션**
좋은 것을 사랑하는 사람이 후회 없이 살 수 있도록, 가장 좋은 때를 알려준다.

**포지셔닝**
- 누구에게: 럭셔리 뷰티를 좋아하지만 정가 앞에서 한 번 멈추는 사람
- 무엇을: 4개국 3년 가격 이력과 브랜드별 세일 패턴으로 "지금 / 기다림"을 판단해 주는 알리미
- 경쟁 대비: 딜 앱은 "지금 싸다"를 외치고, 브랜드 앱은 "지금 사라"만 말한다. compa만 **"아직 아니에요"**라고 말할 수 있다.

**태그라인 3개**
1. **럭셔리엔 때가 있다.** / *Luxury has its moment.* ← 메인 추천
2. 살 만한 때를 아는 사람. / *Know when.*
3. 서두르지 않아도 됩니다. / *No rush. We'll tell you.*

**피해야 할 비주얼**
빨간 할인 태그, 큰 % 숫자, 폭발형 버스트·별 모양, 카운트다운 타이머, 점선 쿠폰, 네온·형광, 빽빽한 상품 그리드, 금박 텍스처 남용, 필기체·캘리그래피, 과한 그라데이션, 3D 광택 아이콘

**로고가 전달해야 할 메시지**
"때를 가리킨다." 시계나 나침반 바늘 같은 **하나의 정확한 가리킴**. 요란함이 아니라 정밀함.

**연상 단어 5개**
순간(moment), 가리킴(needle), 여백(space), 확신(assurance), 의식(ritual)

**로고 방향성**
소문자 워드마크 `compa`를 중심에 둔다. 글자 `o`를 다이얼로 바꾸고 안에 헤어라인 바늘 하나를 넣는다. 단독 심볼은 모노그램 `c`(열린 원호 + 바늘 한 점). 색은 잉크 단색이 기본이고, 액센트 색은 "지금" 신호에만 쓴다.

---

## 2. 로고 콘셉트 10개

입력: 산업 = 럭셔리 뷰티 가격 타이밍 서비스 / 성격 = 모던·럭셔리 / 핵심 메시지 = "때를 가리킨다" / 선호 스타일 = 워드마크 + 모노그램 / 색 = 잉크 + 아이보리

| # | 이름 | 심볼 아이디어 | 폰트 스타일 | 색 | 장점 | 추천 사용처 |
|---|---|---|---|---|---|---|
| 1 | **Dial-o** | 워드마크의 `o` = 다이얼, 1시 방향 헤어라인 바늘 | 넓은 자간의 지오메트릭 소문자 산세리프 | 잉크 단색 | 이름과 컨셉이 한 번에 읽힘 | 메인 로고, 웹 헤더 |
| 2 | Arc-c | 원의 3/4 원호로 만든 `c`, 틈이 "열린 창(세일 윈도우)" | 모노그램 단독 | 잉크 / 아이보리 반전 | 앱 아이콘에서 강함 | 앱 아이콘, 파비콘 |
| 3 | Needle | 워드마크 위 가는 수직선 하나(바늘) | 하이콘트라스트 세리프 | 잉크 + 액센트 한 점 | 극단적 절제 | 인쇄, 패키지 스티커 |
| 4 | Hourmark | `a` 뒤에 작은 시계 눈금 하나 | 휴머니스트 산세리프 | 잉크 | 은근한 위트 | SNS 프로필 |
| 5 | Window | 얇은 사각 테두리 안의 워드마크, 한 변만 열림 | 모던 세리프 | 잉크 | 편집 디자인 느낌 | 뉴스레터 헤더 |
| 6 | North | `c` 안에 나침반 북쪽 삼각형 하나 | 모노그램 | 잉크 + 액센트 | 나침반 은유가 명확 | 온보딩, 마케팅 |
| 7 | Tide | 워드마크 아래 완만한 가격 곡선 헤어라인, 최저점에 점 하나 | 지오메트릭 산세리프 | 잉크 + 액센트 점 | 서비스 기능을 직접 암시 | 랜딩 히어로 |
| 8 | Seal | 원형 엠블럼, 테두리 텍스트 "at the right moment" | 세리프 대문자 | 잉크 | 럭셔리 부티크 인장 느낌 | 인쇄물, 굿즈 |
| 9 | Split | `com·pa` 사이 중점 하나 = 순간 | 모노라인 산세리프 | 잉크 | 가장 단순함 | 텍스트 전용 환경 |
| 10 | Bracket | `(compa)` 괄호로 감싼 워드마크 | 모노스페이스 | 잉크 | 테크 느낌 | (비추천 — 럭셔리 톤과 거리) |

1차 선별: **#1 Dial-o**(메인) + **#2 Arc-c**(심볼). #6, #7은 컨셉이 겹치는 보조 후보로 3·6단계에서 흡수.

---

## 3. 미니멀 럭셔리 로고 방향 7가지

입력: 분위기 = 우아함 · 타임리스 · 모던 / 참고 브랜드 = Aesop(절제된 편집 톤), Le Labo(타자기풍 라벨의 정직함), Byredo(여백과 소문자), Tatcha(동양적 차분함 — 4개국 서비스와 맞음)

| # | 방향 | 스타일 / 심볼 | 폰트 | 컬러 | 레이아웃 | 고급스러워 보이는 이유 |
|---|---|---|---|---|---|---|
| A | **Quiet Dial** | 소문자 워드마크, `o` 다이얼 + 헤어라인 바늘 | 지오메트릭 산세리프(Jost 계열), 자간 +8% | 잉크 on 아이보리 | 가로 1행, 넓은 여백 | 장식 없이 정밀한 디테일 하나 — 시계 브랜드 문법 |
| B | Editorial Serif | 소문자 하이콘트라스트 세리프, 심볼 없음 | Fraunces(SOFT 0) | 잉크 | 중앙 정렬, 잡지 마스트헤드 | 인쇄 매체 권위 |
| C | Label Honesty | 타자기풍 라벨 박스 안의 `compa / est. 2026` | 모노스페이스 + 세리프 | 잉크 on 크라프트 | 라벨형 | Le Labo식 "숨길 게 없음" |
| D | Stone Monogram | `c` 원호 단독, 스톤 컬러 | 모노그램 | 웜스톤 | 심볼 단독 | 조약돌 같은 촉감적 절제 |
| E | Hairline Frame | 얇은 괘선 프레임 + 워드마크 | 모던 세리프 | 잉크 | 좌상단 정렬 | 갤러리 캡션 느낌 |
| F | Moment Dot | 워드마크 끝의 액센트 점 하나(= 지금) | 지오메트릭 산세리프 | 잉크 + 딥 올리브 점 | 가로 1행 | 색을 단 한 점에만 써서 가치가 생김 |
| G | Duo | A의 워드마크 + D의 모노그램을 세로 락업 | A와 동일 | 잉크 | 세로 스택 | 시스템으로서의 완성도 |

**선택: A(Quiet Dial) + F의 액센트 점 규칙 + G의 락업 체계.** B는 제목용 서체로 흡수(5단계).

A 방향 AI 이미지 프롬프트 (8단계에서 확장):
`minimalist lowercase wordmark "compa", geometric sans serif, generous letter spacing, the letter o drawn as a thin watch dial with a single hairline needle pointing to one o'clock, ink black on warm ivory, flat vector, no gradients, lots of negative space`

---

## 4. 전체 비주얼 방향성

입력: 브랜드 가치 = 안목·정직·차분한 확신 / 느낌 = 미니멀 + 프리미엄 / 상품 = 모바일 앱 + 웹 + 알림 + 뉴스레터

**로고 스타일**: **Notch-o 워드마크 + Arc-c 모노그램(틈 60°, 크기별 두 벌)** — 7단계 비평으로 확정된 최종안. (초기 Quiet Dial 바늘안은 작은 크기에서 사라져 기각)

**컬러 팔레트** (최종 — 근거는 5단계)
| 역할 | 이름 | HEX |
|---|---|---|
| 배경 | Paper | `#F7F4EF` |
| 표면 | Linen | `#EDE8E0` |
| 본문·로고 | Ink | `#1E1D1B` |
| 보조 텍스트·"기다림" | Stone | `#8A8378` |
| 액센트·"지금" 신호 | Moss | `#3E5646` |
| 상태: 가격 상승 경고 (아이콘·라벨 전용, 액센트 아님) | Clay | `#A5634D` |

**폰트**: 로고 = Jost 기반 커스텀 조정 / 제목 = Fraunces / 본문·UI = Inter + Pretendard(한국어) + Noto Sans JP·SC(일·중) (5단계 참조)

**아이콘**: 1.25px 모노라인, 둥근 끝, 24px 그리드. 채움 아이콘은 쓰지 않음. 신호는 점(●) 하나로.

**사진 스타일**: 자연광, 낮은 채도, 제품 하나 + 넓은 여백. 대리석·린넨·돌 같은 무채색 소재. 손·피부 클로즈업은 허용하되 얼굴은 드물게. 할인 합성, 가격 스티커 합성 금지.

**SNS 스타일**
- 피드: 제품 한 컷 + 한 줄 판정("지금 · 기다려도 더 내려갈 가능성 낮음") — "최저가" 서열 표현 금지. compa는 가격 순위가 아니라 **타이밍 판단**을 말한다 — 판정 카드는 Paper 배경, Ink 텍스트, Moss 점 하나
- 스토리: "이번 주 기다려야 할 브랜드 3" 같은 **기다림 콘텐츠**가 차별화 무기 (딜 계정은 절대 못 하는 말)
- 중국(샤오홍슈)·일본용도 같은 템플릿, 언어만 교체

**웹사이트 스타일**: 한 화면에 결론 하나. 제품 검색 → 큰 판정("지금" / "기다림 — 11월 셋째 주 예상") → 아래에 3년 가격 곡선(헤어라인, 최저점 Moss 점). 카드 그리드 대신 넓은 리스트.

**패키지 방향** (물리 상품이 없으므로 = 앱 아이콘·알림·이메일):
- 앱 아이콘: Ink 배경 + 아이보리 Arc-c
- 푸시 알림: "라 메르 크림 · 지금 사도 좋습니다" — 이모지·느낌표 없음
- 이메일: 타자기풍 라벨 헤더(3단계 C 흡수), 본문 한 줄 결론

**Do 5**
1. 결론을 먼저, 한 줄로
2. 여백을 기능으로 취급 (정보 밀도보다 판단 명료성)
3. 액센트 색(Moss)은 "지금" 신호에만. Clay는 경고 **상태** 색이며 아이콘·작은 라벨에만 쓴다 — 한 화면에 Moss와 Clay를 동시에 강조하지 않는다
4. "기다리세요"를 당당하게 말하기
5. 4개 언어에서 같은 레이아웃·같은 톤

**Don't 5**
1. 할인율 숫자를 가장 크게 쓰지 않는다
2. 긴급성 장치(타이머, "마감 임박") 금지
3. 금박·광택·그라데이션 금지
4. 상품을 빽빽하게 늘어놓지 않는다
5. 브랜드 로고를 compa 로고보다 요란하게 두지 않는다 (큐레이터는 조용해야 함)

---

## 5. 컬러 팔레트와 폰트

**후보 팔레트 3가지**

| 팔레트 | 구성 (HEX) | 의미 | 판정 |
|---|---|---|---|
| ① Paper & Moss | `#F7F4EF` `#EDE8E0` `#1E1D1B` `#8A8378` `#3E5646` | 종이의 차분함 + 이끼색 = 조용한 "진행" 신호 | **채택** |
| ② Porcelain & Rose | `#FAF7F5` `#1F1C1C` `#C9A9A0` `#8E5E57` | 뷰티 업계 표준 핑크 누드 | 기각 — 흔하고 여성 소비자 고정관념에 기댐, 차별화 약함 |
| ③ Noir & Brass | `#111111` `#F2EFE9` `#B08D57` | 블랙 + 황동 | 기각 — 과시적 럭셔리, "정직한 조언자"보다 "명품 매장" |

**각 색의 의미 (채택안)**
- Paper `#F7F4EF`: 흰색보다 따뜻한 여백. 종이 = 기록·이력
- Linen `#EDE8E0`: 카드·구획용 두 번째 표면
- Ink `#1E1D1B`: 순흑 대신 살짝 따뜻한 잉크. 판단의 무게
- Stone `#8A8378`: 보조 정보 + "기다림" 상태. 돌 = 인내
- Moss `#3E5646`: "지금" 신호. 신호등 초록이 아니라 낮은 채도의 이끼색이라 재촉하지 않음
- Clay `#A5634D`: 가격 상승 경고 전용. 빨강 대신 흙색

**대비 확인 (WCAG 2.x, 계산값 — 상대휘도 공식 `(L1+0.05)/(L2+0.05)`, sRGB 선형화 임계 0.03928, Python으로 2026-09-23 계산)**: Paper 배경 기준 Ink 15.35:1 · Moss 7.29:1(AA 본문 통과) · Clay 4.26:1 · Stone 3.42:1. Linen 배경에선 각각 13.81 · 6.56 · 3.83 · 3.08.
→ **Stone·Clay는 본문 금지** (AA 4.5 미달). 18px 이상 큰 글자·아이콘·보조 라벨에만 쓴다(AA Large 3:1은 통과).

**폰트** (전부 SIL Open Font License — 앱·웹·상업 사용 가능)
| 용도 | 폰트 | 설정 |
|---|---|---|
| 로고 | **Jost** 기반 (Futura 계열 지오메트릭) | 소문자, 자간 +8%, `o` 다이얼 커스텀 |
| 제목 | **Fraunces** | 가변축 SOFT 0 · WONK 0, weight 400~500 (장식 억제) |
| 본문·UI (라틴) | **Inter** | 400/500, 숫자는 tabular-nums (가격 정렬) |
| 한국어 | **Pretendard** | Inter와 메트릭 호환 |
| 일본어 / 중국어 | **Noto Sans JP / Noto Sans SC** | 본문 전용, 제목도 동일 계열로 통일 |

**좋은 조합**: Fraunces 제목 + Inter 본문 (편집적 권위 + UI 가독성) / 가격 숫자는 Inter tabular

**피할 조합**: 세리프 두 개 동시 사용 · Fraunces를 본문에 · Jost를 긴 문장에 · CJK에 세리프 제목 혼용 (4개 언어 톤이 갈라짐)

**Tailwind v4 토큰** (`frontend/src/index.css`에 그대로 적용 가능)
```css
@theme {
  --color-paper: #F7F4EF;
  --color-linen: #EDE8E0;
  --color-ink: #1E1D1B;
  --color-stone: #8A8378;
  --color-moss: #3E5646;
  --color-clay: #A5634D;
  --font-display: "Fraunces", Georgia, serif;
  --font-sans: "Inter", "Pretendard", "Noto Sans JP", "Noto Sans SC", system-ui, sans-serif;
}
```

---

## 6. 모노그램 로고 10개

입력: 이니셜 = `c` (보조: `cp`) / 분위기 = 럭셔리·모던 / 사용처 = 앱 아이콘·파비콘·SNS 프로필·이메일 서명

| # | 결합 방식 / 형태 | 폰트 | 의미 | 색 | 느낌 |
|---|---|---|---|---|---|
| M1 | **Arc-c**: 원의 270° 원호, 열린 틈 1시 방향 | 모노라인 | 열린 틈 = 세일 윈도우, 1시 = 바늘 위치 | Ink / 반전 | 정밀·조용 |
| M2 | Arc-c + 틈 끝에 Moss 점 | 모노라인 | 창이 열리는 "지금" | Ink + Moss | 신호가 있는 정밀함 |
| M3 | `c` 안의 헤어라인 바늘 | 모노라인 | 다이얼 | Ink | 시계 |
| M4 | `c`와 `p`의 세로 획 공유 | 지오메트릭 | 비교(compare) | Ink | 구조적 |
| M5 | `c` 두 개가 겹침 (4개국 비교) | 모노라인 | 여러 시장 | Ink | 다소 복잡 |
| M6 | 원형 인장 안의 소문자 `c` | 세리프 | 부티크 인장 | Ink | 클래식 |
| M7 | 정사각 안 `c`, 모서리 하나 열림 | 지오메트릭 | 창 | Ink | 모던 |
| M8 | `c` 끝이 나침반 북침 삼각형 | 모노라인 | compass | Ink + Moss | 은유 직접적 |
| M9 | 세리프 `c`의 볼 터미널 = 점 | Fraunces | 순간 | Ink | 편집적 |
| M10 | 가격 곡선이 `c`를 그림 | 헤어라인 | 가격 이력 | Ink | 설명적 |

AI 이미지 프롬프트 (M1·M2 — 1순위):
- M1: `monogram logo, a single lowercase c drawn as a 270 degree thin circular arc, gap opening at the one o'clock position, uniform hairline stroke, ink black on warm ivory, flat vector, centered, generous margin, no text, no gradient`
- M2: 위와 동일 + `a small solid moss green dot (#3E5646) at the end of the arc where the gap begins`

---

## 7. 로고 비평 (엄격 모드)

평가 대상: **Quiet Dial 워드마크**(`compa`, `o` = 다이얼 + 1시 방향 헤어라인 바늘) + **Arc-c 모노그램**(M1/M2)

| 항목 | 평가 |
|---|---|
| 기억성 | 중상. 다이얼 `o`는 기억에 남지만, 헤어라인 바늘은 **작게 보면 사라진다** |
| 독창성 | 중. 시계 은유 워드마크는 선례가 있다. 가격 타이밍 서비스라는 **맥락**이 차별점이지 형태 자체는 아니다 |
| 타깃 적합성 | 상. 딜 사이트 문법이 전혀 없고, 시계 브랜드 문법은 이 타깃이 "좋은 물건"과 연결하는 언어 |
| 흑백 사용성 | 상. 단색 설계라 문제없음. M2의 Moss 점은 흑백에서 검은 점으로 남아 의미가 흐려지지만 형태는 유지 |
| 작은 크기 사용성 | **하 — 핵심 결함.** 16px 파비콘·앱 아이콘에서 헤어라인 바늘은 1px 미만. Arc-c 원호도 헤어라인이면 뭉개짐 |
| 전문성 | 상. 절제된 구성 |

**제거할 요소**
- 워드마크 다이얼 안의 **눈금 표시**(초기 구상에 있던 12개 눈금) — 전부 제거, 바늘만 남김
- M2의 점을 **파비콘 크기에서는 제거** (작은 크기에선 형태가 먼저)

**개선할 점**
1. **크기별 두 벌 운용**: 32px 이상은 헤어라인, 32px 미만은 굵은 획(선 두께 = 글자 획의 60%) 버전을 따로 둔다
2. 바늘을 선이 아니라 **다이얼 외곽에서 안쪽으로 파인 쐐기(노치)**로 바꾼다 — 작은 크기에서도 음각으로 살아남음
3. Arc-c의 틈 각도를 1시 방향(30°)에서 **2시 방향(60°)으로 넓혀** 작은 크기에서 `o`와 구분되게

**더 나은 대안 3가지**
1. **Notch-o** (채택): `o` 외곽 1시 방향에 작은 쐐기 홈. 바늘 대신 "여기"를 표시. 모든 크기에서 동작
2. **Moment Dot**: 워드마크는 순수 타이포, 끝에 Moss 점 하나만 — 가장 단순하지만 compass 은유를 잃음
3. **Arc-c Bold**: 모노그램을 굵은 원호 + 넓은 틈으로 — 앱 아이콘 전용

**비평 반영 결과 (최종안 변경)**
- 워드마크: Quiet Dial → **Notch-o** (바늘 제거, 쐐기 홈)
- 모노그램: M1 → **Arc-c, 틈 60°, 크기별 두 벌**
- Moss 점: 32px 이상에서만 사용

---

## 8. AI 로고 이미지 프롬프트 10개 (비평 반영본)

공통 조건: flat vector, 배경 = warm ivory `#F7F4EF` 또는 투명, 잉크 `#1E1D1B`. 피할 요소 공통: `no gradient, no gold foil, no 3D, no glossy, no shadow, no percentage sign, no price tag, no sparkles, no script font, no mockup`

| # | 로고 타입 | 프롬프트 |
|---|---|---|
| P1 | 워드마크 (최종안) | `minimalist lowercase wordmark "compa", geometric sans serif similar to Futura, letter spacing slightly wide, the letter o has a small wedge-shaped notch cut into its outer edge at the one o'clock position, ink black #1E1D1B on warm ivory #F7F4EF, flat vector logo, centered, large negative space` + 공통 피할 요소 |
| P2 | 모노그램 (최종안, 대형) | `monogram logo, lowercase c formed by a thin circular arc of 300 degrees, 60 degree gap opening toward two o'clock, a tiny solid moss green dot #3E5646 at the upper end of the arc, ink black on warm ivory, flat vector, centered` + 공통 |
| P3 | 모노그램 (소형·앱 아이콘) | `app icon, rounded square filled with ink black #1E1D1B, bold lowercase c formed by a thick circular arc with a wide 60 degree gap toward two o'clock, warm ivory color, no dot, flat, highly legible at 16 pixels` + 공통 |
| P4 | 세로 락업 | `vertical logo lockup, bold arc c monogram above lowercase wordmark "compa" in geometric sans serif, ink on ivory, balanced spacing, flat vector` + 공통 |
| P5 | 가로 락업 | `horizontal logo lockup, small arc c monogram left of lowercase "compa" wordmark, aligned to x-height, ink on ivory, flat vector, minimal` + 공통 |
| P6 | 반전 | P1과 동일, `warm ivory #F7F4EF logo on ink black #1E1D1B background` |
| P7 | 제품 컨텍스트 목업 | `a luxury skincare jar on a warm ivory linen surface, soft natural window light, beside it a small printed card showing the lowercase "compa" wordmark with a notched o, muted colors, editorial product photography, lots of empty space` (목업이 목적이므로 공통 피할 요소에서 `no mockup` 제외) |
| P8 | SNS 판정 카드 | `social media square card, warm ivory background, small "compa" wordmark top left, large calm serif text "Worth it — now.", a single tiny moss green dot, a thin hairline price curve at the bottom with its lowest point marked, minimal editorial layout` + 공통 |
| P9 | "기다림" 카드 | P8과 동일, 텍스트 `"Wait. It usually drops in November."`, 점 색상 warm stone `#8A8378` |
| P10 | 흑백 테스트 | P1 + P2 나란히, `pure black on pure white, no color, logo sheet showing sizes 256px, 64px, 16px` + 공통 |

주의: 이미지 모델은 글자 철자를 틀리는 경우가 많다. P1·P4·P5의 워드마크는 **최종본을 벡터로 직접 그리는 것이 원칙**이고, 이미지 생성은 방향 확인용 레퍼런스로만 쓴다.

---

## 정직성 원칙과 제휴 수익의 충돌 (✅ 확정 2026-09-23, Woosung)

"기다리세요"라고 말하는 브랜드가 "지금 사세요" 클릭에서 제휴 수수료를 받으면 이해상충이 생긴다. 이 브랜드의 핵심 자산은 신뢰라서, 이걸 명시적으로 처리하지 않으면 컨셉 전체가 무너진다.

**방침 (아래 1~4 그대로 확정)**
1. 판정이 **"기다림"이면 구매 링크를 노출하지 않는다.** 대신 "세일 시작 시 알림 받기" 버튼만.
2. 판정 로직은 제휴 수수료율을 입력으로 쓰지 않는다 (판정 ↔ 수익 분리).
3. 구매 링크 옆에 제휴 고지를 항상 표시한다 (이미 Amazon 어소시에이트 고지 있음, `c1c5eca`).
4. 이 방침 자체를 브랜드 메시지로 쓴다: "기다리라고 할 때는 링크를 걸지 않습니다."

**수익 모델 방향 (Woosung, 2026-09-23)**
- 제휴(affiliate)는 **최종 단계에서 아예 안 걸 수도 있다.** 걸더라도 위 1~4를 지킨다.
- 대신 유료(구독) 기능 후보:
  1. **광고 제거**
  2. **분석 기간 차등** — 예: 무료 1년 / 유료 3년 가격 이력
  3. **검색 기반 권장 상품 안내** — 수수료가 없으므로 이해상충 없이 "지금 사기 좋은 것"을 추천 가능
  4. **세일 시작 알림**
- 브랜드와의 정합: 무료 사용자도 **판정 자체("기다림 — 11월 셋째 주 예상")는 본다.** 유료는 그 순간을 놓치지 않게 **알려주는** 것. "정직한 판단은 무료, 편의는 유료"로 나누면 정직성 원칙이 수익 구조와 부딪히지 않는다.
- 따라서 1번 방침의 "세일 시작 알림 받기" 버튼은 무료 사용자에겐 구독 유도 지점이 된다 — 판정 문구를 가리거나 흐리게 하는 방식의 유도는 금지.

## 다음 단계 (이 문서 범위 밖)

1. P1~P3로 레퍼런스 이미지 생성 → Woosung 선택
2. 선택안 벡터화 (Figma 등) → `frontend/public/` 로고·파비콘 세트
3. `frontend/src/index.css`에 5단계 토큰 적용 → 기존 화면 톤 교체 (STATUS.md 중간목표 ⑥ "아름다운 디자인")
4. 레지스트리(`~/agent_hub/pm/project_registry.json`) compa 설명 "비교 분석 도구" → 실제 목적으로 정정
