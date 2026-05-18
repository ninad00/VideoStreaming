import jwt from "jsonwebtoken";
import dotenv from "dotenv";
dotenv.config();
// import { prisma } from "../prisma.js";


export function generateToken(username, id) {
    const payload = {
        id: id,
        username: username,
    };
    return jwt.sign(payload, process.env.JWT_SECRET, { expiresIn: '1h' });
}

export const authenticateToken = (req, res, next) => {
    const token = req.cookies.token;
    if (!token) {
        return res.status(401).json({ error: 'Token required' });
    }
    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        req.user = decoded;
        next();
    } catch (err) {
        return res.status(401).json({ error: 'Invalid token' });
    }
}