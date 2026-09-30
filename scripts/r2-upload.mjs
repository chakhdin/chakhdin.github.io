// Uploads content/**/*.png to R2, keyed by its path relative to content/.
// Safe to run any time you add or change photos — it skips files whose
// content already matches what's in R2 (compared by MD5 against the
// object's ETag), so re-running after a small addition only uploads what's
// actually new or changed. Requires R2_ACCOUNT_ID, R2_BUCKET,
// R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in the environment.
import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { PutObjectCommand, HeadObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const contentDir = path.resolve(import.meta.dirname, "..", "content");

async function* walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) yield* walk(full);
        else if (entry.isFile() && entry.name.toLowerCase().endsWith(".png")) yield full;
    }
}

async function existingETag(key) {
    try {
        const head = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
        return (head.ETag ?? "").replaceAll('"', "");
    } catch (err) {
        if (err.name === "NotFound" || err.$metadata?.httpStatusCode === 404) return null;
        throw err;
    }
}

let uploaded = 0;
let skipped = 0;
let bytes = 0;
for await (const file of walk(contentDir)) {
    const key = path.relative(contentDir, file).split(path.sep).join("/");
    const body = await readFile(file);
    const md5 = createHash("md5").update(body).digest("hex");

    if ((await existingETag(key)) === md5) {
        skipped++;
        continue;
    }

    const { size } = await stat(file);
    await s3.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: body, ContentType: "image/png" }));
    uploaded++;
    bytes += size;
    console.log(`uploaded ${key} (${(size / 1024 / 1024).toFixed(1)} MB)`);
}
console.log(`\nDone: ${uploaded} uploaded (${(bytes / 1024 / 1024).toFixed(1)} MB), ${skipped} unchanged and skipped.`);
