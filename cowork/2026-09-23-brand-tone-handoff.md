# Codex Handoff — 2026-09-23 (brand tone, visual layer 1)

> **상태(Status):** `대기중 / pending`
> _(Executor: set `진행중 / in-progress` on start, `검토대기 / review-pending` when done.
>  Only the author/reviewer sets `완료 / done`, after the commit.)_
>
> **시작 기록(Started by):** _(empty — the first party to start work stamps
> `session=<id> machine=<tag> started=<ISO8601>` here)_
>
> **작성자(Author):** Claude Opus 5.5 (design & review) → **수행자(Executor):** Codex gpt-5.6-luna (low)
> **작업명(Task):** Apply the compa brand tokens (color, type, surfaces) to every public screen.
> **설계 근거(Design basis):** `docs/design-brand-tone-2026-09-23.md` (read it) and
> `docs/brand/brand-identity-2026-09-23.md` sections 4–5 (the values).
> **범위(Scope):** IN: `frontend/index.html`, `frontend/src/index.css`, delete
> `frontend/src/App.css`, and restyle `routes/HomePage.tsx`, `routes/DealFeedPage.tsx` +
> `DealFeedPage.css`, `routes/InfoPages.tsx`, and every file in `src/components/`. Also the
> font-family names only in `routes/CoveragePage.css` and `routes/AdminMatchesPage.css`.
> OUT: any behavior/logic/state/API change, admin page layout/colors, backend, logo/favicon
> files, `CONTACT_EMAIL` value, the verdict-first layout, hiding buy links.

---

## 0. How to use this document (Executor, read first)

You have none of this project's context. Trust only what's below.

- **Do NOT:** change any logic, props, state, hooks, API calls, routes or text meaning ·
  touch `backend/` · run `npm run build` into the real `dist` — see below · edit `.env` ·
  add npm dependencies · commit.
- **Always:** after each task run the checks in "Execution environment" and confirm they
  pass. Record your work in §8. Flip the status line when you start and finish.
- **If unsure:** don't guess. Stop and leave the question in §8-6.

### Execution environment
- Working directory: `/Users/Mung/dev/compa-worktrees/brand-tone` (git worktree, branch
  `feat/brand-tone`). `frontend/node_modules` is a symlink to main's. Leave it.
- Typecheck + lint: `cd frontend && npx tsc -b && npm run lint`
- Build (**scratch outDir only**, the real `dist` belongs to main):
  `cd frontend && npx vite build --outDir /tmp/compa-brand-dist --emptyOutDir`
- Tests: `cd frontend && npm run test`. **Current baseline: 13 tests, 13 pass.**
  Fewer passes is a regression.
- Backend is untouched, so no backend tests are needed.

---

## 1. Background

compa is a luxury-beauty sale-timing site ("buy now or wait"). A brand identity was
finalized (`docs/brand/brand-identity-2026-09-23.md`): warm paper background, ink text,
one moss accent for "now", Fraunces headings, Inter/Pretendard body, hairlines instead of
shadows, and no emoji, gradients or urgency. The live UI still uses Tailwind defaults:
gray/amber/rose/blue, emoji, gradients, Space Grotesk. An affiliate network also rejected
the site partly because it looked unfinished. This handoff makes the site look like the
brand. It does not change how anything works.

---

## 2. Task A — Tokens and fonts (do first)

### Diagnosis
- `frontend/src/index.css` is only `@import "tailwindcss";` + `.platform-grid`. No tokens.
- `frontend/index.html:8-9` loads Space Grotesk + Instrument Sans from Google Fonts.
- `frontend/src/App.css` (184 lines) is imported nowhere (`grep -rn "App.css" src` = 0).

### How to fix
1. In `index.css`, after the import, add the brand `@theme` block **verbatim**:
   ```css
   @theme {
     --color-paper: #F7F4EF;
     --color-linen: #EDE8E0;
     --color-ink: #1E1D1B;
     --color-stone: #8A8378;
     --color-moss: #3E5646;
     --color-clay: #A5634D;
     --font-display: "Fraunces", Georgia, serif;
     --font-sans: "Inter", "Pretendard Variable", "Pretendard", "Noto Sans JP", "Noto Sans SC", system-ui, sans-serif;
   }
   ```
   Add a base rule: `body` uses the Paper background, Ink color and `var(--font-sans)`.
   Keep `.platform-grid`.
