/**
 * Token utility for proactive JWT refresh
 * This ensures WebSocket messages always use valid tokens
 */

const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Buffer time (in seconds) before expiry to trigger refresh
const EXPIRY_BUFFER_SECONDS = 60;

/**
 * Decode JWT payload without verifying signature
 */
function decodeJWT(token: string): { exp?: number; email?: string } | null {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
            atob(base64)
                .split('')
                .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                .join('')
        );
        return JSON.parse(jsonPayload);
    } catch {
        return null;
    }
}

/**
 * Check if token is expiring soon (within buffer time)
 */
function isTokenExpiringSoon(token: string): boolean {
    const payload = decodeJWT(token);
    if (!payload?.exp) return true;

    const nowInSeconds = Math.floor(Date.now() / 1000);
    const timeUntilExpiry = payload.exp - nowInSeconds;

    console.log(`[TokenUtils] Token expires in ${timeUntilExpiry} seconds`);
    return timeUntilExpiry < EXPIRY_BUFFER_SECONDS;
}

/**
 * Refresh the access token using refresh token
 */
async function refreshAccessToken(): Promise<string | null> {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

    if (!refreshToken) {
        console.error('[TokenUtils] No refresh token available');
        return null;
    }

    try {
        console.log('[TokenUtils] Refreshing access token...');
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });

        if (!response.ok) {
            throw new Error(`Refresh failed with status ${response.status}`);
        }

        const data = await response.json();
        const newToken = data.access_token;

        if (newToken) {
            localStorage.setItem(TOKEN_KEY, newToken);
            console.log('[TokenUtils] Token refreshed successfully');
            return newToken;
        }

        return null;
    } catch (error) {
        console.error('[TokenUtils] Failed to refresh token:', error);
        // Clear all tokens and redirect to login
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem('hr_user');
        window.location.href = '/login';
        return null;
    }
}

/**
 * Get a valid access token, refreshing if necessary
 * This should be called before any WebSocket message
 */
export async function getValidToken(): Promise<string | null> {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
        console.warn('[TokenUtils] No access token found');
        return null;
    }

    // Check if token is expiring soon
    if (isTokenExpiringSoon(token)) {
        console.log('[TokenUtils] Token expiring soon, refreshing...');
        return await refreshAccessToken();
    }

    return token;
}

/**
 * Setup periodic token check (every 30 seconds)
 * Call this once on app initialization
 */
let tokenCheckInterval: ReturnType<typeof setInterval> | null = null;

export function startTokenAutoRefresh(): void {
    // Clear existing interval if any
    if (tokenCheckInterval) {
        clearInterval(tokenCheckInterval);
    }

    // Check every 30 seconds
    tokenCheckInterval = setInterval(async () => {
        const token = localStorage.getItem(TOKEN_KEY);
        if (token && isTokenExpiringSoon(token)) {
            console.log('[TokenUtils] Periodic check: Token expiring, refreshing...');
            await refreshAccessToken();
        }
    }, 30000);

    console.log('[TokenUtils] Auto-refresh started');
}

export function stopTokenAutoRefresh(): void {
    if (tokenCheckInterval) {
        clearInterval(tokenCheckInterval);
        tokenCheckInterval = null;
        console.log('[TokenUtils] Auto-refresh stopped');
    }
}
