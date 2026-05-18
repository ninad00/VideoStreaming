import express from "express";

import { getVideos } from '../controllers/videocontroller.js';
import { getVideoById } from '../controllers/videocontroller.js';

const router = express.Router();

router.get('/', getVideos);

// router.get("/", async (req, res) => {
//     try {

//         const search = req.query.search || "";

//         const videos = await prisma.video.findMany({
//             where: {
//                 title: {
//                     contains: search,
//                     mode: "insensitive",
//                 },
//             },
//         });

//         console.log(`Fetched ${videos.length} videos for search: "${search}"`);
//         res.json(videos);

//     } catch (err) {
//         console.error(err);

//         res.status(500).json({
//             error: "Failed to fetch videos",
//         });
//     }
// });
router.get('/:id', getVideoById);

export default router;