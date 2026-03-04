import { useRef, useEffect } from 'react';
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
    const statusText = useChatStore((state) => state.statusText);
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

    const lastMessage = messages[messages.length - 1];
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages.length, lastMessage?.content, isLoading, statusText, stageData, subEvents]);

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
        <div className="h-full overflow-y-auto">
            {/* 3-column grid: empty | chat | empty
                When sidebar is open, the side cols are slightly wider to keep chat compact.
                When sidebar is closed, side cols shrink to give chat more space — 
                but still centered to avoid feeling too spread. */}
            <div className={`grid transition-all duration-300 ${sidebarOpen
                ? 'grid-cols-[1fr_3fr_1fr]'
                : 'grid-cols-[1fr_4fr_1fr]'
                }`}>

                {/* Left spacer */}
                <div />

                {/* Center: chat content */}
                <div className="flex flex-col py-4 space-y-4 min-h-full min-w-0">
                    {messages.map((message, index) => (
                        <MessageBubble
                            key={message.id || index}
                            message={message}
                        />
                    ))}

                    {isLoading && (
                        <ProcessingBlock
                            stages={stageData}
                            currentStatus={statusText}
                            subEvents={subEvents}
                        />
                    )}

                    <div ref={bottomRef} />
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
