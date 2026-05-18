import express from "express";
import { putPresignedUrl ,startMultipartUpload,getMultipartPresignedUrl,completeMultipartUpload} from '../controllers/s3controller.js';
const router = express.Router();

router.post('/posturl', putPresignedUrl);
router.post(
    "/multipart/start",
    startMultipartUpload
);

router.post(
    "/multipart/sign",
    getMultipartPresignedUrl
);

router.post(
    "/multipart/complete",
    completeMultipartUpload
);
export default router;