2. In `index.html`, replace the Space Grotesk/Instrument `<link>` with:
   - Google Fonts: Fraunces (opsz axis, weights 400–500) + Inter (400, 500), `display=swap`.
   - Pretendard: `<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">`
   - Keep the `preconnect`, the `impact-site-verification` meta, title and description as they are.
3. `git rm frontend/src/App.css`.
4. In `CoveragePage.css`, `AdminMatchesPage.css` and `DealFeedPage.css`, replace
   `'Space Grotesk', sans-serif` with `var(--font-display)` and `'Instrument Sans', sans-serif`
   with `var(--font-sans)`. In the admin CSS files, change **nothing else**.

## 3. Task B — Restyle public screens

Files: `routes/HomePage.tsx`, `routes/DealFeedPage.tsx`, `routes/DealFeedPage.css`,
`routes/InfoPages.tsx`, `components/*.tsx` (SearchBar, WaitBuyWidget, PriceComparison,
SiteEventsGrid, EventTimeline, EventCard, SiteTimeline, PriceChart, SiteManager,
FeedbackButton, PremiumBanner, SiteFooter).

### Mapping rules (apply consistently)
| Current | Replace with |
|---|---|
| page `bg-gray-50` | `bg-paper` |
| `bg-white` cards/panels, `shadow*` | `bg-paper` or `bg-linen`, `border border-ink/10`, **no shadow** |
| `rounded-2xl` / `rounded-xl` | `rounded-md` at most |
| `text-gray-800/900/700` | `text-ink` |
| `text-gray-400/500/600` small text (<18px) | `text-ink/70` (AA-safe; **never `text-stone` for small text**) |
| `border-gray-*` | `border-ink/10` |
| gray placeholder/skeleton `bg-gray-200` | `bg-linen` |
| amber/rose/pink/orange/emerald/blue/indigo/purple **accents** | "now / buy / primary action / selected" → `moss`; "wait" → `stone` (dot or ≥18px text only); **price-rise warning label only** → `clay`; anything else → ink / ink/70 |
| `bg-gradient-*`, `from-*`, `to-*` | remove (flat `bg-linen`) |
| `font-bold` / `font-semibold` | `font-medium` |
| h1/h2/h3 headings | add `font-display font-normal` (Fraunces) |
| prices, %, counts, D-day numbers | add `tabular-nums` |
| emoji (💄 🔍 ✨ ⏳ 🛒 ✅ 🔄 💬 ⚙️ etc.) in UI | delete. For a verdict signal use a `●` span colored moss/stone. For spinners use a small CSS spinner (`animate-spin` on a bordered circle) or plain text |

Rule: on one screen, never emphasize both moss and clay at once.

### Specific points
- **Header (`HomePage.tsx` ~line 66):** replace `💄` + `COMPA` with a lowercase text
  wordmark `compa` (`font-sans font-medium tracking-wide text-ink`). It is interim; a logo
  SVG replaces it later. Keep the tagline and the buttons. Header background `bg-paper`
  with a bottom `border-ink/10`, no shadow.
- **`WaitBuyWidget.tsx`:** keep `VERDICT_CONFIG` keys and labels. Drop emoji. `buy_now` →
  moss dot + label in moss. `wait` → stone dot + label in ink. `good_deal` → ink dot +
  label in ink. The verdict label is the **largest** text in the widget
  (`font-display text-2xl`). The expected-discount `-N%` must be **no larger** than the
  D-day number and must not be moss or clay: use `text-ink`, `text-lg`, `tabular-nums`.
- **`PriceChart.tsx:23`:** replace the rainbow `COLORS` with series styles that cycle
  stroke colors `['#1E1D1B', '#3E5646', '#8A8378']` and dash patterns `['', '6 4', '2 3']`
  (color index = i % 3, dash index = floor(i / 3) % 3). `strokeWidth` 1.25, dots r=2 in
  the series color. Grid stroke `#EDE8E0` (Linen), axis stroke and ticks
  `rgba(30,29,27,0.7)`. Keep all data logic untouched.
- **`PremiumBanner.tsx`:** remove the gradient and ✨. Use a flat `bg-linen`,
  `border-ink/10` panel. Primary button in moss (`bg-moss text-paper`). Logic unchanged.
