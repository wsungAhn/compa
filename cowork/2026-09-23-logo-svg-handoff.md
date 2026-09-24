# Codex Handoff — 2026-09-23 (compa logo SVGs)

> **상태(Status):** `완료 / done`
>
> **시작 기록(Started by):** `session=logo-svg-2026-09-23 machine=mingzis-Mac-Studio.local started=2026-09-23T23:52:15-07:00`
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

## 8. Executor response (round 5)
### 8-1. Files
Updated `docs/brand/logo-svg/build.py` and regenerated `compa-wordmark.svg`, `compa-monogram.svg`, `compa-app-icon.svg`, and `frontend/public/favicon.svg`. Existing scoped changes in `frontend/index.html` and `frontend/src/routes/HomePage.tsx` remain. Raster outputs were intentionally skipped.

### 8-2. Round-5 results
1. Replaced the wordmark `o` notch's even-odd construction with a real `skia-pathops` `DIFFERENCE` against the glyph outline. The glyph and wedge now share the corrected final SVG coordinate space (`translate(..., pad - min_y)`), preventing the floating wedge and descender clipping issue.
2. Result-path assertions verify reduced area, no ink at the inner notch probe, no added ink outside the outer edge, and ink retained at 210° inside the stroke. The notch angle is `30.0°`.
3. Monogram and app-icon outputs were preserved byte-for-byte from round 4: their SHA-256 hashes remain `8227cce2337b256630d0f7c2629c7ff6c54d073f491c331a7f6cd5070e454ec4` and `1c1e58b5a9db876432f9248630533648f8b943aa13289a81e2669cd11e1a0d05`.
4. Gap assertions still report `10.0°` and `50.0°`, centered at `30.0°`; the moss dot remains centered at `30.0°`.

### 8-3. Checks
`docs/brand/logo-svg/.venv/bin/python docs/brand/logo-svg/build.py` passed twice. SHA-256 checks confirmed byte-for-byte reproducibility for all four generated SVGs. `npx tsc -b` passed; `npm run lint` passed; `npm run test` passed `13/13`; `npx vite build --outDir /tmp/compa-logo-dist --emptyOutDir` passed. No raster files were created. No commit made.

### 8-4. Honest deductions
I did not perform a fresh rendered visual comparison in this round, so final raster appearance and 16px app-icon legibility remain reviewer checks. The new assertions validate the boolean result geometry and reject the prior floating sliver, but they do not replace visual review. Raster outputs remain absent.

### 8-5. Rubric self-score (deductions first)
Deductions: rendered visual comparison and raster legibility remain unverified. Fidelity `4/5` (pending visual review), System consistency `5/5`, Craft `4/5` (pending visual review), Scope `5/5`.

## 9. Review log (reviewer)

### 라운드 1
**Verdict:** changes requested

Reviewer rendered the SVGs with macOS `qlmanage -t -s 600` and put them next to the references
(`docs/brand/logo-svg/review-r1.png`: left = reference, right = output).
1. **Wordmark reads "copn", not "compa".** Hand-drawn fallback outlines are rejected. The font is now in the
   repo: `docs/brand/logo-svg/Jost[wght].ttf` + `OFL.txt` (reviewer downloaded them; your sandbox has no network).
   Use it exactly as §2 says: instancer at wght=400, real glyph outlines for c o m p a, +8% tracking, then the notch.
