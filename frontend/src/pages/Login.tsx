import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import PrimaLogo from '../img/primalogo.png';
import LoginBg from '../img/login_bg_decoration.png';

export function Login() {
    const navigate = useNavigate();
    const { login, isLoading, error, clearError } = useAuthStore();

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();

        try {
            await login(username, password);
            navigate('/chat');
        } catch {
            // Error is handled in store
        }
    };

    return (
        <div className="min-h-screen w-full flex items-center justify-center p-4 lg:p-12 relative overflow-hidden bg-[#0a0a0aff]">
            {/* Background Decorations */}
            <div className="absolute inset-0 opacity-20 pointer-events-none">
                <img src={LoginBg} alt="" className="w-full h-full object-cover" />
            </div>
            <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-primary-600/20 rounded-full blur-[120px] pointer-events-none"></div>
            <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/20 rounded-full blur-[120px] pointer-events-none"></div>

            <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-16 items-center relative z-10">
                {/* Left: Login Box */}
                <div className="w-full max-w-md mx-auto lg:ml-auto lg:mr-0 order-2 lg:order-1">
                    <div className="glass-dark rounded-3xl p-8 lg:p-10 shadow-2xl border border-white/10">
                        <div className="mb-8">
                            <h2 className="text-3xl font-bold text-white mb-2">Welcome Back</h2>
                            <p className="text-zinc-400">Masuk ke dashboard HR Anda</p>
                        </div>

                        {error && (
                            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-3 animate-fade-in">
                                <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                    Username atau Email
                                </label>
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="w-full px-5 py-4 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                    placeholder="Masukkan username anda"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full px-5 py-4 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>

                            <div className="flex items-center justify-between text-sm px-1">
                                <label className="flex items-center gap-2 text-zinc-400 cursor-pointer hover:text-zinc-200 transition-colors">
                                    <input type="checkbox" className="rounded border-white/10 bg-white/5 text-primary-600" />
                                    Ingat saya
                                </label>
                                <Link to="#" className="text-primary-400 hover:text-primary-300 transition-colors">
                                    Lupa password?
                                </Link>
                            </div>

                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full py-4 rounded-2xl bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white font-bold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-xl shadow-primary-900/20 active:scale-[0.98] mt-2 flex items-center justify-center"
                            >
                                {isLoading ? (
                                    <>
                                        <div className="spinner-sm mr-3"></div>
                                        Memproses...
                                    </>
                                ) : (
                                    'Masuk Ke Akun'
                                )}
                            </button>
                        </form>

                        <div className="mt-8 pt-8 border-t border-white/5 text-center">
                            <p className="text-zinc-400 text-sm">
                                Belum punya akun?{' '}
                                <Link to="/register" className="text-primary-400 hover:text-primary-300 font-bold ml-1 transition-colors">
                                    Daftar sekarang
                                </Link>
                            </p>
                        </div>
                    </div>

                    {/* Demo credentials */}
                    <div className="mt-6 p-5 rounded-2xl bg-white/5 border border-white/5 backdrop-blur-sm">
                        <div className="flex items-center gap-2 mb-3 text-zinc-500">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-xs uppercase tracking-wider font-bold">Demo Access</p>
                        </div>
                        <div className="grid grid-cols-1 gap-2 text-xs text-zinc-400">
                            <div className="flex justify-between p-2 rounded-lg bg-black/20">
                                <span className="text-zinc-500">Admin</span>
                                <span className="font-mono text-primary-400/80">admin / admin123</span>
                            </div>
                            <div className="flex justify-between p-2 rounded-lg bg-black/20">
                                <span className="text-zinc-500">HR Manager</span>
                                <span className="font-mono text-primary-400/80">hr_manager / manager123</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right: Branding Section */}
                <div className="hidden lg:flex flex-col items-center lg:items-start text-center lg:text-left order-1 lg:order-2">
                    <div className="mb-8 p-4 rounded-3xl bg-white/5 border border-white/10 inline-block animate-pulse-glow">
                        <img src={PrimaLogo} alt="Primassistant Logo" className="w-20 h-20 object-contain" />
                    </div>
                    <h1 className="text-5xl lg:text-6xl font-black text-white mb-6 tracking-tight">
                        Primassistant<span className="text-primary-500">.</span>
                    </h1>
                    <div className="max-w-md">
                        <p className="text-xl text-zinc-400 leading-relaxed">
                            Transformasi manajemen SDM dengan kecerdasan buatan terotomasi dan efisien.
                        </p>
                        <div className="mt-10 flex gap-4">
                            <div className="flex -space-x-3 overflow-hidden">
                                {[1, 2, 3, 4].map(i => (
                                    <div key={i} className="inline-block h-10 w-10 rounded-full ring-2 ring-zinc-900 bg-zinc-800 flex items-center justify-center text-[10px] font-bold text-zinc-500">
                                        HR
                                    </div>
                                ))}
                            </div>
                            <div className="text-sm">
                                <p className="text-white font-bold font-mono">10+ Model AI Terintegrasi</p>
                                <p className="text-zinc-500">Siap membantu operasional harian</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Mobile Branding (only show logo/name) */}
                <div className="lg:hidden text-center mb-4 order-1">
                    <img src={PrimaLogo} alt="Primassistant" className="w-16 h-16 mx-auto mb-4" />
                    <h1 className="text-4xl font-black text-white mb-2">Primassistant</h1>
                </div>
            </div>
        </div>
    );
}

export default Login;
