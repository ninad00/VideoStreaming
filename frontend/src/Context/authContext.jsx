import { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const api = axios.create({
    baseURL: "http://localhost:3000",
    withCredentials: true
});

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const refreshUser = async () => {
        try {
            const res = await api.get("/auth/getMe");
            setUser(res.data);
        } catch (err) {
            setUser(null);
        }
    };

    useEffect(() => {
        const init = async () => {
            await refreshUser();
            setLoading(false);
        };
        init();
    }, []);


    const login = async (credentials) => {
        await api.post("/auth/login", credentials); // cookie set here
        await refreshUser(); // fetch user
    };


    const googleLogin = async () => {
        window.location.href = "http://localhost:3000/auth/google";
    };


    const logout = async () => {
        try {
            await api.post("/auth/logout");
        } catch (err) {
            console.error("Logout failed:", err);
        }
        setUser(null);
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                isAuthenticated: !!user,
                login,
                logout,
                googleLogin,
                refreshUser
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};