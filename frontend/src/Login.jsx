// import { useState } from "react";
// import { useNavigate } from "react-router-dom";
// import { useAuth } from "./Context/authContext.jsx";
// import { FcGoogle } from "react-icons/fc";
// import Signup from "./SIgnup.jsx";


// const Login = () => {
//     const [username, setUsername] = useState("");
//     const [password, setPassword] = useState("");

//     const { login, googleLogin } = useAuth();
//     const navigate = useNavigate();

//     const handleSubmit = async (e) => {
//         e.preventDefault();
//         try {
//             await login({
//                 username, password
//             });
//             navigate("/");
//         } catch (error) {
//             console.error("Error occurred while logging in:", error);
//         }
//     }

//     const handleGoogleLogin = (e) => {
//         e.preventDefault();
//         try {
//             googleLogin();
//         } catch (error) {
//             console.error("Error occurred while logging in with Google:", error);
//         }
//     };

//     return (
//         <div className="min-h-screen flex items-center justify-center bg-gray-900">
//             <form
//                 onSubmit={handleSubmit}
//                 className="bg-gray-800 p-6 rounded-lg shadow-md w-full max-w-sm"
//             >
//                 <h2 className="text-2xl font-bold text-white mb-4">Login</h2>

//                 <div className="mb-4">
//                     <label className="block text-gray-300 text-sm font-bold mb-2">
//                         Username
//                     </label>
//                     <input
//                         type="text"
//                         value={username}
//                         onChange={(e) => setUsername(e.target.value)}
//                         className="bg-gray-700 text-gray-300 border border-gray-500 rounded py-2 px-4 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
//                         placeholder="Username"
//                     />
//                 </div>

//                 <div className="mb-4">
//                     <label className="block text-gray-300 text-sm font-bold mb-2">
//                         Password
//                     </label>
//                     <input
//                         type="password"
//                         value={password}
//                         onChange={(e) => setPassword(e.target.value)}
//                         className="bg-gray-700 text-gray-300 border border-gray-500 rounded py-2 px-4 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
//                         placeholder="Password"
//                     />
//                 </div>

//                 <button
//                     type="submit"
//                     className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full"
//                 >
//                     Login
//                 </button>

//                 <button
//                     type="button"
//                     onClick={handleGoogleLogin}
//                     className="bg-white hover:bg-gray-100 text-black font-semibold py-2 px-4 rounded w-full mt-4 flex items-center justify-center gap-3 transition"
//                 >
//                     <FcGoogle size={22} />
//                     Login with Google
//                 </button>
//                 <p className="text-gray-400 text-sm text-center mt-6">
//                     Don't have an account?{" "}
//                     <span
//                         onClick={() => navigate("/signup")}
//                         className="text-blue-400 hover:text-blue-300 cursor-pointer font-semibold"
//                     >
//                         Sign Up
//                     </span>
//                 </p>
//             </form>
//         </div>
//     );


// }
// export default Login;
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./Context/authContext.jsx";
import { FcGoogle } from "react-icons/fc";
import { Play, MonitorPlay } from "lucide-react";

