# Luxury brand coverage (2026-09-23)

User request: "럭셔리 브랜드 다 넣어줘". It came after the user searched "프레쉬" and got a
product with "관측 이력 0일(1건)".

## 선행조사
- **레포 내 검색:** `backend/app/scrapers/brands/shopify.py:BRANDS` (26 Shopify brands),
  `app/scrapers/catalog.py:seed_catalog` (brand catalog → `products`, cap 100/brand),
  `app/core/seed.py` (platform rows derived from `BRANDS` at API startup),
  `app/tasks/collect.py:_collect_all` (daily sweep **updates existing products only** —
  unmatched groups are skipped), `app/scrapers/brand_dictionary.py` (deal-detection aliases).
  No retailer brand-catalog sweep exists.
- **외부 선행작업:** Shopify storefront `/products.json` (public, the pattern this repo already
  uses). Probed 2026-09-23 with curl + the repo's own scraper class:
  - Open (200, parses, USD): Clinique, Chantecaille, Augustinus Bader (`/en-us`), Omorovicza,
    Erno Laszlo, Royal Fern, Tom Ford Beauty, Hourglass, Laura Mercier, Dermalogica, Rodial,
    Susanne Kaufmann, Kjaer Weis, Vintner's Daughter, Dr. Loretta, Makeup by Mario, Danessa
    Myricks, Violette_FR, Anastasia Beverly Hills, Rhode, Glow Recipe, Supergoop!, Oribe.
  - Closed (403/404/410 or non-Shopify): La Mer, Estée Lauder, Lancôme, Shiseido,
    Clé de Peau, Sisley, Guerlain, Dior, Chanel, Dr. Barbara Sturm, Fresh, Drunk Elephant,
    Kiehl's, Natura Bissé, Valmont, Charlotte Tilbury, YSL, Armani, Givenchy, Hermès, NARS,
    Bobbi Brown, Byredo, Aesop, Diptyque (fr-fr only), Jo Malone, Peter Thomas Roth,
    Dr. Dennis Gross, Dr. Jart+, Kérastase, Sulwhasoo KR, Hera.
- **결론:** Layer A reuses the registry as is (a data-only change). Closed brands need a new
  retailer path → Layer B, separate design.

## Root cause found on the way
Seeding runs only when `products` is empty (`seed_catalog_if_empty`). Brands added after the
first seed on 08-05 were never catalog-seeded, and the daily sweep does not create products.
Measured 2026-09-23: Saie has 3 products of 63 in its catalog, Natasha Denona 2 of 124,
Rare Beauty 2, Nécessaire 3.

## Layer A (this change)
1. Add the 23 open brands to `BRANDS`, and the 17 missing aliases to `BRAND_ALIASES`
   (the test requires aliases > 2 × brands).
2. Ops, one time: `seed_platforms` + `seed_catalog(all registry brands)`, then restart the
   worker so the 03:00 sweep sees the new registry.

## Layer B (next design, not done here)
- Make catalog seeding recurring. The sweep should add new catalog items and not just update.
  Watch the interaction with `cleanup_empty_orphan_products` (it soft-deletes products with
  no events after 24h).
- Retailer brand-catalog sweep for the closed houses (Sephora brand pages / other retailers).
- `MAX_PER_BRAND=100` and first-page-only `products.json` (250) truncate Clinique and Tom Ford.

## Observation-window fix (2026-09-23, user decision)
`history_days` now runs from the first observation to the request time, not to the last
observation. Measured: 275 of 4,184 products (collection gaps) showed a shorter history than
they really had. A shallow history now says "YYYY-MM-DD부터 관측 중(N건)" instead of "0일",
and the API exposes `observed_since`. This does not create past data. Products first seen
today are still day 0. Historical backfill (e.g. Wayback snapshots) is a Layer B candidate.
