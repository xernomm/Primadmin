import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import PrimaLogo from '../img/primalogo.png';
import LoginBg from '../img/login_bg_decoration.png';

export function Register() {
    const navigate = useNavigate();
    const { register, isLoading, error, clearError } = useAuthStore();

    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        confirmPassword: '',
        fullName: '',
    });
    const [validationError, setValidationError] = useState('');

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
        setValidationError('');
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();
        setValidationError('');

        // Validate passwords match
        if (formData.password !== formData.confirmPassword) {
            setValidationError('Password tidak cocok');
            return;
        }

        // Validate password length
        if (formData.password.length < 6) {
            setValidationError('Password minimal 6 karakter');
            return;
        }

        try {
            await register(
                formData.username,
                formData.email,
                formData.password,
                formData.fullName
            );
            navigate('/chat');
        } catch {
            // Error is handled in store
        }
    };

    const displayError = validationError || error;

    return (
        <div className="min-h-screen w-full flex items-center justify-center p-4 lg:p-12 relative overflow-hidden bg-hr-dark">
            {/* Background Decorations 
            <div className="absolute inset-0 opacity-20 pointer-events-none">
                <img src={LoginBg} alt="" className="w-full h-full object-cover" />
            </div> */}
            <div className="absolute top-[20%] left-[-10%] w-[40%] h-[40%] bg-hr-accent rounded-full blur-[100px] pointer-events-none"></div>
            <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-hr-accent rounded-full blur-[120px] pointer-events-none"></div>

            <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-16 items-center relative z-10">
                {/* Left: Register Box */}
                <div className="w-full max-w-md mx-auto lg:ml-auto lg:mr-0 order-2 lg:order-1">
                    <div className="glass-dark rounded-3xl p-8 lg:p-10 shadow-2xl border border-white/10">
                        <div className="mb-6">
                            <h2 className="text-3xl font-bold text-white mb-2">Create Account</h2>
                            <p className="text-zinc-400">Mulailah perjalanan HR cerdas Anda</p>
                        </div>

                        {displayError && (
                            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-3 animate-fade-in">
                                <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                {displayError}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-1 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                        Nama Lengkap
                                    </label>
                                    <input
                                        type="text"
                                        name="fullName"
                                        value={formData.fullName}
                                        onChange={handleChange}
                                        className="w-full px-5 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                        placeholder="Nama lengkap"
                                        required
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                            Username
                                        </label>
                                        <input
                                            type="text"
                                            name="username"
                                            value={formData.username}
                                            onChange={handleChange}
                                            className="w-full px-5 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                            placeholder="User"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                            Email
                                        </label>
                                        <input
                                            type="email"
                                            name="email"
                                            value={formData.email}
                                            onChange={handleChange}
                                            className="w-full px-5 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                            placeholder="mail@e.com"
                                            required
                                        />
                                    </div>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    name="password"
                                    value={formData.password}
                                    onChange={handleChange}
                                    className="w-full px-5 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-300 mb-2 ml-1">
                                    Konfirmasi Password
                                </label>
                                <input
                                    type="password"
                                    name="confirmPassword"
                                    value={formData.confirmPassword}
                                    onChange={handleChange}
                                    className="w-full px-5 py-3 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-zinc-600 focus:border-primary-500/50 focus:bg-white/10 transition-all outline-none"
                                    placeholder="••••••••"
                                    required
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={isLoading}
                                className="w-full py-4 rounded-2xl bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white font-bold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-xl shadow-primary-900/20 active:scale-[0.98] mt-4 flex items-center justify-center"
                            >
                                {isLoading ? (
                                    <>
                                        <div className="spinner-sm mr-3"></div>
                                        Membuat Akun...
                                    </>
                                ) : (
                                    'Daftar Sekarang'
                                )}
                            </button>
                        </form>

                        <div className="mt-8 pt-6 border-t border-white/5 text-center">
                            <p className="text-zinc-400 text-sm">
                                Sudah punya akun?{' '}
                                <Link to="/login" className="text-primary-400 hover:text-primary-300 font-bold ml-1 transition-colors">
                                    Masuk di sini
                                </Link>
                            </p>
                        </div>
                    </div>
                </div>

                {/* Right: Branding Section */}
                <div className="hidden lg:flex flex-col items-center lg:items-start text-center lg:text-left order-1 lg:order-2">
                    <div className="mb-8 flex w-full justify-center lg:justify-start">
                        <img src={PrimaLogo} alt="Primassistant Logo" className="w-1/2 md:w-48 lg:w-64 object-contain" />
                    </div>
                    <h1 className="text-5xl lg:text-6xl font-black text-white mb-6 tracking-tight">
                        Primassistant<span className="text-primary-500">.</span>
                    </h1>
                    <div className="max-w-md">
                        <p className="text-xl text-zinc-400 leading-relaxed">
                            Manajemen SDM masa depan dimulai hari ini. Daftarkan tim Anda sekarang.
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
                                <p className="text-white font-bold font-mono">Powered by Qwen & MCP</p>
                                <p className="text-zinc-500">Agentic Orchestrator, qwen3 & qwen2.5-coder</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Mobile Branding */}
                <div className="lg:hidden text-center mb-4 order-1">
                    <img src={PrimaLogo} alt="Primassistant" className="w-16 h-16 mx-auto mb-4" />
                    <h1 className="text-4xl font-black text-white mb-2">Primassistant</h1>
                </div>
            </div>
        </div>
    );
}

export default Register;
