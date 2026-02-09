import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

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
        <div className="min-h-screen flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo and Title */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 mb-4">
                        <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-bold gradient-text">Daftar Akun</h1>
                    <p className="text-slate-400 mt-2">Bergabung dengan HR Agent</p>
                </div>

                {/* Register Form */}
                <div className="glass rounded-2xl p-8">
                    {displayError && (
                        <div className="mb-4 p-3 rounded-lg bg-red-500/20 border border-red-500/50 text-red-300 text-sm">
                            {displayError}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Nama Lengkap
                            </label>
                            <input
                                type="text"
                                name="fullName"
                                value={formData.fullName}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Masukkan nama lengkap"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Username
                            </label>
                            <input
                                type="text"
                                name="username"
                                value={formData.username}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Pilih username"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Email
                            </label>
                            <input
                                type="email"
                                name="email"
                                value={formData.email}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Masukkan email"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                name="password"
                                value={formData.password}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Minimal 6 karakter"
                                required
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Konfirmasi Password
                            </label>
                            <input
                                type="password"
                                name="confirmPassword"
                                value={formData.confirmPassword}
                                onChange={handleChange}
                                className="w-full px-4 py-3 rounded-lg bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:border-primary-500 transition-colors"
                                placeholder="Ulangi password"
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
                                'Daftar'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center text-sm text-slate-400">
                        Sudah punya akun?{' '}
                        <Link to="/login" className="text-primary-400 hover:text-primary-300 font-medium">
                            Masuk di sini
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Register;
