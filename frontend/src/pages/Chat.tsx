import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useChatStore } from '../store/chatStore';
import Sidebar from '../components/Sidebar';
import ChatWindow from '../components/ChatWindow';
import InputArea from '../components/InputArea';
import PoliciesPanel from '../components/PoliciesPanel';
import PrimaLogo from '../img/primalogo.png';
import BackgroundImg from '../img/Background-vankaai.png';

export function Chat() {
    const navigate = useNavigate();
    const { user, isAuthenticated, logout } = useAuthStore();
    const messages = useChatStore((state) => state.messages);
    const isLoading = useChatStore((state) => state.isLoading);
    const sendMessage = useChatStore((state) => state.sendMessage);
    const abortRequest = useChatStore((state) => state.abortRequest);
    const loadConversations = useChatStore((state) => state.loadConversations);
    const currentConversationId = useChatStore((state) => state.currentConversationId);
    const initSocket = useChatStore((state) => state.initSocket);

    const [sidebarOpen, setSidebarOpen] = useState(true);
    const [policiesOpen, setPoliciesOpen] = useState(false);
    const [inputText, setInputText] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const hasLoadedConversations = useRef(false);

    // Initialize Socket (only once on mount, cleanup on unmount)
    useEffect(() => {
        initSocket();

        // Cleanup on unmount
        return () => {
            useChatStore.getState().disconnectSocket();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Redirect to login if not authenticated
    useEffect(() => {
        if (!isAuthenticated) {
            navigate('/login');
        }
    }, [isAuthenticated, navigate]);

    // Load conversations when authenticated
    useEffect(() => {
        if (isAuthenticated && !hasLoadedConversations.current) {
            hasLoadedConversations.current = true;
            loadConversations();
        }
    }, [isAuthenticated, loadConversations]);

    // Reset on logout
    useEffect(() => {
        if (!isAuthenticated) {
            hasLoadedConversations.current = false;
        }
    }, [isAuthenticated]);

    // Scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async (message: string, file?: File) => {
        if ((!message.trim() && !file) || isLoading) return;
        setInputText(''); // Clear input after send

        let filePath: string | undefined;
        let fileAttachment: { filename: string; size: number; type: string } | undefined;

        // Upload file first if attached
        if (file) {
            try {
                const { getValidToken } = await import('../utils/tokenUtils');
                const token = await getValidToken();
                const formData = new FormData();
                formData.append('file', file);

                const resp = await fetch('/api/upload/cv', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    body: formData
                });
                const result = await resp.json();
                if (result.success) {
                    filePath = result.file_path;
                    fileAttachment = {
                        filename: file.name,
                        size: file.size,
                        type: file.name.split('.').pop()?.toLowerCase() || 'file',
                    };
                }
            } catch (err) {
                console.error('File upload failed:', err);
            }
        }

        const messageToSend = filePath ? `${message} [file_attached: ${filePath}]` : message;

        await sendMessage(
            messageToSend,
            currentConversationId || undefined,
            fileAttachment
        );
    };

    const handleSuggestionClick = (text: string) => {
        setInputText(text);
    };

    const handleLogout = () => {
        hasLoadedConversations.current = false;
        logout();
        navigate('/login');
    };

    if (!isAuthenticated) {
        return null;
    }

    return (
        <div
            className="flex h-screen overflow-hidden"
            style={{
                // backgroundImage: `url(${BackgroundImg})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                backgroundColor: '#181818'
            }}
        >
            {/* Sidebar */}
            <Sidebar
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
                user={user}
                onLogout={handleLogout}
                onOpenPolicies={() => setPoliciesOpen(true)}
            />

            {/* Policies Panel Modal */}
            <PoliciesPanel
                isOpen={policiesOpen}
                onClose={() => setPoliciesOpen(false)}
            />

            {/* Main Chat Area */}
            <main className="flex-1 flex flex-col min-w-0">
                {/* Header */}
                <header className="h-14 border-b border-slate-700/50 flex items-center justify-between px-4 glass-dark">
                    <div className="flex items-center gap-3">
                        {!sidebarOpen && (
                            <button
                                onClick={() => setSidebarOpen(true)}
                                className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                            >
                                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                                </svg>
                            </button>
                        )}
                        <img src={PrimaLogo} alt="Primassistant" className="w-7 h-7 object-contain" />
                        <h1 className="text-lg font-semibold text-white">Primassistant</h1>
                    </div>

                    <div className="flex items-center gap-2 text-sm text-slate-400 min-w-[100px] justify-end">
                        {isLoading && (
                            <div className="flex items-center gap-2 animate-fade-in">
                                <div className="spinner-sm"></div>
                                <span>Memproses...</span>
                            </div>
                        )}
                    </div>
                </header>

                {/* Chat Window */}
                <div className="flex-1 overflow-hidden">
                    <ChatWindow
                        messages={messages}
                        isLoading={isLoading}
                        onSuggestionClick={handleSuggestionClick}
                        sidebarOpen={sidebarOpen}
                    />
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <InputArea
                    onSend={handleSend}
                    onStop={abortRequest}
                    disabled={isLoading}
                    inputValue={inputText}
                    onInputChange={setInputText}
                />
            </main>
        </div>
    );
}

export default Chat;
