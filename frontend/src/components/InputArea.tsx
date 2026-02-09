import { useState, KeyboardEvent, useRef, useEffect } from 'react';

interface InputAreaProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    inputValue?: string;
    onInputChange?: (value: string) => void;
}

export function InputArea({ onSend, disabled, inputValue, onInputChange }: InputAreaProps) {
    const [internalMessage, setInternalMessage] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Use external value if provided, otherwise use internal state
    const message = inputValue !== undefined ? inputValue : internalMessage;
    const setMessage = onInputChange || setInternalMessage;

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
        }
    }, [message]);

    const handleSend = () => {
        if (message.trim() && !disabled) {
            onSend(message);
            setMessage('');
            // Also reset internal state if using external control
            if (inputValue !== undefined) {
                setInternalMessage('');
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="border-t border-hr-card p-4 glass-dark bg-hr-darker">
            <div className="max-w-4xl mx-auto">
                <div className="relative flex items-end gap-2">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Ketik pesan Anda... (Enter untuk kirim, Shift+Enter untuk baris baru)"
                            disabled={disabled}
                            rows={1}
                            className="w-full px-4 py-3 pr-12 rounded-xl bg-hr-card border border-hr-accent text-hr-text placeholder-zinc-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all resize-none disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                    </div>

                    <button
                        onClick={handleSend}
                        disabled={disabled || !message.trim()}
                        className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white flex items-center justify-center transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-primary-500/25"
                    >
                        {disabled ? (
                            <div className="spinner"></div>
                        ) : (
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        )}
                    </button>
                </div>

                <p className="text-xs text-slate-500 mt-2 text-center">
                    HR Agent dapat membantu dengan data karyawan, absensi, dan surat peringatan
                </p>
            </div>
        </div>
    );
}

export default InputArea;
