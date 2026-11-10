---
name: new-target
description: Run the whole flow for one new target from its PixInsight object folder to the live page and the Instagram, Facebook and Pinterest posts. Chains web-copies.py, pi_logs.py, add-image, social-post, social-images.py, r2-upload-social.mjs, the Hugo test, the deploy and Buffer, with three approval gates. Use when the user says "new target", gives a PixInsight object folder, or wants a finished image published end to end.
---

# New target, end to end

Input: a PixInsight object folder, e.g. `E:\Astro\pixinsight\vdB 142` (NGC 253 is in `C:\Astro\pixinsight\`).
This skill only sequences other steps; the details live in `add-image` and `social-post`. Read both before starting.
Nothing is committed, pushed, uploaded to R2 or sent to Buffer without the approval of the gate it belongs to.
Order matters: the page must be deployed before any Buffer post, because Facebook and Pinterest link to it.

## Step 0: duplicate check

Before any work, check whether the target is already posted (by hand or by an earlier run) on Instagram, Facebook or Pinterest
with `list_posts` for each channel (vdB 142 was posted by hand on Facebook on 01/11/2026). Tell the user what exists and
which channels to skip. Repeat this check right before `create_post` (step 12).

## Gate 1: content ready, then R2 uploads

1. **Web copies.** Italian targets keep the final XISF in a date subfolder (e.g. `E:\Astro\pixinsight\vdB 142\2024-09-07\vdB142_1.xisf`),
   and `find_final_xisf` searches only the top level of the folder it is given. So pass the date folder that holds the final file,
   or `--file "<xisf>"`: `python scripts/web-copies.py "<date folder>"`. It takes the highest `_N` XISF that is not `*.annotated.xisf`
   and writes `<object>.png`, `.jpg` (q95, 4:4:4), `.resample.png` and `.facts.json` next to it (no overwrite without `--force`;
   `--name`, `--no-lookup`, `--file`/`--out` as in the script header). Always check the `Source:` line it prints: it must be the intended file.
   Files such as M31 masterLight files and `NGC7635_1.crop.xisf` are not picked reliably; use `--file` for them.
   `<object>` is `--name` or the first SIMBAD object, which can be the parent nebula: check the `Object:` line and, if it is wrong,
   rerun with `--name <name> --force`. `.resample.png` exists only when the full PNG exceeds 15 MiB.
   Known limits: compressed XISF and non-attachment image data are refused, and no title/author/copyright metadata is written.
   16-bit and mono sources are handled by the code but untested, so check the output. If the file is refused, stop and tell the user.
   Check the result by looking at the JPEG.
2. **Facts.** `python scripts/pi_logs.py "<object folder>"` (the object folder, not the date folder: it globs `*/output/logs/*.log`)
   prints the final Light groups, the `SESSION:` nights and the lights' header. For a mosaic it prints "Mosaic: N panels" and the counts per panel: follow the mosaic rules in `add-image` section 2 (`mosaic_panels`, `panels` per filter, a sentence in the body text).
   Use the "active" count (never the group total; `Clear` is `L`), recompute `total_exposure` and check subs x seconds.
   Location name and Bortle class come from the git-ignored `scripts/sites.local.json`; if the site is missing, ask the user and
   never write coordinates into the repo. Swan Reach (`australia` section) follows the "Remote rig" rules in `add-image`.
3. **Page bundle.** Follow `add-image` sections 1-2: `content/<section>/<slug>/` with `index.md`, `index.it.md`, `index.ru.md`
   and the JPEG as `featured_image` (the DSO pages use the non-annotated full-size JPEG; it replaces the PNG mentioned in `add-image` sections 1-2). Copy a sibling page of the same type
   for the front matter. Every factual statement in the body must be sourced (facts.json, logs, an existing page); no outside knowledge.
4. **Social material.** Follow `social-post`: `python scripts/social-export.py content/<section>/<slug>` (once only, it overwrites the post texts),
   then `python scripts/social-images.py content/<section>/<slug>` for `instagram.jpg` (4:5, also Facebook) and `pinterest.jpg` (2:3),
   then the intros, hashtags and `claims.txt`. Run `social-export.py` first, never again after the intros are written.
   Instagram has no first-comment on the Free plan, so all hashtags go into the caption (max 2,200 characters, check the count).
5. **Show and stop.** Show the user: page text in all three languages, figures with the arithmetic, post texts with character counts,
   `claims.txt`, and the page JPEG and both social JPEGs. List exactly what the R2 uploads will be:
   - Social: the output of `node scripts/r2-upload-social.mjs <slug>` (dry run, no network).
   - Page images: `r2-upload.mjs` has no dry run and uploads every `content/**/*.png|jpg` whose MD5 differs from R2, not only this target's.
     These files are git-ignored, so `git status` does not show them. List the new and changed image files under `content/`
     (the bundle's files plus any other recently modified image, e.g. with `Get-ChildItem content -Recurse -Include *.png,*.jpg | Sort-Object LastWriteTime -Descending | Select-Object -First 20 FullName, LastWriteTime`).
     This listing shows recently written files, not a comparison with R2. Warn the user that the page-image upload covers all changed images.

   Wait for approval.
6. **R2 uploads (after approval).** Page images: `node scripts/r2-upload.mjs` (skips files whose MD5 matches).
   Social JPEGs: `node scripts/r2-upload-social.mjs <slug> --yes` uploads to `social/<slug>/`.
   The `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` variables are in the user's environment;
   never write them into files or commands, and if one is missing, name it and stop.
   Public check: `https://pub-31bf1763ca934d78aa1296ab64e4629e.r2.dev/social/<slug>/instagram.jpg` with curl (Python urllib gets 403).

## Gate 2: local test, commit, push

7. **Local test.** `hugo server` or `hugo --minify` (Hugo 0.168.0 extended, Node 24). Check the new page in EN, IT and RU,
   the section list, Latest and the equipment pages. Clean up by deleting `public/` only; never `resources/_gen`.
8. **Show and stop.** The repo may hold other untracked work, so stage only `content/<section>/<slug>/` (`git add content/<section>/<slug>/`;
   never `git add -A` or `git add .`). Show `git status`, the staged list (`git diff --cached --name-status`) and the diff summary.
   The JPEG must not appear (`content/**/*.png` and `*.jpg` are ignored); if it does, stop. Any other change to commit needs its own mention.
   Ask before committing. After a yes: commit with an English, short, imperative message (e.g. "Add vdB 142 (Elephant's Trunk Nebula)"),
   then ask again before pushing. Pushing `main` triggers the GitHub Pages deploy.
9. **Verify the deploy.** Get the run with `gh run list --workflow hugo.yaml --branch main --limit 1` and compare its `headSha` with `git rev-parse HEAD`
   (they must match), then `gh run watch <run-id> --exit-status`.
   After it succeeds, check that the live page loads with the image and the right title in EN, IT and RU.
   Do not go to Gate 3 before this passes.

## Gate 3: Buffer posts

Buffer MCP (`https://mcp.buffer.com/mcp`), organisation "My organization", timezone Europe/Rome. Get channel and board IDs with
`list_channels` / `get_channel` in the session rather than from memory; the notes that follow were true on 02/11/2026.

10. **Prepare.** One post per channel with the public R2 image URL as asset and required alt text:
    - Instagram (@chakhdin): `social/<slug>/post-instagram.txt`, `instagram.jpg`, English then Italian, "Link in bio" wording, no `linkAttachment`.
    - Facebook Page: `post-web.txt`, `instagram.jpg`, English then Italian; `linkAttachment` cannot go with assets, so the text carries the page URLs.
    - Pinterest: `post-pinterest.txt` (English only, at most 500 characters; show the count), `pinterest.jpg`,
      the board for the object type (Nebulae, Galaxies or Star Clusters: Astrophotography; look up the `serviceId` with `get_channel`), link to the page.
    - Instagram and Facebook slot is Wednesday 18:58; Pinterest Friday 16:24. Free plan: 10 scheduled posts per channel.
11. **Show and stop.** For each post show the exact text, image, channel, `mode` and `dueAt` (Europe/Rome, with offset). Wait for approval.
    A queued post publishes by itself.
12. **Create as drafts.** Repeat the duplicate check of step 0. Then call `create_post` with `saveToDraft: true` for each channel,
    setting `mode` and `dueAt` per channel as approved. To schedule, ask for a fresh explicit yes before each `edit_post` with `saveToDraft:false`
    (plus `mode`). `edit_post` re-validates the whole post, so resend text, assets and metadata every time.
    Without `saveToDraft:false` the post stays `draft`. Check `get_post` status afterwards.
13. **Report** what was scheduled (post ids, channel, time Rome). Metrics a week later with `get_post` and `includeMetrics: true`.

## Not covered (stay manual)

AstroBin posting (its API is read-only; the user does it by hand), SSO images, the Instagram API route (declined).

## Never

Never:

- Commit, push or upload to R2 without the approval of the gate the action belongs to.
- Call `edit_post` with `saveToDraft:false` without a fresh explicit yes for that specific call, given just before it.
- Create a post without `saveToDraft: true`.
- Stage with `git add -A` or `git add .`.
- Re-run `social-export.py` after the intros exist.
- Put post text into `content/` or `static/`.
- Write credentials or site coordinates into the repo.
