# Codex Handoff — 2026-09-23 (compa logo SVGs)

> **상태(Status):** `대기중 / pending`
>
> **시작 기록(Started by):** _(empty — executor stamps `session=<id> machine=<tag> started=<ISO8601>`)_
>
> **작성자(Author):** Claude Opus 5.5 (spec & review) → **수행자(Executor):** Codex gpt-5.6-luna (low)
> **작업명(Task):** Draw the three final compa logos as clean SVG, then wire the wordmark and favicon into the site.
> **설계 근거(Design basis):** `docs/brand/brand-identity-2026-09-23.md` (sections 4, 5, 7, 8). The user picked these
> references on 2026-09-23: wordmark `docs/brand/logo-refs/p1-a.png`, monogram `docs/brand/logo-refs/r2/m4.png`,
> app icon `docs/brand/logo-refs/r2/a1.png`. Look at all three PNGs before drawing.
> **범위(Scope):** IN: new files under `frontend/public/brand/`, a generator script
> `docs/brand/logo-svg/build.py`, `frontend/index.html` favicon links, the header wordmark in
> `frontend/src/routes/HomePage.tsx`. OUT: any other UI, backend, logic, `frontend/dist`.

---

## 0. Rules (executor, read first)
- The user wants GPT to draw the logos. **You** produce the geometry (in code). Do not trace or embed the PNGs.
- Do not commit. Do not run `npm run build` into `frontend/dist` (it is live). Use
  `npx vite build --outDir /tmp/compa-logo-dist --emptyOutDir` for checks.
- Checks: `cd frontend && npx tsc -b && npm run lint && npm run test` (baseline 13/13 pass).
- If unsure, stop and write the question in §8.

## 1. Shared geometry (the system rule)
- **One angle for everything: 1 o'clock = 30° clockwise from 12 o'clock.** In SVG coordinates
  (y down), that direction is the unit vector (sin 30°, −cos 30°) = (0.5, −0.866).
- Colors, exact: ink `#1E1D1B`, paper `#F7F4EF`, moss `#3E5646`. No gradients, strokes-with-effects, filters or shadows.
- Output real `<path>` geometry (no `<text>`, no external fonts). Each SVG has a `viewBox`, no fixed px width/height, and a `<title>`.
- Write ONE script, `docs/brand/logo-svg/build.py` (python3, stdlib + fontTools, which is installed for the
  system `python3`), that generates every SVG. Parameters (stroke width, gap angle, radii) are named
  constants at the top so a human can retune them. Re-running it must reproduce the files byte-for-byte.

## 2. Wordmark — `frontend/public/brand/compa-wordmark.svg`
- Font: **Jost** (SIL OFL). Download `https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf`
  into `docs/brand/logo-svg/` (commit-able, with `OFL.txt` from the same folder). Use weight 400 (instantiate the
  variable font at wght=400 with `fontTools.varLib.instancer`).
- Text "compa", all lowercase, tracking +8% of the em (see brand doc 5단계), glyph outlines converted to paths.
- The **o** gets a small wedge-shaped notch cut into its OUTER edge at 1 o'clock, as in `p1-a.png`: the wedge
  apex points at the o's center, opening angle about 30°, depth about 45% of the o's stroke thickness (constants).
  Do the cut as geometry (e.g. a boolean subtract via a clip/mask-free path: draw the o ring as two circles/ellipses
  from the glyph bbox if that is simpler, but the result must look like the Jost o). Everything ink.
- Tight viewBox around the ink with ~4% padding.

## 3. Monogram — `frontend/public/brand/compa-monogram.svg` (from m4)
- A lowercase **c** made of a single circular arc, ink, uniform stroke, **flat (butt) ends**. The gap is
  **centered exactly on 1 o'clock**, gap width 60° (so the arc spans 300°). Stroke width about 12% of the diameter.
- One solid **moss** dot centered in the gap, on the arc's center-line radius, diameter ≈ 1.4× the stroke width.
- Draw the arc as a filled path (outer arc, butt end, inner arc, butt end), not as a stroked path.
- Square viewBox, centered, ~8% padding.

## 4. App icon — `frontend/public/brand/compa-app-icon.svg` (from a1)
- Rounded square filled ink `#1E1D1B`, corner radius 22% of the side (iOS-like).
- A **thick** paper-colored c arc: gap **centered on 1 o'clock**, gap width 60°, stroke ≈ 22% of the icon side,
  **ends cut along the radial line** (this is what gives a1 its angled look). No dot.
- Must read at 16 px. Keep the c's outer diameter ≈ 62% of the side.
- Also export raster copies with the same script (use `rsvg-convert` if present, else cairosvg if importable,
  else skip rasters and say so in §8): `frontend/public/brand/icon-32.png`, `icon-180.png` (apple-touch), `icon-512.png`.

## 5. Favicon
- `frontend/public/favicon.svg` becomes the monogram (m4) on transparent background. Keep the path `/favicon.svg`.
- `frontend/index.html`: keep the existing `<link rel="icon" type="image/svg+xml" href="/favicon.svg">`, add
  `<link rel="apple-touch-icon" href="/brand/icon-180.png">` if the PNG exists.

## 6. Header wordmark
- `frontend/src/routes/HomePage.tsx:68` currently renders `<h1 className="text-lg font-medium tracking-wide text-ink">compa</h1>`.
  Replace the text with `<img src="/brand/compa-wordmark.svg" alt="compa" className="h-6 w-auto" />` inside the same `<h1>`
  (keep the h1 for semantics; move the text classes off). Nothing else in the header changes.

## 7. Done criteria
- [ ] 3 SVGs + favicon + script (+ rasters or a stated reason) exist; script reruns reproduce them.
- [ ] Visual check: open each SVG (e.g. render to PNG) and compare with its reference PNG; describe any deliberate difference.
- [ ] Angle check in §8: print the computed gap-center angle for monogram and app icon (must be 30.0°) and the notch angle.
- [ ] tsc, lint, tests 13/13, scratch build OK.
- [ ] Did NOT commit.

### Acceptance rubric (fixed before execution)
| Dimension | What 5 means | Gate |
|---|---|---|
| Fidelity | Each SVG clearly reads as its chosen reference (p1-a / m4 / a1) | 4+ |
| System consistency | All three openings at exactly 30°; exact brand hex colors | 5 |
| Craft | Real paths, clean viewBox, no text/fonts/filters; legible at 16 px (icon) and 24 px height (wordmark) | 4+ |
| Scope | Only the listed files touched; header change is the one-line swap | 5 |

## 8. Executor response (executor writes here)
### 8-1. Files
_(write here)_
### 8-2. Angle/size numbers
_(write here)_
### 8-3. Checks
_(write here)_
### 8-4. Deviations / questions
_(write here)_
### 8-5. Rubric self-score (deductions first)
_(write here)_

## 9. Review log (reviewer)
_(reviewer writes here)_
