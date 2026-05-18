import { putObject, s3Client } from '../functions/s3.js';
import prisma from '../prisma.js';
import dotenv from 'dotenv';
import {
    CreateMultipartUploadCommand, UploadPartCommand, CompleteMultipartUploadCommand, AbortMultipartUploadCommand
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
dotenv.config();




export async function putPresignedUrl(req, res) {
    try {
        const { filename, contentType } = req.body;
        if (!filename || !contentType) {
            return res.status(400).json({ error: 'Filename and contentType are required' });
        }
        if (contentType !== 'video/mp4') {
            return res.status(400).json({ error: 'Only video/mp4 content type is supported' });
        }
        const video = await prisma.video.create({
            data: {
                title: filename,
                rawBucket: process.env.AWS_RAW_BUCKET,
                outBucket: process.env.AWS_OUT_BUCKET,
                status: 'UPLOADED',
                createdAt: new Date(),
            },
        });
        const fileId = video.id;

        const url = await putObject(fileId, contentType);
        await prisma.video.update({
            where: { id: fileId },
            data: {
                status: 'READY',
                thumbnail: `https://${process.env.AWS_OUT_BUCKET}.s3.${process.env.AWS_REGION}.amazonaws.com/${fileId}/thumbnails/thumb.jpg`,
                hls: `https://${process.env.AWS_OUT_BUCKET}.s3.${process.env.AWS_REGION}.amazonaws.com/${fileId}/master.m3u8`
            },
        });

        return res.status(200).json({ url });
    } catch (error) {

        return res.status(500).json({ error: `${error.message}` });
    }
}

export async function getPresignedUrl(req, res) {
    try {
        const { filename, contentType } = req.body;
        if (!filename || !contentType) {
            return res.status(400).json({ error: 'Filename and contentType are required' });
        }
        if (contentType !== 'video/mp4') {
            return res.status(400).json({ error: 'Only video/mp4 content type is supported' });
        }
        const url = await putObject(filename, contentType);

        return res.status(200).json({ url });
    } catch (error) {

        return res.status(500).json({ error: `${error.message}` });
    }
}
export async function startMultipartUpload(
    req,
    res
) {
    try {
        console.log(req.body);
        const { filename, description, uploaderName, contentType } =
            req.body;

        if (!filename || !contentType) {
            return res.status(400).json({
                error:
                    "Filename and contentType required"
            });
        }

        if (contentType !== "video/mp4") {
            return res.status(400).json({
                error: "Only mp4 supported"
            });
        }

        const video = await prisma.video.create({
            data: {
                title: filename,
                uploaderName: uploaderName || "Anonymous",
                rawBucket:
                    process.env.AWS_RAW_BUCKET,
                outBucket:
                    process.env.AWS_OUT_BUCKET,
                description: description || "",
                status: "UPLOADED",
                createdAt: new Date()
            }
        });

        const fileId = video.id;

        const key = `videos/${fileId}.mp4`;

        const command =
            new CreateMultipartUploadCommand({
                Bucket: process.env.AWS_RAW_BUCKET,
                Key: key,
                ContentType: contentType
            });

        const response = await s3Client.send(
            command
        );

        return res.status(200).json({
            uploadId: response.UploadId,
            key,
            fileId
        });
    } catch (err) {
        return res.status(500).json({
            error: err.message
        });
    }
}

export async function getMultipartPresignedUrl(req, res) {
    try {
        const {
            key,
            uploadId,
            partNumber
        } = req.body;

        const command = new UploadPartCommand(
            {
                Bucket:
                    process.env.AWS_RAW_BUCKET,
                Key: key,
                UploadId: uploadId,
                PartNumber: partNumber
            }
        );

        const url = await getSignedUrl(
            s3Client,
            command,
            {
                expiresIn: 3600
            }
        );

        return res.status(200).json({
            url
        });
    } catch (err) {
        return res.status(500).json({
            error: err.message
        });
    }
}

export async function completeMultipartUpload(
    req,
    res
) {
    try {
        const {
            key,
            uploadId,
            parts,
            fileId
        } = req.body;

        const command =
            new CompleteMultipartUploadCommand({
                Bucket:
                    process.env.AWS_RAW_BUCKET,

                Key: key,

                UploadId: uploadId,

                MultipartUpload: {
                    Parts: parts
                }
            });

        await s3Client.send(command);

        await prisma.video.update({
            where: {
                id: fileId
            },
            data: {
                status: "READY",

                thumbnail:
                    `https://${process.env.AWS_OUT_BUCKET}.s3.${process.env.AWS_REGION}.amazonaws.com/${fileId}/thumbnails/thumb.jpg`,

                hls:
                    `https://${process.env.AWS_OUT_BUCKET}.s3.${process.env.AWS_REGION}.amazonaws.com/${fileId}/master.m3u8`
            }
        });

        return res.status(200).json({
            success: true
        });
    } catch (err) {
        return res.status(500).json({
            error: err.message
        });
    }
}