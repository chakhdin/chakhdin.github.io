// Deletes the R2 objects listed in a text file (one key per line, relative to
// the bucket root, e.g. dso/clusters/m13/M13_1.annotated.png). Lines starting
// with # and blank lines are ignored.
// Default is a dry run: it only reports which keys exist. Add --yes to delete.
// Usage: node scripts/r2-delete.mjs <keys-file> [--yes]
// Requires R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in
// the environment.
import { readFile } from "node:fs/promises";
import { DeleteObjectCommand, HeadObjectCommand } from "@aws-sdk/client-s3";
import { s3, bucket } from "./r2-client.mjs";

const args = process.argv.slice(2);
const apply = args.includes("--yes");
const file = args.find((a) => !a.startsWith("--"));
if (!file) {
    console.error("Usage: node scripts/r2-delete.mjs <keys-file> [--yes]");
    process.exit(1);
}

const keys = (await readFile(file, "utf8"))
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));

async function size(key) {
    try {
        const head = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
        return head.ContentLength ?? 0;
    } catch (err) {
        if (err.name === "NotFound" || err.$metadata?.httpStatusCode === 404) return null;
        throw err;
    }
}

let found = 0;
let deleted = 0;
let missing = 0;
for (const key of keys) {
    const bytes = await size(key);
    if (bytes === null) {
        console.log(`missing   ${key}`);
        missing++;
        continue;
    }
    found++;
    if (apply) {
        await s3.send(new DeleteObjectCommand({ Bucket: bucket, Key: key }));
        deleted++;
        console.log(`deleted   ${key} (${(bytes / 1024 / 1024).toFixed(1)} MB)`);
    } else {
        console.log(`would delete ${key} (${(bytes / 1024 / 1024).toFixed(1)} MB)`);
    }
}
console.log(`\n${apply ? "Done" : "Dry run"}: ${keys.length} keys, ${found} existing, ${deleted} deleted, ${missing} missing.`);
if (!apply) console.log("Nothing was deleted. Add --yes to delete.");
