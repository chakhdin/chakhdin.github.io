---
name: social-post
description: Write the intro, claim list and object-specific hashtags for an Instagram/Facebook/Pinterest post of a gallery page. Reads the page bundle and writes into social/<slug>/. Never posts or uploads. Use after the page exists (or is drafted) and before any Buffer call.
---

# Social post text

Input: a page bundle `content/<section>/<slug>/` (index.md, index.it.md).
Output: files in `social/<slug>/` (git-ignored). This skill never calls Buffer, never uploads to R2 (the upload belongs to new-target step 6), never commits.

## 1. Generate the fixed part
`python scripts/social-export.py content/<section>/<slug>` (adds a "Mosaic of N panels" line to the stats block when the page has `mosaic_panels`) writes post-instagram.txt and post-web.txt
(title, intro placeholder, 📍🔭📷⏱️💻 lines, link, hashtags). Figures come from front matter; do not retype them.

## 1b. Generate the channel images
`python scripts/social-images.py content/<section>/<slug>` writes `social/<slug>/instagram.jpg` (4:5, 1080x1350; Facebook uses it too)
and `pinterest.jpg` (2:3, 1000x1500). A landscape frame is rotated 90 degrees clockwise (lossless, the sky has no up or down)
and cropped to fill the canvas; `--rotate none|ccw` and `--x/--y` (crop centre) override it. Show both files to the user.
Do not re-run `social-export.py` after the intros are written: it overwrites post-instagram.txt and post-web.txt.
Upload is a separate step: `node scripts/r2-upload-social.mjs <slug>` is a dry run, `--yes` uploads; the assistant runs it
after the user approves (the R2 variables are in the user's environment, never in files or commands).

## 2. Write the intro (replaces the placeholder)
- EN first, then IT. Length: 4-5 sentences per language for post-web.txt (Facebook);
  at most 3 sentences per language for post-instagram.txt, because the caption carries both languages
  and Instagram caps a caption at 2,200 characters. Check the final character count.
- Pinterest: write `post-pinterest.txt` by hand, English only, at most 500 characters including title and hashtags
  (title, a shortened EN intro with the key data, the hashtags; the link goes on the pin, not in the text).
  Shorten or reword as needed to stay under the limit; same sourcing rules.
- Plain and factual, no hype, no hashtags in the intro.
- Source only: the page body, the front matter, `<object>.facts.json` (SIMBAD/plate solve).
  No outside knowledge. If a fact is not on the page, leave it out.
- IT is a translation of the EN intro, not a separate text; reuse the wording of index.it.md where it fits.
- Do not use words the page does not support (e.g. "protostars", "carves", "stunning").
- Say what the image shows and how it was made; one sentence on the object, one on the data.

## 3. Hashtags
- 2-3 object-specific tags built from names that appear on the page or in facts.json
  (catalogue id without spaces, e.g. `#vdB142`; common name, e.g. `#ElephantsTrunkNebula`;
  parent object or constellation named on the page, e.g. `#IC1396`, `#Cepheus`).
- Then the generic tags of the template (`#astrophotography #astronomy #deepsky`).
- Total at most 10. Apply the same tags to all channels.

## 4. Claim list (shown to the user, not posted)
Write `social/<slug>/claims.txt`: one line per factual statement in the intro,
as `<claim> | <page sentence or facts.json key that supports it>`.
A claim with no source is deleted from the intro before showing it.

## 5. Annotations (optional)
If facts.json lists objects in the field, add one line "In the field: A, B, C" (max 5, brightest first),
each present in facts.json. Skip if the list is empty.

## 6. Show and stop
Show the user: both intros, the hashtags, the claim list, the final post-instagram.txt, post-web.txt and post-pinterest.txt
with character counts. Wait for approval. Posting is a separate step with its own approval
(see `new-target`, Gate 3).
