import { useChatStore } from "../store/chatStore";

export function LoadingIndicator() {
    const statusText = useChatStore(state => state.statusText) || "Memproses...";

    return (
        <div className="flex justify-start animate-fade-in group py-2">
            <div className="flex items-center gap-3">
                {/* Assistant Icon */}
                <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
                    <svg className="w-6 h-6 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                </div>

                {/* Status Text & Dots */}
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-primary-400 uppercase tracking-[0.2em] animate-pulse">
                        {statusText}
                    </span>
                    <div className="typing-indicator flex items-center gap-1 ml-1">
                        <span className="w-1 h-1 bg-primary-500/60 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                        <span className="w-1 h-1 bg-primary-500/60 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                        <span className="w-1 h-1 bg-primary-500/60 rounded-full animate-bounce"></span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default LoadingIndicator;
