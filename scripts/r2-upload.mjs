// One-time migration: uploads every content/**/*.png to R2, keyed by its
// path relative to content/. Run locally, once, before removing the PNGs
// from git tracking. Requires R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID,
// R2_SECRET_ACCESS_KEY in the environment.
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const contentDir = path.resolve(import.meta.dirname, "..", "content");

async function* walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) yield* walk(full);
        else if (entry.isFile() && entry.name.toLowerCase().endsWith(".png")) yield full;
    }
}

let count = 0;
let bytes = 0;
for await (const file of walk(contentDir)) {
    const key = path.relative(contentDir, file).split(path.sep).join("/");
    const body = await readFile(file);
    const { size } = await stat(file);
    await s3.send(new PutObjectCommand({ Bucket: bucket, Key: key, Body: body, ContentType: "image/png" }));
    count++;
    bytes += size;
    console.log(`uploaded ${key} (${(size / 1024 / 1024).toFixed(1)} MB)`);
}
console.log(`\nDone: ${count} files, ${(bytes / 1024 / 1024).toFixed(1)} MB total.`);
