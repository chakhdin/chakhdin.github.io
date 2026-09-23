import { S3Client } from "@aws-sdk/client-s3";

const required = ["R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"];
for (const name of required) {
    if (!process.env[name]) {
        console.error(`Missing required env var ${name}`);
        process.exit(1);
    }
}

export const bucket = process.env.R2_BUCKET;

export const s3 = new S3Client({
    region: "auto",
    endpoint: `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: {
        accessKeyId: process.env.R2_ACCESS_KEY_ID,
        secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
    },
});
