# astro-gallery-cat

Sergey's astrophotography gallery: a static **Hugo** site (Tailwind CSS 4), trilingual **EN / IT / RU** (EN is the default language). Published on GitHub Pages (`baseURL` https://sleepytelescope.com/); pushing to `main` triggers the deploy (`.github/workflows/hugo.yaml`).

## Pinned versions
Hugo 0.168.0 (extended), Node 24. Match them locally.

## Structure
- `content/dso/{nebulas,galaxies,clusters}/<slug>/`, `content/sso/<body>/<slug>/` (jupiter, mars, moon, sun, saturn, venus, uranus, neptune, comets) and `content/australia/<slug>/` (Swan Reach remote rig, flat); `content/latest` lists recent pages by `date`.
- A new top-level section needs: `_index` in 3 languages with a cover PNG, a nav link in `layouts/_default/baseof.html`, `nav_<name>` in the 3 `i18n` files, and its name in the section list of `layouts/index.html`.
- Each image is a page bundle: `index.md` (EN), `index.it.md`, `index.ru.md` plus the PNG.
- `layouts/` (`_default/{baseof,list,single,terms}.html`, `latest/`, `partials/`, `robots.txt`), `i18n/{en,it,ru}.toml`.
- Taxonomies: `categories` and `equipment` (equipment names become taxonomy pages, so they must match existing ones exactly). A term page folder under `content/equipment/` keeps the name's special characters (e.g. the apostrophe in `gar's-…`); without them Hugo does not bind the content to the term and builds two pages on one URL.
- `scripts/r2-*.mjs`: upload/sync to Cloudflare R2 (needs `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` in the environment; never write them to files).
- Traffic stats: Cloudflare Web Analytics (JS beacon, token from CI secret `CLOUDFLARE_ANALYTICS_TOKEN`). Read them via the GraphQL API `https://api.cloudflare.com/client/v4/graphql` with the user token in the user env var `CF_ANALYTICS_TOKEN` (only permission: Account Analytics Read; verify at `/user/tokens/verify`, not the account endpoint) and `accountTag` = `R2_ACCOUNT_ID`. Dataset `rumPageloadEventsAdaptiveGroups` (`count` = page views, `sum.visits`; filter `datetime_geq`/`datetime_lt`, `bot: 0`); siteTag `69e65220167846e0bbc1bfef1e2368ae` covers both sleepytelescope.com and shakhdinarov.com.
- Google Search Console API (scope `webmasters.readonly`, Google Cloud project `sleepytelescope-analytics`, OAuth app "In production", Desktop client): user env vars `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, `GSC_REFRESH_TOKEN`; exchange the refresh token at `https://oauth2.googleapis.com/token`, then `POST https://searchconsole.googleapis.com/webmasters/v3/sites/sc-domain%3Asleepytelescope.com/searchAnalytics/query` (`startDate`, `endDate`, `dimensions`). Data lags ~3 days. The API has no Page indexing report, only per-URL inspection. The refresh token dies if unused for 6 months; recreate it with `python scripts/gsc-auth.py`.
- `python scripts/stats.py [--days 7] [--top 10]` prints both (Cloudflare and Search Console) in one report.

## Images and video
- PNGs are **not committed** (`content/**/*.png` is git-ignored). They live in R2 and CI fetches them before building. Upload to R2 *before* pushing.
- Videos/time-lapses are served directly from R2 (`videoBaseURL` in `hugo.toml`, keys under `videos/`) and are never synced into `content/`.
- Two buckets: `astro-site` (private originals, `R2_BUCKET`) and `media-sleepytelescope-com` (public via media.sleepytelescope.com, `videos/`, `social/` and `full/` only; `mediaBucket` in `scripts/r2-client.mjs`).
- `full/` holds the full-size JPEGs the fullscreen viewer loads when zooming (DSO, Australia, comets wider than 2400 px): `scripts/full-images.py` builds them and `data/full_images.json`, `scripts/r2-upload-full.mjs` uploads them.
- To add or edit an image page use the project skill `add-image` (`.claude/skills/add-image/SKILL.md`).

## Rules
- Every image taken from Italy lists `NEQ6 Pro` in `equipment` without asking. Exception: the Swan Reach remote rig (Paramount ME, no NEQ6 Pro); see the skill.
- Do not guess exposure figures; `total_exposure` is the sum of the filter integrations.
- Dates in front matter are `YYYY-MM-DD`.
- Every factual claim in a body text (distance, size, discoverer, year, magnitude, classification) must be checked against a source (Wikipedia plus ESO/NASA/ESA, SIMBAD or the literature) before it goes on the site. Where sources disagree, say so or give a range; never state it from memory. The Russian place name for Swan Reach is `Суон-Рич` (no official transcription exists; confirmed by the user).
- Local cleanup after test builds: delete `public/` only. **Never delete `resources/_gen`** (image-processing cache, very slow to regenerate).
- Uploading to R2, committing and pushing need the user's confirmation first. Commit messages in English, short, imperative.
- Curation: execute literal instructions; do not ask about edge cases the user did not mention.
