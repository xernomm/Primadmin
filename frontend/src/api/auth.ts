import client from './client';
import type { LoginRequest, RegisterRequest, AuthResponse, User, RefreshResponse } from '../types';

export const authApi = {
    login: async (data: LoginRequest): Promise<AuthResponse> => {
        const response = await client.post<AuthResponse>('/auth/login', data);
        return response.data;
    },

    register: async (data: RegisterRequest): Promise<AuthResponse> => {
        const response = await client.post<AuthResponse>('/auth/register', data);
        return response.data;
    },

    getMe: async (): Promise<User> => {
        const response = await client.get<User>('/auth/me');
        return response.data;
    },

    refreshToken: async (token: string): Promise<RefreshResponse> => {
        const response = await client.post<RefreshResponse>('/auth/refresh', {}, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });
        return response.data;
    },

    changePassword: async (currentPassword: string, newPassword: string): Promise<{ message: string }> => {
        const response = await client.post('/auth/change-password', {
            current_password: currentPassword,
            new_password: newPassword,
        });
        return response.data;
    },
};

export default authApi;
