// Fetches every object in the R2 bucket into content/<key>, recreating the
// same layout the PNGs used to have when they were committed directly. Run
// before `hugo build` in CI. Requires R2_ACCOUNT_ID, R2_BUCKET,
// R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in the environment.
//
// Objects under the "videos/" prefix are skipped: those are served directly
// from R2's public URL (see scripts/r2-upload-video.mjs) and never become
// Hugo page resources, so pulling them here would just waste CI time/disk.
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { ListObjectsV2Command, GetObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const contentDir = path.resolve(import.meta.dirname, "..", "content");
const CONCURRENCY = 8;
const MAX_ATTEMPTS = 4;

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchOne(key) {
    const dest = path.join(contentDir, key);
    await mkdir(path.dirname(dest), { recursive: true });
    for (let attempt = 1; ; attempt++) {
        try {
            const got = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
            await writeFile(dest, await got.Body.transformToByteArray());
            console.log(`fetched ${key}`);
            return;
        } catch (err) {
            if (attempt >= MAX_ATTEMPTS) throw err;
            const delay = 500 * 2 ** (attempt - 1);
            console.warn(`retrying ${key} after error (attempt ${attempt}/${MAX_ATTEMPTS}): ${err.message}`);
            await sleep(delay);
        }
    }
}

async function runPool(keys, limit) {
    let next = 0;
    async function worker() {
        while (next < keys.length) {
            const key = keys[next++];
            await fetchOne(key);
        }
    }
    await Promise.all(Array.from({ length: Math.min(limit, keys.length) }, worker));
}

let token;
let count = 0;
do {
    const page = await s3.send(new ListObjectsV2Command({ Bucket: bucket, ContinuationToken: token }));
    const keys = (page.Contents ?? []).map((obj) => obj.Key).filter((key) => !key.startsWith("videos/"));
    await runPool(keys, CONCURRENCY);
    count += keys.length;
    token = page.NextContinuationToken;
} while (token);

console.log(`\nDone: ${count} files synced from R2.`);
