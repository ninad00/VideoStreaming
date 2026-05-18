import express from "express";
import cors from "cors";
import upload from "./routes/upload.js";
import video from "./routes/video.js";
import deletes from "./routes/delete.js";
import auth from "./routes/auth.js";
import cookieParser from "cookie-parser";
import dotenv from "dotenv";
dotenv.config();


const PORT = process.env.PORT || 3000;

const app = express();
app.use(express.json());
app.use(cookieParser());

app.use(cors({
    origin: process.env.FRONTEND_URL,
    credentials: true,
    methods: ["GET", "POST", "PUT", "DELETE"],
    allowedHeaders: ["Content-Type", "Authorization"]
}));

app.use('/upload', upload);
app.use('/delete', deletes);
app.use('/video', video);
app.use('/auth', auth);

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});