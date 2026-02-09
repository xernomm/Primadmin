import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuthStore } from './store/authStore';
import { startTokenAutoRefresh, stopTokenAutoRefresh } from './utils/tokenUtils';
import Login from './pages/Login';
import Register from './pages/Register';
import Chat from './pages/Chat';

function PrivateRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated } = useAuthStore();

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
}

function App() {
    const { checkAuth, isAuthenticated } = useAuthStore();

    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    // Start token auto-refresh when authenticated
    useEffect(() => {
        if (isAuthenticated) {
            startTokenAutoRefresh();
        } else {
            stopTokenAutoRefresh();
        }

        return () => stopTokenAutoRefresh();
    }, [isAuthenticated]);

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route
                    path="/chat"
                    element={
                        <PrivateRoute>
                            <Chat />
                        </PrivateRoute>
                    }
                />
                <Route path="/" element={<Navigate to="/chat" replace />} />
                <Route path="*" element={<Navigate to="/chat" replace />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
