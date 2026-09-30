// Uploads one video file to R2 under a "videos/" key, for direct public
// playback via videoBaseURL (see hugo.toml) — never synced into Hugo/content.
// Requires R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
// in the environment.
//
// Usage: node scripts/r2-upload-video.mjs <local-file> <dest-key>
// Example: node scripts/r2-upload-video.mjs "C:\...\2025-02-05...mp4" videos/jupiter/2025-02-05.mp4
import { readFile, stat } from "node:fs/promises";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const [localFile, destKey] = process.argv.slice(2);
if (!localFile || !destKey) {
    console.error("Usage: node scripts/r2-upload-video.mjs <local-file> <dest-key>");
    process.exit(1);
}
if (!destKey.startsWith("videos/")) {
    console.error(`Destination key must start with "videos/" (got "${destKey}")`);
    process.exit(1);
}

const body = await readFile(localFile);
const { size } = await stat(localFile);
await s3.send(new PutObjectCommand({ Bucket: bucket, Key: destKey, Body: body, ContentType: "video/mp4" }));
console.log(`uploaded ${destKey} (${(size / 1024 / 1024).toFixed(1)} MB)`);
