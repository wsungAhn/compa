# Site readiness for affiliate review (2026-09-23)

Tier 1. Impact.com rejected the publisher application with no stated reason
("can't partner at this time"). The live site (`compa.mwco.io`) shows signs a
reviewer reads as "under construction". Fix those before the next application.

## Observed (2026-09-23, live site)
- `<title>frontend-new</title>` (Vite template default), `lang="en"` on a Korean UI.
- Home is mostly an `AdSlot` placeholder box ("광고 영역 [home]"). No ad network is wired.
- `/privacy`, `/about`, `/terms`, `/contact` all return the same SPA shell — no such pages.

## 선행조사
- Repo: `App.tsx` routes, `components/` listing, grep for footer/privacy — nothing existing
  beyond the Amazon disclosure footer in `HomePage.tsx`.
- External: affiliate networks (Impact, CJ, Amazon Associates) commonly require a
  privacy policy, an about/contact path and real content on publisher sites. Convention,
  no library needed.
- Conclusion: new static pages, no dependency.

## Change
1. Delete `AdSlot` and its two usages (no ad network exists; re-add with a real one).
2. `index.html`: `lang="ko"`, real title + meta description from brand v1 core line.
3. New `routes/InfoPages.tsx`: About (incl. contact), Privacy, Terms. KO + EN.
   Privacy content is limited to facts verified in code: search logs (query, result
   count, time), optional feedback contact, IP in access logs and in-memory rate limit,
   localStorage premium key, Cloudflare, Google Fonts, Amazon affiliate links. No analytics.
4. `components/SiteFooter.tsx`: disclosure + links, used by Home and info pages.

## Verify
`npm run build && npm run lint`, render the pages from a scratch build, then deploy
(`npm run build` into `dist` is live immediately).
