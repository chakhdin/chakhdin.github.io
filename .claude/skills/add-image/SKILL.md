---
name: add-image
description: Add a new astrophoto (DSO, planet, Sun, Moon, comet; still or time-lapse video) to the Hugo gallery. Covers the page bundle, front matter, EN/IT/RU translations, R2 upload, local test and deploy. Use when the user wants to publish a new image or edit an existing image page.
---

# Add an image to the gallery

Each image is a Hugo page bundle with three language files. The PNG is **not committed**: it lives in Cloudflare R2 and CI fetches it before building. Order matters: upload to R2 *before* pushing, or the deploy builds without the image.

## 1. Gather inputs (ask only for what is missing)

- Image file (PNG) and, if relevant, the annotated version (`*.annotated.png` is the convention).
- Object name and short descriptive subtitle (e.g. "LDN 1295: The Giraffe Nebula").
- Section: `dso/nebulas`, `dso/galaxies`, `dso/clusters`, `sso/<body>` (jupiter, mars, moon, sun, saturn, venus, uranus, neptune, comets), or `australia` (Swan Reach remote rig).
- Capture nights, location and Bortle class.
- Equipment, total exposure, focal length, per-filter subs and integration.
- Processing notes (default tools: PixInsight; planets add AutoStakkert!3).

Do not guess exposure figures. Compute `total_exposure` as the sum of the filter integrations and check the arithmetic (subs x seconds).

## 2. Create the bundle

Path: `content/<section>/<slug>/` with `index.md` (EN), `index.it.md`, `index.ru.md`, plus the PNG.

- DSO slug: lowercase catalogue id, e.g. `ldn1295`, `m31-andromeda`, `sh2-114`.
- Solar-system slug: capture date, e.g. `2024-08-17`, or `YYYY-MM-DD-<designation>` for comets.
- Copy the front matter of a sibling page of the same kind (nebula, galaxy, planet) and adapt it. Do not invent new fields.

Front matter fields: `title`, `date` (publication timestamp, drives the Latest page), `categories`, `equipment`, `description`, `total_exposure`, `focal_length`, `locations` (name, bortle, dates as `YYYY-MM-DD`), `featured_image`, `filters` (name, subs as `"96 x 300s"`, integration as `"8h 00m"`).

Rules:
- **List `NEQ6 Pro` in `equipment` for every image taken from Italy** (home-site and Italian dark-site captures all use it). The one exception is the Swan Reach remote rig (see "Remote rig" below), which uses the Paramount ME instead. Never list both on one capture.
- Equipment names must match existing ones exactly (they become taxonomy pages). Grep the other pages before adding a new name.
- `categories` is a translated value: `Nebula` / `Nebulose` / `Туманности`. Copy the IT and RU values from a sibling page of the same type.
- IT and RU files: translate `title`, `description`, location names, `bortle` ("Class 4" becomes "Classe 4" in IT), body text. Keep numeric and equipment fields identical. Use localized quotation marks.
- Body text: factual, no hype. Say how it was stacked and processed.
- Several captures of one object (different rigs, crops): use a `versions:` list as in `content/dso/clusters/m5/index.md`. Top-level fields still feed cards and the equipment index.
- Alt text and ISO dates are enforced in the layouts; just keep dates in `YYYY-MM-DD`.

### Remote rig (Swan Reach, South Australia)

Images from the rented, shared remote rig go in the `australia` section: `content/australia/<slug>/` (flat, no subsections; the first five are ngc346, ngc1851, ngc300, ngc253, ngc6744). Use the same `categories` values as for Italian pages of the same type. Use these values:

