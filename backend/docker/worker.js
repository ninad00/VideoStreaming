import {
  SQSClient,
  ReceiveMessageCommand,
  GetQueueUrlCommand,
  DeleteMessageCommand
} from "@aws-sdk/client-sqs";

import {
  S3Client,
  GetObjectCommand,
  PutObjectCommand,
  DeleteObjectCommand
} from "@aws-sdk/client-s3";

import fs from "fs";
import path from "path";
import { processVideo } from "./transcode.js";
import "dotenv/config";

/* =========================
   ENV
========================= */

const RAW_BUCKET = process.env.AWS_RAW_BUCKET;
const OUT_BUCKET = process.env.AWS_OUT_BUCKET;
const REGION = process.env.AWS_REGION;
const MODAL_PROCESS_URL = process.env.MODAL_PROCESS_URL;

/* =========================
   AWS CLIENTS
========================= */

const sqs = new SQSClient({ region: REGION });

const { QueueUrl } = await sqs.send(
  new GetQueueUrlCommand({ QueueName: process.env.AWS_SQS_NAME })
);

const s3 = new S3Client({
  region: REGION,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
  }
});

/* =========================
   HELPERS
========================= */

async function downloadFromS3(bucket, key, dest) {
  const res = await s3.send(
    new GetObjectCommand({ Bucket: bucket, Key: key })
  );

  await new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    res.Body.pipe(file);
    res.Body.on("error", reject);
    file.on("finish", resolve);
  });
}

async function uploadDir(dir, prefix) {
  const files = fs.readdirSync(dir, { recursive: true });

  for (const f of files) {
    const full = path.join(dir, f);
    if (fs.statSync(full).isFile()) {
      await s3.send(
        new PutObjectCommand({
          Bucket: OUT_BUCKET,
          Key: `${prefix}/${f}`,
          Body: fs.createReadStream(full)
        })
      );
    }
  }
}


async function requestSubtitles(videoId, audioKey) {
  const res = await fetch(MODAL_PROCESS_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      video_id: videoId,
      out_bucket: OUT_BUCKET,
      out_prefix: videoId,
      audio_key: audioKey
    })
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Modal failed: ${res.status} ${text}`);
  }

  const json = await res.json();
  console.log("✅ Subtitles done:", json);
}

/* =========================
   MAIN LOOP
========================= */

async function loop() {
  console.log("🚀 Worker started, polling SQS…");

  while (true) {
    const { Messages } = await sqs.send(
      new ReceiveMessageCommand({
        QueueUrl,
        MaxNumberOfMessages: 1,
        WaitTimeSeconds: 20
      })
    );

    if (!Messages) continue;

    const msg = Messages[0];

    try {
      const event = JSON.parse(msg.Body);
      const record = event.Records[0];

      const bucket = record.s3.bucket.name;
      const key = decodeURIComponent(
        record.s3.object.key.replace(/\+/g, " ")
      );

      console.log("📦 Processing:", bucket, key);

      const input = "/tmp/input.mp4";
      const output = "/tmp/output";

      // 1. Download video
      await downloadFromS3(bucket, key, input);


      const fileName = path.basename(key);
      const baseName = path.parse(fileName).name;
      console.log("🎬 Base name:", baseName);

      try {
        const { whisperAudio } = await processVideo(input, output);

        if (whisperAudio) {

          const audioKey = `${baseName}/audio/whisper.wav`;

          await s3.send(
            new PutObjectCommand({
              Bucket: OUT_BUCKET,
              Key: audioKey,
              Body: fs.createReadStream(whisperAudio),
              ContentType: "audio/wav"
            })
          );

          try {
            await requestSubtitles(baseName, audioKey);
          } catch (err) {
            console.error(
              "❌ Subtitle dispatch failed:",
              err.message
            );
          }
        }
      } catch (err) {
        console.error(
          "❌ Audio processing failed:",
          err
        );
      }



      // 4. Upload HLS output
      await uploadDir(output, baseName);

      // 5. Trigger Modal transcription


      // 6. Cleanup original upload
      await s3.send(
        new DeleteObjectCommand({ Bucket: bucket, Key: key })
      );



      // 7. Delete SQS message
      await sqs.send(
        new DeleteMessageCommand({
          QueueUrl,
          ReceiptHandle: msg.ReceiptHandle
        })
      );

      console.log("✅ Finished:", baseName);

    } catch (err) {
      console.error("🔥 Worker error:", err);
    } finally {
      try {
        fs.rmSync("/tmp/input.mp4", { force: true });
        fs.rmSync("/tmp/output", { recursive: true, force: true });
      } catch { }
    }
  }
}

loop().catch(console.error);