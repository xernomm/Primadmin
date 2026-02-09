import type { Message } from '../types';
import MessageBubble from './MessageBubble';
import ProcessingBlock from './ProcessingBlock';
import { useChatStore } from '../store/chatStore';
import VankaLogo from '../img/Vanka-logo.png';


interface ChatWindowProps {
    messages: Message[];
    isLoading: boolean;
    onSuggestionClick?: (text: string) => void;
}

export function ChatWindow({ messages, isLoading, onSuggestionClick }: ChatWindowProps) {
    const { stageData, statusText } = useChatStore();

    if (messages.length === 0 && !isLoading) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8">
                <div className=" flex items-center justify-center mb-6 ">
                    <img src={VankaLogo} alt="Vanka AI" className="w-40 h-40 object-contain" />
                </div>

                <h2 className="text-2xl font-bold text-white mb-2 tracking-tight">Selamat Datang di Primassistant</h2>
                <p className="text-hr-muted text-center max-w-md mb-8 leading-relaxed">
                    Saya adalah asisten AI yang membantu Anda mengelola data HR.
                    Tanyakan apapun tentang karyawan, absensi, atau surat peringatan.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-lg w-full">
                    <SuggestionCard
                        icon="👥"
                        text="Tampilkan daftar semua karyawan"
                        onClick={onSuggestionClick}
                    />
                    <SuggestionCard
                        icon="📅"
                        text="Cek absensi hari ini"
                        onClick={onSuggestionClick}
                    />
                    <SuggestionCard
                        icon="📋"
                        text="Lihat kebijakan cuti"
                        onClick={onSuggestionClick}
                    />
                    <SuggestionCard
                        icon="⚠️"
                        text="Cara membuat surat peringatan"
                        onClick={onSuggestionClick}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => (
                <MessageBubble
                    key={message.id || index}
                    message={message}
                />
            ))}

            {/* Show ProcessingBlock during loading instead of simple LoadingIndicator */}
            {isLoading && (
                <ProcessingBlock
                    stages={stageData}
                    currentStatus={statusText}
                />
            )}
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