- `equipment`: `["RCOS 16\"", "ASI2600MM Pro", "Paramount ME", "Astrodon LRGBSHO 2\" filters"]`. No `NEQ6 Pro`. Before writing, grep existing pages and reuse any matching name exactly (the Astrodon and RCOS names are new to the site until the first page is added, so the first one defines them for all later pages).
- `focal_length`: `"3660mm"` (the user's stated value for this rig; it differs from the 3360 mm in the user's profile notes, so do not "correct" it). Change it only if the user says a reducer was used.
- `locations`: name `"Swan Reach, South Australia, Australia"` (IT: `"Swan Reach, Australia Meridionale, Australia"`; RU: `"Суон-Рич, Южная Австралия, Австралия"`). Capture dates in `YYYY-MM-DD`. **`bortle`: `"Class 1"`** (IT `"Classe 1"`, RU `"Класс 1"`), as stated by the user for Swan Reach. The sky quality (about 21.98 SQM at moonless best) can go in the body text if it helps.
- Filters: names as for other pages (`L`, `R`, `G`, `B`, `Ha`, `OIII`, `SII`). Astrodon filters are 2", so they are not the Antlia 36 mm set.
- The frames belong to the whole group that shares the rig, not to the user alone. Say so in the body text ("data collected jointly by the group sharing the rig"). Do not write any copyright wording for these pages. The user has supplied the collaborators, to be credited in the body text on every Swan Reach page ("in collaboration with ...", alphabetical by surname): Paride Gabini, Rino Morra, Federico Palaia, Alessio Carmine Scipione (RU: Париде Габини, Рино Морра, Федерико Палайя, Алессио Кармине Щипионе). Do not name anyone else. The camera is the same ASI2600MM Pro as in the user's Italian setup, so reuse that equipment name unchanged.
- Ask the user whether the sub counts match the NINA session log, since several people may have captured the same target.
- Note for the layout: `layouts/_default/single.html` adds a copyright notice ("© year author. All rights reserved.") to each image's structured data, and the footer in `baseof.html` has a site-wide one. Writing nothing in the body does not remove either. If the user wants the per-image notice gone on remote pages, that needs a layout change (for example a front matter flag); propose it, do not edit the layout as part of adding an image.
- Add one factual sentence in the body: remotely operated rig at Swan Reach Imaging (link https://swanreachimaging.com.au), controlled with NINA. Do not state rental terms or prices on the site.
- Check Swan Reach Imaging's terms for any credit requirement before the first publication; do not assume them.
- The rental ends around 03/01/2027. Old pages stay valid, so write them in the past tense ("captured remotely from...").

### Video / time-lapse
Put a poster frame PNG in the bundle, set `featured_image` and `video_poster` to it, and add `video: "videos/<body>/<name>.mp4"`, `video_width`, `video_height`. Upload the MP4 with
`node scripts/r2-upload-video.mjs <local-file> videos/<body>/<name>.mp4`
(key must start with `videos/`). Videos are served directly from R2 and never synced into `content/`.

## 3. Upload the PNG to R2

`node scripts/r2-upload.mjs` (skips files whose MD5 already matches). It needs `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` in the environment. Never write these into files or commands; if they are not set, tell the user which are missing and stop.

This writes to external storage: state what will be uploaded and get confirmation first.

## 4. Test locally

- `hugo server` or `hugo --minify`. Check the new page in EN, IT and RU, the section list, Latest, and the equipment pages.
- Clean up by deleting `public/` only. **Never delete `resources/_gen`** (the image-processing cache; regenerating it is very slow).
- Node 24 and Hugo 0.168.0 (extended) are the pinned versions; match them.

## 5. Commit and deploy

Pushing to `main` triggers the GitHub Pages deploy. Show the diff summary and ask before committing or pushing. Commit message in English, short, imperative, e.g. "Add LDN 1295 (Giraffe Nebula)". The PNG must not appear in `git status` (`content/**/*.png` is ignored); if it does, stop.

## Out of scope

Posting to AstroBin, Instagram or other platforms is done by the user. If asked, produce only the text (caption, acquisition summary) in the chat or a git-ignored local folder, never in `content/` or `static/`.