2. **Gap geometry is wrong on the monogram and the app icon.** Measured on the render, the moss dot sits at ~30°
   (correct), but the arc's gap runs from about −30° to about +60°: ~90° wide, centered near 15°. Required: gap
   **60° wide, centered on 30°**, i.e. the arc ends are at 0° and 60° (clockwise from 12 o'clock), and the arc
   covers the other 300°. Recheck the angle convention in code (SVG y-down: point at angle θ from 12 o'clock
   clockwise = (cx + r·sinθ, cy − r·cosθ)). Add an assertion in build.py that computes both end angles from the
   generated end points and asserts 0.0° and 60.0° (±0.1). Print them in §8.
3. Rasters: `qlmanage` (macOS built-in) works on this host: `qlmanage -t -s 512 -o <dir> file.svg` writes
   `<dir>/file.svg.png`. Use it for icon-32/180/512 (then resize/rename with PIL, which is installed). If it fails
   in your sandbox, say so. The reviewer will run it.
4. Render all three final SVGs with qlmanage and look at them before reporting. Compare against the references.
- failure_log: cb350a25 (SPEC_MISMATCH)

### 라운드 2
**Verdict:** changes requested

Reviewer render: `docs/brand/logo-svg/review-r2.png` (left = reference, right = output). Good: the wordmark is real
Jost "compa". The gap end assertion holds (0°/60°, center 30°).
1. **Notch is in the wrong place.** It shows as a small mark on the o's INNER side at about 8 o'clock. It must be
   a wedge cut into the o's OUTER edge at 1 o'clock (upper right), as in p1-a.png. Likely cause: font units are
   y-up and SVG is y-down, so the angle is mirrored and/or the wedge is anchored on the inner contour. Compute the
   notch in the final SVG coordinate space (after the y-flip and the glyph offset), and anchor the apex toward the
   o's center, with the mouth on the outer contour. Assert in build.py that the wedge centroid lies up-and-right
   of the o's center (dx > 0, dy < 0 in SVG coordinates) and outside the inner counter.
2. **Tracking is too wide** compared with p1-a. Set the extra tracking to +3% of the em (constant `TRACKING_EM = 0.03`).
   The chosen reference wins over the brand doc's +8%. The reviewer will note this deviation in the brand doc.
3. **App icon stroke too thick** (my spec error). Set the stroke to 17% of the side, keep the outer diameter at 62%.
4. **Monogram touches the viewBox edge.** Make the OUTER edge of the arc sit at 8% padding: outer diameter = 84
   in the 100 viewBox, stroke = 12% of that outer diameter, and keep the dot on the stroke's center-line radius.
5. Rasters: skip them. The reviewer generates them on the host.
- failure_log: d3b98604 (SPEC_MISMATCH)

### 라운드 3
**Verdict:** changes requested

Reviewer render: `docs/brand/logo-svg/review-r3.png` (left = reference, right = output). Tracking and the app-icon
stroke are better.
1. **Wordmark notch still wrong.** The o has NO visible notch. A small separate ink speck floats above, between c and
   o. The in-code assertions passed but the render is wrong, so the assertion checks the wrong thing. Required: the
   notch must be a REMOVAL of ink from the o ring (a wedge-shaped bite out of the ring's outer edge at 1 o'clock,
   reaching about 45% into the ring's stroke), not an added shape. Implement it as a boolean difference on the o's
   outline, e.g. by building the o ring's outer and inner contours yourself as polygons sampled from the glyph and
   subtracting the wedge polygon, OR by emitting the wedge as part of the same path with the opposite winding
   (even-odd fill) so it cuts. Add an assertion that samples points: the wedge centroid must fall in a pixel that is
   NOT ink when the path is filled (use a simple even-odd point-in-polygon test over the final path's polygons).
2. **User decision 2026-09-24: gap width 40° (option B), still centered on 1 o'clock.** Arc ends at 10° and 50°
   clockwise from 12 o'clock, arc covers 320°. Apply to BOTH monogram and app icon. Update `GAP_WIDTH = 40.0` and the
   end-angle assertion (10.0 / 50.0 ± 0.1). The moss dot stays centered at 30° on the center-line radius.
3. Rasters: skip. The reviewer makes them.
- failure_log: 5318fddb (SPEC_MISMATCH)

### 라운드 4
**Verdict:** changes requested (monogram and app icon approved; wordmark notch only)

Reviewer render `docs/brand/logo-svg/review-r4.png`: monogram and app icon are correct (gap 10°–50°). **Approved,
do not change them.** The wordmark notch wedge floats well above the o. Root cause, found by the reviewer:
1. **Y-offset mismatch.** Glyph paths are drawn with `TransformPen(pen, (1,0,0,-1,0,asc))`, so glyph y = asc − y,
   whose minimum is `min_y`. They are then placed with `translate(x, pad)` (`build.py:91`, `:116`), so the
   glyphs sit `min_y` too low. But the wedge is computed with `o_top = pad + (asc - ob3 - min_y)` (`:100`), which
   includes `−min_y`. Fix: place every glyph with `translate(offset - min_x + pad, pad - min_y)`, and use
   `ty = pad - min_y` for the wedge's local coordinates. Then glyphs and wedge share one coordinate space, and the
   viewBox `0 0 W H` also contains the glyphs (today the descender of p can be clipped).
2. **Even-odd cannot cut cleanly.** Any wedge area outside the o's ink becomes NEW ink under even-odd. Use a real
   boolean difference instead: **skia-pathops** (BSD-3) is installed in `docs/brand/logo-svg/.venv`. Run the
   script with `docs/brand/logo-svg/.venv/bin/python docs/brand/logo-svg/build.py` (fontTools is in that venv too).
   Draw the o glyph into a `pathops.Path` (via `pathops.PathPen` or by replaying the SVG/Recording pen with the same
   transform), build the wedge as a `pathops.Path` triangle whose mouth overshoots the outer contour, compute
   `pathops.op(o_path, wedge_path, pathops.PathOp.DIFFERENCE)`, and emit the result as the o's `d` (no fill-rule
   tricks). Put the venv command in the script's module docstring.
3. Replace the notch assertions with ones that check the RESULT: (a) the o's new outline has less area than the
   original (use the pathops area or a sampled even-odd point test), (b) a point at radius (outer_r − 0.2·depth) on
   the 30° ray is NOT ink, (c) the point at radius (outer_r + depth) on the same ray (outside the o) is also NOT
   ink, which proves there is no added sliver, and (d) a point at 210° inside the stroke IS ink.
4. Keep `TRACKING_EM`, the constants and everything else. Regenerate all SVGs. The monogram and app icon must be
   byte-identical to round 4 (assert it by comparing to the round-4 files before overwriting).
- failure_log: cccba33e (SPEC_MISMATCH)

### 라운드 5
**Verdict:** approved (with reviewer tuning)

- Round 5 fixed the y-offset and switched to a skia-pathops DIFFERENCE. The notch is now a real cut at 1 o'clock
  (rendered and zoomed). The monogram and app icon are byte-identical to the approved round 4.
- Reviewer tuning, constants only (the script's geometry is unchanged): the hard-coded `wght 400` and `±10°` became
  constants, and a mouth-overshoot constant fixes a hairline ink sliver along the notch chord (seen at 4× zoom).
  Values were picked from a 4-variant render against p1-a (`/tmp` sheet, summarised here): `WORDMARK_WEIGHT=450`,
  `NOTCH_DEPTH=0.75`, `NOTCH_HALF_WIDTH=14`, `NOTCH_MOUTH_OVERSHOOT=1.15`, `TRACKING_EM=0.05`
  (the brand doc says +8%; p1-a reads tighter, so the chosen reference wins).
- Rasters: made on the host with macOS `qlmanage` + PIL (Codex's sandbox cannot run qlmanage):
  `frontend/public/brand/icon-{32,180,512}.png`. The apple-touch link is in `index.html`.
- Checks (reviewer): build.py ×2 reproducible, tsc, lint, tests 13/13, scratch build OK.
- Deploy: not done. `frontend/dist` build is gated on CONTACT_EMAIL (info pages).

