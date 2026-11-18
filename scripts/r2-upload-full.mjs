// Uploads the full-size JPEGs listed in data/full_images.json (built by scripts/full-images.py into full/)
// to the R2 media bucket, where the fullscreen viewer loads them when it zooms in. Never synced into Hugo/content.
// Default is a dry run: it lists the files and keys, with no network access.
// Add --yes to upload. Uploading requires R2_ACCOUNT_ID, R2_BUCKET,
// R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in the environment.
//
// Usage: node scripts/r2-upload-full.mjs [<text>] [--yes]
//   <text>: only keys containing it, e.g. "australia/ngc300"
import { readFile, stat } from "node:fs/promises";

const args = process.argv.slice(2);
const apply = args.includes("--yes");
const only = args.find((a) => !a.startsWith("--"));

const mapping = JSON.parse(await readFile("data/full_images.json", "utf8"));
const keys = [...new Set(Object.values(mapping))].filter((k) => !only || k.includes(only)).sort();
if (!keys.length) {
    console.error(only ? `No key in data/full_images.json contains "${only}"` : "data/full_images.json is empty");
    process.exit(1);
}

let client;
if (apply) {
    client = await import("./r2-client.mjs");
}
const { PutObjectCommand } = apply ? await import("@aws-sdk/client-s3") : {};

let total = 0;
for (const key of keys) {
    // The local copy sits at the same path as the key: full/<page path>/<name>.jpg
    const { size } = await stat(key);
    total += size;
    const label = `${key} (${(size / 2 ** 20).toFixed(1)} MiB)`;
    if (!apply) {
        console.log(`would upload ${label}`);
        continue;
    }
    const body = await readFile(key);
    await client.s3.send(new PutObjectCommand({ Bucket: client.mediaBucket, Key: key, Body: body, ContentType: "image/jpeg" }));
    console.log(`uploaded ${label}`);
}
console.log(`${keys.length} files, ${(total / 2 ** 20).toFixed(1)} MiB`);
if (!apply) console.log("Dry run only. Add --yes to upload.");
