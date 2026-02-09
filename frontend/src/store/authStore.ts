import { create } from 'zustand';
import type { User } from '../types';
import { authApi } from '../api/auth';

// Token key in localStorage - SINGLE SOURCE OF TRUTH
const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'hr_user';

interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;

    login: (username: string, password: string) => Promise<void>;
    register: (username: string, email: string, password: string, fullName: string) => Promise<void>;
    logout: () => void;
    checkAuth: () => Promise<void>;
    clearError: () => void;
    getToken: () => string | null;
    getRefreshToken: () => string | null;
    updateAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
    user: (() => {
        if (typeof window === 'undefined') return null;
        try {
            const stored = localStorage.getItem(USER_KEY);
            return stored ? JSON.parse(stored) : null;
        } catch {
            return null;
        }
    })(),
    isAuthenticated: typeof window !== 'undefined' ? !!localStorage.getItem(TOKEN_KEY) : false,
    isLoading: false,
    error: null,

    login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await authApi.login({ username, password });

            // Debug: log the response
            console.log('Login response:', response);
            console.log('Access token:', response.access_token);
            console.log('User:', response.user);

            // Check if access_token exists
            if (!response.access_token) {
                console.error('No access_token in response!');
                throw new Error('No access_token received from server');
            }

            // Save tokens
            try {
                localStorage.setItem(TOKEN_KEY, response.access_token);
                localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
                console.log('Tokens saved to localStorage');
            } catch (storageError) {
                console.error('Error saving tokens to localStorage:', storageError);
                throw storageError;
            }

            // Save user as JSON
            try {
                localStorage.setItem(USER_KEY, JSON.stringify(response.user));
                console.log('User saved to localStorage');
            } catch (storageError) {
                console.error('Error saving user to localStorage:', storageError);
            }

            set({
                user: response.user,
                isAuthenticated: true,
                isLoading: false,
            });

            console.log('Auth state updated');
        } catch (error: unknown) {
            console.error('Login error:', error);
            const errorMessage = (error as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Login gagal';
            set({ error: errorMessage, isLoading: false });
            throw error;
        }
    },

    register: async (username: string, email: string, password: string, fullName: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await authApi.register({
                username,
                email,
                password,
                full_name: fullName,
            });

            console.log('Register response:', response);

            if (!response.access_token) {
                throw new Error('No access_token received from server');
            }

            localStorage.setItem(TOKEN_KEY, response.access_token);
            localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
            localStorage.setItem(USER_KEY, JSON.stringify(response.user));

            set({
                user: response.user,
                isAuthenticated: true,
                isLoading: false,
            });
        } catch (error: unknown) {
            console.error('Register error:', error);
            const errorMessage = (error as { response?: { data?: { error?: string } } })?.response?.data?.error || 'Registrasi gagal';
            set({ error: errorMessage, isLoading: false });
            throw error;
        }
    },

    logout: () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        set({
            user: null,
            isAuthenticated: false,
        });
    },

    checkAuth: async () => {
        const token = localStorage.getItem(TOKEN_KEY);
        console.log('checkAuth - token from localStorage:', token);

        if (!token) {
            set({ isAuthenticated: false, user: null });
            return;
        }

        try {
            const user = await authApi.getMe();
            localStorage.setItem(USER_KEY, JSON.stringify(user));
            set({
                user,
                isAuthenticated: true,
            });
        } catch (error) {
            console.error('checkAuth error:', error);
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            set({
                user: null,
                isAuthenticated: false,
            });
        }
    },

    getToken: () => localStorage.getItem(TOKEN_KEY),

    getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),

    updateAccessToken: (token: string) => {
        localStorage.setItem(TOKEN_KEY, token);
        set({ isAuthenticated: true });
    },

    clearError: () => set({ error: null }),
}));

export default useAuthStore;
