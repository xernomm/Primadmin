import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export function Login() {
    const navigate = useNavigate();
    const { login, isLoading, error, clearError } = useAuthStore();

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();

        try {
            // login() now waits for token to be fully saved before resolving
            await login(username, password);
            // Only navigate after token is verified saved
            navigate('/chat');
        } catch {
            // Error is handled in store
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo and Title */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 mb-4 animate-pulse-glow">
                        <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-bold gradient-text">HR Agent</h1>
                    <p className="text-slate-400 mt-2">AI-Powered HR Management System</p>
                </div>

                {/* Login Form */}
                <div className="glass rounded-2xl p-8">
                    <h2 className="text-xl font-semibold text-white mb-6">Masuk ke Akun Anda</h2>

                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-red-500/20 border border-red-500/50 text-red-300 text-sm">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Username atau Email
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Masukkan username atau email"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Masukkan password"
                                required
                            />
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full py-3 rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                        >
                            {isLoading ? (
                                <>
                                    <div className="spinner mr-2"></div>
                                    Memproses...
                                </>
                            ) : (
                                'Masuk'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center text-sm text-slate-400">
                        Belum punya akun?{' '}
                        <Link to="/register" className="text-primary-400 hover:text-primary-300 font-medium">
                            Daftar sekarang
                        </Link>
                    </div>
                </div>

                {/* Demo credentials */}
                <div className="mt-6 p-4 rounded-lg bg-slate-800/30 border border-slate-700/50">
                    <p className="text-xs text-slate-500 mb-2">Demo Credentials:</p>
                    <div className="text-xs text-slate-400 space-y-1">
                        <p><span className="text-slate-500">Admin:</span> admin / admin123</p>
                        <p><span className="text-slate-500">HR Manager:</span> hr_manager / manager123</p>
                        <p><span className="text-slate-500">HR Staff:</span> hr_staff / staff123</p>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Login;
