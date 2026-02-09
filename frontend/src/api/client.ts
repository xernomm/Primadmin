import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const TOKEN_KEY = 'access_token';

// Create axios instance
const client: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 60000, // 60 seconds for LLM responses
});

// Request interceptor - add auth token
client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem(TOKEN_KEY);
        console.log('Axios request to:', config.url, '| Token:', token ? 'present' : 'missing');
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error: AxiosError) => {
        return Promise.reject(error);
    }
);

// Response interceptor - handle errors
client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
        console.log('Axios error:', error.response?.status, 'for URL:', originalRequest?.url);

        // Handle 401 errors
        if (error.response?.status === 401 && !originalRequest._retry) {
            const url = originalRequest.url || '';

            // If it's an auth endpoint (login, register, refresh), don't retry
            if (url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh')) {
                return Promise.reject(error);
            }

            originalRequest._retry = true;
            const refreshToken = localStorage.getItem('refresh_token');

            if (refreshToken) {
                try {
                    console.log('Attempting to refresh token...');
                    // Use a clean axios call to avoid interceptors for the refresh call
                    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });

                    const { access_token } = response.data;
                    localStorage.setItem(TOKEN_KEY, access_token);

                    console.log('Token refreshed successfully');

                    // Update the original request's auth header
                    if (originalRequest.headers) {
                        originalRequest.headers.Authorization = `Bearer ${access_token}`;
                    }

                    // Retry the original request
                    return client(originalRequest);
                } catch (refreshError) {
                    console.error('Failed to refresh token:', refreshError);
                    // Clear tokens and logout if refresh fails
                    localStorage.removeItem(TOKEN_KEY);
                    localStorage.removeItem('refresh_token');
                    localStorage.removeItem('hr_user');
                    // We could also trigger a redirect here, but better to let the app state handle it
                    window.location.href = '/login';
                    return Promise.reject(refreshError);
                }
            }
        }

        return Promise.reject(error);
    }
);

export default client;
