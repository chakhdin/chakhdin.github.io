// Fetches every object in the R2 bucket into content/<key>, recreating the
// same layout the PNGs used to have when they were committed directly. Run
// before `hugo build` in CI. Requires R2_ACCOUNT_ID, R2_BUCKET,
// R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in the environment.
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { ListObjectsV2Command, GetObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const contentDir = path.resolve(import.meta.dirname, "..", "content");

let token;
let count = 0;
do {
    const page = await s3.send(new ListObjectsV2Command({ Bucket: bucket, ContinuationToken: token }));
    for (const obj of page.Contents ?? []) {
        const dest = path.join(contentDir, obj.Key);
        await mkdir(path.dirname(dest), { recursive: true });
        const got = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: obj.Key }));
        await writeFile(dest, await got.Body.transformToByteArray());
        count++;
        console.log(`fetched ${obj.Key}`);
    }
    token = page.NextContinuationToken;
} while (token);

console.log(`\nDone: ${count} files synced from R2.`);
