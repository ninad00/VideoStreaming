import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../Context/authContext";

export default function OAuthSuccess() {
    const navigate = useNavigate();
    const { refreshUser } = useAuth();

    useEffect(() => {
        const run = async () => {
            await refreshUser();
            navigate("/dashboard");
        };
        run();
    }, []);

    return <p>Signing you in...</p>;
}