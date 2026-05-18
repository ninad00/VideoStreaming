import { X, Home, Video, Upload, User, Settings, LogOut } from "lucide-react";

export default function Sidebar({
    sidebarOpen,
    setSidebarOpen,
    user,
    logout,
}) {

    return (
        <>
            {/* Overlay */}
            <div
                onClick={() => setSidebarOpen(false)}
                className={`fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity duration-300
                ${sidebarOpen
                        ? "opacity-100 pointer-events-auto"
                        : "opacity-0 pointer-events-none"
                    }`}
            />

            {/* Sidebar */}
            <aside
                className={`fixed top-0 right-0 h-screen w-[340px] bg-[#111827]/95 backdrop-blur-2xl border-l border-white/10 z-50 transition-transform duration-300
                ${sidebarOpen
                        ? "translate-x-0"
                        : "translate-x-full"
                    }`}
            >

                {/* Header */}
                <div className="h-20 px-6 border-b border-white/10 flex items-center justify-between">

                    <div>

                        <h2 className="text-xl font-bold text-white">
                            Menu
                        </h2>

                        <p className="text-sm text-gray-500">
                            Navigation Panel
                        </p>

                    </div>

                    <button
                        onClick={() => setSidebarOpen(false)}
                        className="p-2 rounded-xl hover:bg-white/10 transition"
                    >
                        <X size={22} className="text-white" />
                    </button>

                </div>

                {/* User */}
                <div className="p-6 border-b border-white/10">

                    <div className="flex items-center gap-4">
                        {user?.avatarUrl ? (

                            <img
                                src={user.avatarUrl}
                                alt="avatar"
                                className="w-16 h-16 rounded-2xl object-cover"
                            />
                            //print the url


                        ) : (

                            <div className="w-16 h-16 rounded-2xl bg-white/10 flex items-center justify-center text-2xl font-bold text-white">
                                {user?.username?.[0]?.toUpperCase()}
                            </div>

                        )}

                        <div>

                            <h3 className="text-lg font-semibold text-white">
                                {user?.username}
                            </h3>

                            <p className="text-sm text-gray-500 break-all">
                                {user?.email}
                            </p>

                        </div>

                    </div>

                </div>

                {/* Navigation */}
                <div className="p-4 space-y-3">

                    <button className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl bg-white text-black font-medium hover:bg-gray-200 transition">
                        <Home size={20} />
                        Home
                    </button>

                    <button className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition text-gray-300">
                        <Video size={20} />
                        My Videos
                    </button>





                </div>

                {/* Footer */}
                <div className="absolute bottom-0 left-0 w-full p-5 border-t border-white/10">

                    <button
                        onClick={logout}
                        className="w-full bg-red-500/10 border border-red-500/20 text-red-300 hover:bg-red-500/20 transition py-4 rounded-2xl font-medium flex items-center justify-center gap-3"
                    >
                        <LogOut size={18} />
                        Logout
                    </button>

                </div>

            </aside>
        </>
    );
}