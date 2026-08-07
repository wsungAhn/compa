# 제휴 네트워크 조사 — 26개 브랜드 공홈 (2026-08-07)

> `backend/app/scrapers/brands/shopify.py`의 `BRANDS`(26개) 전수 웹조사. 확인 안 된
> 항목은 "확인 안됨"으로 명시(추측 아님). `docs/PRD-2026-08-07.md` US-001 이후
> 제휴 우선 확장 논의의 근거 자료.

## 브랜드별 제휴 네트워크

| # | 브랜드 | 제휴 여부 | 채널/네트워크 | 커미션(확인분만) | 신청 링크/근거 |
|---|--------|-----------|----------------|-------------------|----------------|
| 1 | SK-II | 있음 | CJ Affiliate / ShareASale / Rakuten Advertising (서드파티, 구체 매칭 불명) | 확인 안됨 | — |
| 2 | Tatcha | 있음 | CJ Affiliate / ShareASale / Rakuten Advertising (서드파티, 구체 매칭 불명) | 확인 안됨 | — |
| 3 | La Prairie | 확인 안됨 | 확인 안됨 | — | — |
| 4 | Glossier | 있음 | **Shopify Collabs**("Generation Glossier") | 확인 안됨 | glossier.com/pages/affiliates-terms |
| 5 | Laneige | 있음 | **ShareASale** | 2.4~10%(출처 상이), 7일 쿠키 | us.laneige.com/pages/affiliate(직접 접속 404, 존재는 간접 확인) |
| 6 | Sulwhasoo | 있음(추정) | Rakuten Advertising(LinkShare) 추정 — 1차 소스 미확인 | 확인 안됨 | — |
| 7 | Amorepacific(본사) | 있음 | **Rakuten Advertising**(signup.linkshare.com 확인) | 비공개 CPA | us.amorepacific.com/pages/affiliates |
| 8 | innisfree | 확인 안됨 | 1차 네트워크 불명(애그리게이터만 노출) | 확인 안됨 | — |
| 9 | Beauty of Joseon | 있음 | **Shopify Collabs**(Affiliate+Collabs+Ambassador 병행) | 확인 안됨 | beautyofjoseon.com/pages/collabs |
| 10 | COSRX | 있음 | 자체 "COSRX Affiliate Club"(TikTok Shop 연동) | 15% | cosrx.com/pages/cosrx-affiliate-club |
| 11 | Sunday Riley | 있음 | 기타 애그리게이터 — Audenticity | 12%, 30일 쿠키 | audenticity.com/retailers/sunday-riley |
| 12 | Tata Harper | 있음(추정) | 1차 네트워크 불명 | 4%(출처 상이) | tataharperskincare.com/pages/refer(고객추천용일 수 있음) |
| 13 | 111SKIN | 있음(추정) | **Awin**(UK만 확인, US 연결 불확실) | 5~10% | ui.awin.com merchant-profile(UK) |
| 14 | Herbivore Botanicals | 있음 | **Impact.com**(공식 확인) | 4% | herbivorebotanicals.com/pages/affiliates |
| 15 | OSEA | 있음 | 기타 — Refersion(자체 SaaS) | 16~20%(판매량 티어), 30일 쿠키 | oseamalibu.refersion.com |
| 16 | Summer Fridays | 있음(추정) | 확인 안됨(자체 신청폼, 네트워크명 비노출) | 확인 안됨 | — |
| 17 | Nécessaire | 있음(추정) | 확인 안됨 | 확인 안됨 | — |
| 18 | Westman Atelier | 있음 | **CJ Affiliate** | 5% | signup.cj.com |
| 19 | Victoria Beckham Beauty | 있음(추정) | 확인 안됨 | 확인 안됨 | — |
| 20 | ILIA | 있음 | **Impact.com**(공식 확인) | 10%(일부 10~20%+보너스), 30일 쿠키 | iliabeauty.com/pages/affiliates |
| 21 | Kosas | 있음 | **Impact.com** | 10% | Impact Radius 대시보드 확인 |
| 22 | MERIT | 있음 | 확인 안됨(자체 인플루언서 폼) | 10%, 30일 쿠키 | — |
| 23 | Rare Beauty | 있음 | 기타 — 비공개 초청제(Impact Private/Dash Hudson/Grin) | 7% | 공개 신청 링크 없음 |
| 24 | Saie | 있음(추정) | **Awin** 추정(확증 약함) | 10%(자체 언급) | ui.awin.com/merchant-profile-terms/93017 |
| 25 | Natasha Denona | 있음 | **Impact.com**(공식 캠페인 페이지) | 확인 안됨 | app.impact.com/campaign-promo-signup/Natasha-Denona-Makeup-(US) |
| 26 | Pat McGrath Labs | 있음(추정) | 확인 안됨(애그리게이터만) | 5~10%(또는 6.4%, 출처 상이) | — |

## 네트워크 커버리지 요약 (가입 우선순위)

확실히 확인된 것만 집계(추정·불확실 제외):

| 네트워크 | 확인된 브랜드 수 | 브랜드 |
|---|---|---|
| **Impact.com** | 4개(+Rare Beauty는 비공개 Impact Private로 별도 취급) | Herbivore, ILIA, Kosas, Natasha Denona |
| Shopify Collabs | 2개 | Glossier, Beauty of Joseon |
| CJ Affiliate | 1개(+SK-II·Tatcha "가능") | Westman Atelier |
| Rakuten Advertising | 1개(+Amorepacific 계열 Sulwhasoo/innisfree 추정 포함 시 최대 3~4개, +SK-II·Tatcha "가능") | Amorepacific(본사) |
| ShareASale | 1개(+SK-II·Tatcha "가능") | Laneige |
| Awin | 0~2개(둘 다 확증 약함) | 111SKIN(추정), Saie(추정) |

**결론**: **Impact.com이 확인된 것만으로 4개 브랜드를 커버해 단일 네트워크 최다
매칭.** 다만 SK-II·Tatcha는 CJ/ShareASale/Rakuten 셋 다 후보라, "Impact.com 하나"
vs "CJ 또는 Rakuten 또는 ShareASale 중 하나(+SK-II·Tatcha 커버 가능성)" 구도로
저울질하면 된다. 확인 안 된 8개(La Prairie, innisfree, Tata Harper, Summer
Fridays, Nécessaire, Victoria Beckham Beauty, MERIT, Pat McGrath Labs)는
공식 사이트 직접 확인이나 브랜드 문의가 필요.

**주의**: Refersion(OSEA)·Audenticity(Sunday Riley)·TikTok Shop 자체 프로그램
(COSRX)은 "네트워크"가 아니라 브랜드 전용 SaaS/플랫폼이라 가입 창구가 다르다 —
Impact.com 같은 데 가입한다고 이 셋이 같이 열리지 않는다.
