// Uploads the social JPEGs of one image to the R2 media bucket under "social/<slug>/", so Buffer
// can fetch them from the public URL. Never synced into Hugo/content.
// Default is a dry run: it lists the files and keys, with no network access.
// Add --yes to upload. Uploading requires R2_ACCOUNT_ID, R2_BUCKET,
// R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in the environment.
//
// Usage: node scripts/r2-upload-social.mjs <slug> [--yes]
// Example: node scripts/r2-upload-social.mjs vdb142 --yes
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

const args = process.argv.slice(2);
const apply = args.includes("--yes");
const slug = args.find((a) => !a.startsWith("--"));
if (!slug || !/^[a-z0-9-]+$/.test(slug)) {
    console.error("Usage: node scripts/r2-upload-social.mjs <slug> [--yes]");
    process.exit(1);
}

const dir = path.join("social", slug);
const files = (await readdir(dir)).filter((f) => /^(instagram|pinterest)\.jpg$/.test(f)).sort();
if (!files.length) {
    console.error(`No instagram.jpg or pinterest.jpg in ${dir}; run scripts/social-images.py first`);
    process.exit(1);
}

let client;
if (apply) {
    client = await import("./r2-client.mjs");
}
const { PutObjectCommand } = apply ? await import("@aws-sdk/client-s3") : {};

for (const file of files) {
    const key = `social/${slug}/${file}`;
    const { size } = await stat(path.join(dir, file));
    const label = `${key} (${(size / 1024).toFixed(0)} KiB)`;
    if (!apply) {
        console.log(`would upload ${label}`);
        continue;
    }
    const body = await readFile(path.join(dir, file));
    await client.s3.send(new PutObjectCommand({ Bucket: client.mediaBucket, Key: key, Body: body, ContentType: "image/jpeg" }));
    console.log(`uploaded ${label}`);
}
if (!apply) console.log("Dry run only. Add --yes to upload.");
