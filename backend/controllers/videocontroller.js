import prisma from '../prisma.js';

export async function getVideos(req, res) {
    try {
        const search = req.query.search || "";
        const videos = await prisma.video.findMany({
            where: {
                title: {
                    contains: search,
                    // mode: "insensitive",
                },
            },
            orderBy: { createdAt: 'desc' },
            select: {
                id: true,
                title: true,
                thumbnail: true,
                description: true,
                duration: true,
                uploaderName: true

            }
        });

        const data = videos.map(video => ({
            id: video.id,
            title: video.title,
            thumbnail_url: video.thumbnail,
            description: video.description,
            duration: video.duration,
            uploaderName: video.uploaderName
        }));
        console.log("SEARCH:", search);
        console.log(videos.map(v => v.id));
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
}
// export const getVideos = async (req, res) => {
//     try {

//         const search = req.query.search || "";

//         const videos = await prisma.video.findMany({
//             where: {
//                 title: {
//                     contains: search,
//                     // mode: "insensitive",
//                 },
//             },
//         });

//         console.log("SEARCH:", search);

//         res.json(videos);

//     } catch (err) {
//         console.error(err);

//         res.status(500).json({
//             error: "Failed to fetch videos",
//         });
//     }
// };

export async function getVideoById(req, res) {
    try {
        const video = await prisma.video.findUnique({
            where: { id: req.params.id }
        });

        if (!video) {
            return res.status(404).json({ error: "Video not found" });
        }

        res.json({
            id: video.id,
            title: video.title,
            hls_url: video.hls,
            description: video.description,
            duration: video.duration,
            uploaderName: video.uploaderName
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
}

export async function deleteVideo(req, res) {
    try {
        const video = await prisma.video.delete({
            where: { id: req.params.id }
        })
        res.json({ message: "Video deleted successfully" })
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
}