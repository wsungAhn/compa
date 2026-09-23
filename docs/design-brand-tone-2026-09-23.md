# Brand tone rollout — visual layer 1 (2026-09-23)

Tier 2 (10+ files). CP-001 follow-up step 3. Source of truth for every visual value:
`docs/brand/brand-identity-2026-09-23.md` sections 4 and 5. This layer changes **how things look
only**. No behavior, data or API change.

## 선행조사
- **레포 내 검색:** (grep over `frontend/src`, 2026-09-23): no design tokens exist.
  `src/index.css` is `@import "tailwindcss"` plus one grid class. Public screens use raw
  Tailwind palette classes. Top counts: `text-amber-700` 6, `text-rose-500` 5,
  `text-rose-600` 4, `text-blue-700` 4, `border-amber-200` 4, `bg-rose-50` 4. Fonts are
  Space Grotesk + Instrument Sans (Google Fonts, `index.html`), referenced by name in
  `DealFeedPage.css`, `CoveragePage.css`, `AdminMatchesPage.css`. 8 emoji in public TSX.
  `src/App.css` (184 lines, Vite template leftovers) is imported by nothing.
  `PriceChart.tsx:23` uses an 8-color rainbow array.
- **외부 선행작업:**
  - Tailwind CSS v4 `@theme` (MIT, the repo's own dependency): tokens declared in CSS
    become utilities (`bg-paper`, `text-ink`, `font-display`) and CSS variables
    (`var(--color-paper)`). Adopted as the only token mechanism. No extra config file.
  - Pretendard (github.com/orioncactus/pretendard, SIL OFL 1.1 per its README, last push 2026-07-23, latest release v1.3.9): the
    dynamic-subset variable CSS from jsDelivr. Adopted because Pretendard is not on Google
    Fonts.
  - Fraunces and Inter (Google Fonts, SIL OFL): adopted as the brand doc specifies.
- **결론:** reuse Tailwind v4 `@theme`. No new npm dependency. No component library.

## Decisions
1. Tokens: exactly the brand doc's `@theme` block. `body` is Paper background, Ink text,
   `font-sans`.
2. Contrast: Stone (3.42:1) and Clay (4.26:1) fail AA for body text on Paper. Small
   secondary text uses `text-ink/70`, which computes to 5.91:1 on Paper, 5.64:1 on Linen. Stone is only
   for text ≥18px, icons, hairlines and the "wait" dot.
3. Accent discipline: Moss marks "now/buy" signals and the primary action only. Clay is
   used only on a small label or icon for a price rise. Never use both as emphasis on one
   screen.
4. Surfaces: white cards with shadows become Paper or Linen with a 1px `border-ink/10`
   hairline. No shadows, no gradients. Radius at most `rounded-md`.
5. Type: headings use `font-display` (Fraunces) at weight 400–500. UI uses Inter/Pretendard
   400/500 and never bold. Prices and numbers use `tabular-nums`.
6. Emoji removed from public UI. Signals become a single dot (●) or plain text.
7. Chart: series strokes cycle Ink/Moss/Stone × solid/dashed/dotted, 1.25px, hairline grid
   in Linen, axis text Ink/70.
8. The verdict label is the largest text in the verdict widget. The discount % is never
   larger than it (brand Don't #1).
9. Interim header wordmark: lowercase text `compa`. The logo SVG replaces it after the
   logo pick (separate step).
10. Admin pages (`/admin/*`) stay out of scope, except their font-family names switch to
    the new variables. The old fonts stop loading, and this keeps admin pages from falling
    back to Times.
11. `App.css` is deleted as unused.

## Next layers (not this doc)
- Logo SVG + favicon (after the GPT reference pick).
- Verdict-first home layout, and hiding buy links on a "wait" verdict (brand policy 1).
  That is a behavior change and gets its own design.
