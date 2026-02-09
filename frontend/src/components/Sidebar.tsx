import { useChatStore } from '../store/chatStore';
import type { User, Conversation } from '../types';
import PrimaLogo from '../img/primalogo.png';

interface SidebarProps {
    isOpen: boolean;
    onToggle: () => void;
    user: User | null;
    onLogout: () => void;
    onOpenPolicies?: () => void;
}

export function Sidebar({ isOpen, onToggle, user, onLogout, onOpenPolicies }: SidebarProps) {
    const {
        conversations,
        currentConversationId,
        loadConversation,
        createNewConversation,
        deleteConversation
    } = useChatStore();

    // loadConversations is now called from Chat.tsx to avoid race condition

    const handleSelectConversation = (conv: Conversation) => {
        loadConversation(conv.id);
    };

    const handleDeleteConversation = (e: React.MouseEvent, convId: number) => {
        e.stopPropagation();
        if (window.confirm('Hapus percakapan ini?')) {
            deleteConversation(convId);
        }
    };

    if (!isOpen) return null;

    return (
        <aside className="w-72 h-full border-r border-slate-700/50 flex flex-col glass-dark">
            {/* Header */}
            <div className="h-14 border-b border-slate-700/50 flex items-center justify-between px-4">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center">
                        <img src={PrimaLogo} alt="Primassistant" className="w-7 h-7 object-contain" />
                    </div>
                    <span className="font-semibold text-white">Primassistant</span>
                </div>
                <button
                    onClick={onToggle}
                    className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
                >
                    <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                    </svg>
                </button>
            </div>

            {/* New Chat Button */}
            <div className="p-3 space-y-2">
                <button
                    onClick={createNewConversation}
                    className="w-full py-2.5 px-4 rounded-lg border border-slate-600 hover:bg-slate-700/50 text-slate-300 hover:text-white flex items-center justify-center gap-2 transition-all duration-200"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Chat Baru
                </button>

                {/* Policies Button */}
                <button
                    onClick={onOpenPolicies}
                    className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-primary-600/20 to-purple-600/20 border border-primary-500/30 hover:border-primary-500/50 text-slate-200 hover:text-white flex items-center justify-center gap-2 transition-all duration-200"
                >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Kebijakan Perusahaan
                </button>
            </div>

            {/* Conversations List */}
            <div className="flex-1 overflow-y-auto px-3">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2 px-2">
                    Riwayat Chat
                </p>

                {conversations.length === 0 ? (
                    <p className="text-sm text-slate-500 px-2 py-4 text-center">
                        Belum ada percakapan
                    </p>
                ) : (
                    <div className="space-y-1">
                        {conversations.map((conv) => (
                            <div
                                key={conv.id}
                                onClick={() => handleSelectConversation(conv)}
                                className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200 ${currentConversationId === conv.id
                                    ? 'bg-primary-500/20 text-white'
                                    : 'hover:bg-slate-700/50 text-slate-300'
                                    }`}
                            >
                                <svg className="w-4 h-4 flex-shrink-0 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                                </svg>
                                <span className="flex-1 text-sm truncate">
                                    {conv.title || 'New conversation'}
                                </span>
                                <button
                                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-600 rounded transition-all"
                                >
                                    <svg className="w-3.5 h-3.5 text-slate-400 hover:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* User Profile */}
            <div className="border-t border-slate-700/50 p-3">
                <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-700/30 transition-colors">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-500 to-purple-600 flex items-center justify-center text-white font-medium text-sm">
                        {user?.full_name?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                            {user?.full_name || 'User'}
                        </p>
                        <p className="text-xs text-slate-500 truncate">
                            {user?.role?.replace('_', ' ') || 'HR Staff'}
                        </p>
                    </div>
                    <button
                        onClick={onLogout}
                        className="p-2 hover:bg-slate-600/50 rounded-lg transition-colors"
                        title="Logout"
                    >
                        <svg className="w-4 h-4 text-slate-400 hover:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                    </button>
                </div>
            </div>
        </aside>
    );
}

export default Sidebar;
