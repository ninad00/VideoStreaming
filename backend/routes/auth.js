import express from "express";
const router = express.Router();

import { register, login, googleAuth, googleAuthCallback, getMe, logout } from "../controllers/authcontroller.js";
import { authenticateToken } from "../middlewares/jwt.js";


router.post("/register", register);
router.post("/login", login);
router.post("/logout", logout);



router.get('/google', googleAuth);         // user clicks "Login with Google"
router.get('/google/callback', googleAuthCallback);// Google redirects back here
router.get('/getMe', authenticateToken, getMe); // Get current user info

export default router;