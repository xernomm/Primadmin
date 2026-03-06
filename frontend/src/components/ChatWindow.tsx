import { useRef, useEffect, useState } from 'react';
import type { Message } from '../types';
import MessageBubble from './MessageBubble';
import ProcessingBlock from './ProcessingBlock';
import { useChatStore } from '../store/chatStore';
import VankaLogo from '../img/Vanka-logo.png';


interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSuggestionClick?: (text: string) => void;
    sidebarOpen?: boolean;
}

const EMPTY_STAGES: any[] = [];

export function ChatWindow({ messages, isLoading, onSuggestionClick, sidebarOpen = true }: ChatWindowProps) {
    const bottomRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [showScrollButton, setShowScrollButton] = useState(false);

    const statusText = useChatStore((state) => state.statusText);
    const isGeneratingResponse = useChatStore((state) => state.isGeneratingResponse);
    const stageData = useChatStore((state) => {
        const targetId = state.processingConversationId ?? state.currentConversationId;
        if (targetId !== null && state.stageDataByConversation[targetId]) {
            return state.stageDataByConversation[targetId];
        }
        return EMPTY_STAGES;
    });
    const subEvents = useChatStore((state) => {
        const targetId = state.processingConversationId ?? state.currentConversationId;
        if (targetId !== null && state.subStatusByConversation[targetId]) {
            return state.subStatusByConversation[targetId];
        }
        return EMPTY_STAGES;
    });

    const isNearBottom = () => {
        if (!containerRef.current) return true;
        const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
        // Consider "near bottom" if within 100px of the bottom
        return scrollHeight - scrollTop - clientHeight < 100;
    };

    const handleScroll = () => {
        setShowScrollButton(!isNearBottom());
    };

    const scrollToBottom = () => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const lastMessage = messages[messages.length - 1];

    // Auto-scroll on new messages or status changes ONLY if already near bottom
    useEffect(() => {
        // If we are already near the bottom, or if we just started loading (new request), auto scroll
        if (isNearBottom() || isLoading) {
            scrollToBottom();
        }
    }, [messages.length, lastMessage?.content, isLoading, isGeneratingResponse, statusText, stageData, subEvents]);

    if (messages.length === 0 && !isLoading) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8">
                <div className="flex items-center justify-center mb-6">
                    <img src={VankaLogo} alt="Vanka AI" className="w-40 h-40 object-contain" />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2 tracking-tight">Selamat Datang di Primassistant</h2>
                <p className="text-hr-muted text-center max-w-md mb-8 leading-relaxed">
                    Saya adalah asisten AI yang membantu Anda mengelola data HR.
                    Tanyakan apapun tentang karyawan, absensi, atau surat peringatan.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg w-full">
                    <SuggestionCard icon="👥" text="Tampilkan daftar semua karyawan" onClick={onSuggestionClick} />
                    <SuggestionCard icon="📅" text="Cek absensi hari ini" onClick={onSuggestionClick} />
                    <SuggestionCard icon="📋" text="Lihat kebijakan cuti" onClick={onSuggestionClick} />
                    <SuggestionCard icon="⚠️" text="Cara membuat surat peringatan" onClick={onSuggestionClick} />
                </div>
            </div>
        );
    }

    return (
        <div
            className="h-full overflow-y-auto relative"
            ref={containerRef}
            onScroll={handleScroll}
        >
            {/* 3-column grid: empty | chat | empty
                When sidebar is open, the side cols are slightly wider to keep chat compact.
                When sidebar is closed, side cols shrink to give chat more space —
                but still centered to avoid feeling too spread. */}
            <div className={`grid transition-all duration-300 min-h-full ${sidebarOpen
                ? 'grid-cols-[1fr_3fr_1fr]'
                : 'grid-cols-[1fr_4fr_1fr]'
                }`}>

                {/* Left spacer */}
                <div />

                {/* Center: chat content */}
                <div className="flex flex-col py-4 space-y-4 min-w-0 relative">
                    {messages.map((message, index) => (
                        <MessageBubble
                            key={message.id || index}
                            message={message}
                        />
                    ))}

                    {isLoading && !isGeneratingResponse && (
                        <ProcessingBlock
                            stages={stageData}
                            currentStatus={statusText}
                            subEvents={subEvents}
                        />
                    )}

                    <div ref={bottomRef} className="h-4" /> {/* Added small height so scrolling reaches entirely past the last item */}

                    {/* Scroll to bottom button (centered relative to this chat column) */}
                    {showScrollButton && (
                        <div className="sticky bottom-4 left-0 right-0 flex justify-center z-50 pointer-events-none mb-10">
                            <button
                                onClick={scrollToBottom}
                                className="pointer-events-auto p-2 bg-zinc-800/90 hover:bg-zinc-700 text-zinc-300 rounded-full shadow-lg border border-white/10 transition-all animate-fade-in hover:scale-105"
                                aria-label="Scroll to bottom"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                                </svg>
                            </button>
                        </div>
                    )}
                </div>

                {/* Right spacer */}
                <div />
            </div>
        </div>
    );
}

function SuggestionCard({ icon, text, onClick }: { icon: string; text: string; onClick?: (text: string) => void }) {
    return (
        <div
            className="p-4 rounded-xl hover:bg-hr-accent border border-white/50 cursor-pointer transition-all duration-200 group hover:shadow-lg hover:shadow-primary-500/5 hover:-translate-y-0.5"
            onClick={() => onClick?.(text)}
        >
            <span className="text-2xl mb-2 block">{icon}</span>
            <p className="text-sm text-hr-muted group-hover:text-white transition-colors font-medium">
                {text}
            </p>
        </div>
    );
}

export default ChatWindow;