const Login = () => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const { login, googleLogin } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            await login({ username, password });
            navigate("/");
        } catch (error) {
            console.error("Error occurred while logging in:", error);
        }
    };

    const handleGoogleLogin = (e) => {
        e.preventDefault();

        try {
            googleLogin();
        } catch (error) {
            console.error("Error occurred while logging in with Google:", error);
        }
    };

    return (
        <div className="min-h-screen bg-[#0b0f19] text-white flex overflow-hidden">

            {/* Left Side */}
            <div className="hidden lg:flex w-1/2 relative items-center justify-center border-r border-white/10">

                {/* Background glow */}
                <div className="absolute top-20 left-20 w-72 h-72 bg-blue-500/10 blur-3xl rounded-full" />
                <div className="absolute bottom-10 right-10 w-80 h-80 bg-cyan-400/10 blur-3xl rounded-full" />

                <div className="relative z-10 max-w-xl px-12">

                    {/* Brand */}
                    <div className="flex items-center gap-4 mb-10">
                        <div className="p-4 rounded-2xl bg-white/10 border border-white/10 backdrop-blur-md">
                            <MonitorPlay size={32} />
                        </div>

                        <div>
                            <h1 className="text-3xl font-bold tracking-tight">
                                StreamFlow
                            </h1>

                            <p className="text-gray-400 text-sm">
                                Modern video streaming platform
                            </p>
                        </div>
                    </div>

                    {/* Main heading */}
                    <h2 className="text-5xl font-bold leading-tight mb-6">
                        Professional streaming
                        <span className="block text-gray-400">
                            built for creators.
                        </span>
                    </h2>

                    <p className="text-gray-400 text-lg leading-relaxed mb-10">
                        Upload, manage and stream high-quality videos with adaptive
                        playback, subtitles and multi-device support.
                    </p>

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-4">

                        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-md">
                            <h3 className="text-2xl font-bold mb-1">4K</h3>
                            <p className="text-gray-400 text-sm">
                                Ultra HD
                            </p>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-md">
                            <h3 className="text-2xl font-bold mb-1">HLS</h3>
                            <p className="text-gray-400 text-sm">
                                Adaptive bitrate
                            </p>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-2xl p-5 backdrop-blur-md">
                            <h3 className="text-2xl font-bold mb-1">99.9%</h3>
                            <p className="text-gray-400 text-sm">
                                Uptime
                            </p>
                        </div>

                    </div>
                </div>
            </div>

            {/* Right Side */}
            <div className="flex-1 flex items-center justify-center px-6 relative">

                {/* subtle background */}
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.04),transparent_30%)]" />

                <form
                    onSubmit={handleSubmit}
                    className="relative z-10 w-full max-w-md bg-white/[0.04] border border-white/10 backdrop-blur-2xl rounded-3xl p-8 shadow-2xl"
                >

                    {/* Logo */}
                    <div className="flex justify-center mb-8">
                        <div className="p-4 rounded-2xl bg-white/10 border border-white/10">
                            <Play size={28} fill="white" />
                        </div>
                    </div>

                    {/* Heading */}
                    <div className="text-center mb-8">
                        <h2 className="text-4xl font-bold mb-2">
                            Welcome Back
                        </h2>

                        <p className="text-gray-400">
                            Sign in to continue
                        </p>
                    </div>

                    {/* Username */}
                    <div className="mb-5">
                        <label className="block text-sm text-gray-300 mb-2">
                            Username
                        </label>

                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Enter your username"
                            className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-white/20 transition"
                        />
                    </div>

                    {/* Password */}
                    <div className="mb-6">
                        <label className="block text-sm text-gray-300 mb-2">
                            Password
                        </label>

                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                            className="w-full bg-black/30 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-white/20 transition"
                        />
                    </div>

                    {/* Login */}
                    <button
                        type="submit"
                        className="w-full bg-white text-black hover:bg-gray-200 transition-all duration-300 py-3 rounded-xl font-semibold text-lg"
                    >
                        Login
                    </button>

                    {/* Divider */}
                    <div className="flex items-center gap-4 my-6">
                        <div className="flex-1 h-px bg-white/10" />
                        <span className="text-gray-500 text-sm">
                            OR
                        </span>
                        <div className="flex-1 h-px bg-white/10" />
                    </div>

                    {/* Google */}
                    <button
                        type="button"
                        onClick={handleGoogleLogin}
                        className="w-full bg-white/5 hover:bg-white/10 border border-white/10 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-3 transition-all duration-300"
                    >
                        <FcGoogle size={24} />
                        Continue with Google
                    </button>

                    {/* Footer */}
                    <p className="text-center text-gray-400 mt-8 text-sm">
                        Don’t have an account?{" "}
                        <span
                            onClick={() => navigate("/signup")}
                            className="text-white hover:text-gray-300 cursor-pointer font-semibold"
                        >
                            Create account
                        </span>
                    </p>

                </form>
            </div>
        </div>
    );
};

export default Login;