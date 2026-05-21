# DB 스키마

## products

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | UUID PK | |
| name_kr | VARCHAR | 유저 검색 쿼리가 정규 제품명으로 저장 |
| name_en / name_jp / name_cn | VARCHAR | |
| brand | VARCHAR | |
| category | ENUM(base/color/functional) | |
| created_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ | 소프트 삭제 |

## platforms

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | UUID PK | |
| name | VARCHAR | |
| country | CHAR(2) | KR/US/JP/CN |
| url | VARCHAR | |
| scrape_method | ENUM(scraping/official_api/unofficial_api) | |

## sale_events

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | UUID PK | |
| product_id | UUID FK | INDEX |
| platform_id | UUID FK | INDEX |
| event_name | VARCHAR | |
| event_type | ENUM(regular/surprise) | |
| start_date / end_date | DATE | INDEX(start_date) |
| original_price / sale_price | NUMERIC(12,2) | |
| discount_rate | NUMERIC(5,2) | |
| currency | CHAR(3) | KRW/USD/JPY/CNY |
| scraped_name | TEXT | 플랫폼에서의 실제 상품명 |
| is_bundle | BOOLEAN | 기획세트/번들 여부 |
| confidence | FLOAT | 0~1, 0.7 미만 → needs_review=True |
| needs_review | BOOLEAN | |
| raw_text | TEXT | 파싱 실패 시에도 보존 |
| source_url | TEXT | |
| created_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ | 소프트 삭제 |

## social_posts

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | UUID PK | |
| platform | ENUM(instagram/tiktok/facebook/naver_blog/...) | |
| post_url | TEXT | |
| content | TEXT | |
| posted_at | TIMESTAMPTZ | |
| processed | BOOLEAN | AI 처리 완료 여부 |
| sale_event_id | UUID FK NULL | 연결된 행사 |
| created_at | TIMESTAMPTZ | |

## 마이그레이션 이력

| 파일 | 내용 |
|------|------|
| `9f41a20f9a7e_initial_schema.py` | 초기 4개 테이블 생성 |
| `4618dbf54f38_add_scraped_name_and_is_bundle_to_sale_.py` | sale_events에 scraped_name, is_bundle 추가 |