- **`DealFeedPage.css`:** replace its hard-coded colors with the token variables
  (`var(--color-paper)`, `var(--color-ink)`, etc.) following the same mapping. Remove
  shadows and gradients.
- **`InfoPages.tsx` / `SiteFooter.tsx`:** apply the mapping (gray → ink / ink/70, page bg
  paper, h1/h2 `font-display font-normal`). In `PrivacyPage`, the "Third parties" list
  currently says "Google Fonts serves the site fonts". Add one item after it: "jsDelivr
  serves the Korean font (Pretendard) and receives your IP address." Add the matching
  words to the Korean summary sentence that mentions Google Fonts. No other text changes.
- Buttons: primary = `bg-moss text-paper`, secondary = `border border-ink/20 text-ink`.
  Focus rings `ring-moss/40`.

### Constraints
- No JSX structure change beyond swapping class names, removing emoji nodes and the
  header wordmark. No prop, state or handler changes.
- Keep every Korean/English text string except the emoji characters and the two privacy
  additions above.

### Required checks
- No new test files are needed (pure styling). Existing tests must stay at 13/13.
- Run this guard. It must print nothing:
  ```bash
  cd frontend && grep -rnE '(amber|rose|pink|orange|emerald|indigo|purple|blue)-[0-9]|gradient|shadow|Space Grotesk|Instrument Sans|💄|🔍|✨|⏳|🛒|✅|🔄' \
    src/routes/HomePage.tsx src/routes/DealFeedPage.tsx src/routes/DealFeedPage.css src/routes/InfoPages.tsx src/components/*.tsx src/index.css index.html
  ```
  If something it flags is truly needed, keep it and explain why in §8-4.

---

## 5. Coding principles
- TypeScript strict stays on. No `any`. No new dependencies.
- Tailwind v4 utilities from the tokens (`bg-paper`, `text-ink/70`, `font-display`, ...).
  No inline `style={{}}` for colors, except in Recharts props, which need hex/rgba.
- Delete code that becomes unused (for example color constants). Don't leave it commented out.
- Do not commit. The reviewer commits.

## 6. Done criteria
- [ ] Task A: tokens, fonts, App.css deleted, CSS font names swapped
- [ ] Task B: all listed public files restyled per mapping
- [ ] `npx tsc -b && npm run lint` clean
- [ ] Scratch build succeeds (`--outDir /tmp/compa-brand-dist`)
- [ ] `npm run test`: 13/13
- [ ] Guard grep prints nothing (or each hit justified in §8-4)
- [ ] Act-based check: the reviewer will render the pages in a browser. Executor: N/A allowed
- [ ] §8-7 self-score filled (deductions first)
- [ ] Did NOT commit

### Acceptance rubric (fixed before execution)
| Dimension | What 5 means | Gate |
|---|---|---|
| Token fidelity | Every color/font on public screens comes from the six tokens + two font stacks. No raw palette classes left | 4+ |
| Accessibility | No `text-stone`/`text-clay` on text under 18px. Secondary text is `ink/70` | 4+ |
| Scope discipline | Zero logic/prop/state/text changes beyond those listed. Admin CSS: only font names | 4+ |
| Brand rules | No emoji, gradients or shadows. Moss only for now/primary. Verdict label largest in the widget | 4+ |
| Build health | tsc, lint, scratch build and 13/13 tests all green | 5 |

## 7. What the executor reports (fill §8)
1 files changed · 2 new tests (expect none) · 3 test result · 4 guard grep output ·
5 N/A · 6 judgment calls · 7 rubric self-score (deductions first)

---

## 8. Executor response (executor writes here)

### 8-1. Files changed
_(write here)_

### 8-2. New tests
_(write here)_

### 8-3. Final test result
_(write here)_

### 8-4. Consistency scan / findings
_(write here)_

### 8-5. Backward-compat check
_(write here)_

### 8-6. Blocked / judgment calls
_(write here — "none" if none)_

### 8-7. Rubric self-score
_(write here)_

---

## 9. Review log (reviewer writes after verifying)

**Reviewed:** _(date)_ | **Verdict:** _(pending)_

### Verified directly
_(reviewer)_

### Notable / beyond spec
_(reviewer)_

### Follow-up
_(reviewer)_
