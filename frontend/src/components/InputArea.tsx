import { useState, KeyboardEvent, useRef, useEffect } from 'react';

interface InputAreaProps {
    onSend: (message: string, file?: File) => void;
    onStop?: () => void;     // Stop the current agent run
    disabled?: boolean;
    inputValue?: string;
    onInputChange?: (value: string) => void;
}

export function InputArea({ onSend, onStop, disabled, inputValue, onInputChange }: InputAreaProps) {
    const [internalMessage, setInternalMessage] = useState('');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

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
        if ((message.trim() || selectedFile) && !disabled) {
            onSend(message, selectedFile || undefined);
            setMessage('');
            setSelectedFile(null);
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

    const handleFileClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setSelectedFile(file);
        }
        // Reset input so the same file can be selected again
        e.target.value = '';
    };

    const removeFile = () => {
        setSelectedFile(null);
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="p-4 ">
            <div className="max-w-4xl mx-auto">
                {/* File attachment chip */}
                {selectedFile && (
                    <div className="mb-2 flex items-center gap-2">
                        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary-600/20 border border-primary-500/30 text-sm text-primary-300">
                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            <span className="truncate max-w-[200px]">{selectedFile.name}</span>
                            <span className="text-xs text-primary-400">({formatFileSize(selectedFile.size)})</span>
                            <button
                                onClick={removeFile}
                                className="ml-1 p-0.5 rounded hover:bg-red-500/20 text-red-400 hover:text-red-300 transition-colors"
                                title="Hapus file"
                            >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    </div>
                )}

                <div className="relative border border-white/20 bg-hr-card px-4 py-1 rounded-full flex items-center items-end gap-2">
                    {/* Attachment button */}
                    <button
                        onClick={handleFileClick}
                        disabled={disabled}
                        className="flex-shrink-0 w-10 h-10 rounded-xl bg-hr-card border-0 text-hr-muted hover:text-primary-400 hover:border-primary-500 flex items-center justify-center transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed mb-0.5"
                        title="Lampirkan file (CV, dokumen)"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                        </svg>
                    </button>

                    {/* Hidden file input */}

                    <input
                        ref={fileInputRef}
                        type="file"
                        onChange={handleFileChange}
                        accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png"
                        className="hidden"
                    />
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Ketik pesan Anda... (Enter untuk kirim, Shift+Enter untuk baris baru)"
                            disabled={disabled}
                            rows={1}
                            className="w-full px-4 py-3 pr-12 rounded-xl bg-hr-card border-0 text-hr-text placeholder-zinc-500 focus:border-0 focus:ring-0 transition-all resize-none disabled:opacity-50 disabled:cursor-not-allowed"
                        />
                    </div>

                    {/* Send / Stop button */}
                    {disabled ? (
                        // ── STOP button ──────────────────────────────────────
                        <button
                            onClick={onStop}
                            className="flex-shrink-0 w-12 h-12 rounded-xl ytext-white flex items-center justify-center transition-all duration-200 shadow-lg hover:shadow-red-500/30 active:scale-95"
                            title="Hentikan proses"
                        >
                            {/* Square 'stop' icon */}
                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                                <rect x="5" y="5" width="14" height="14" rx="2" />
                            </svg>
                        </button>
                    ) : (
                        // ── SEND button ──────────────────────────────────────
                        <button
                            onClick={handleSend}
                            disabled={!message.trim() && !selectedFile}
                            className="flex-shrink-0 w-12 h-12 rounded-xl  text-white flex items-center justify-center transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-500/25"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        </button>
                    )}
                </div>

                <p className="text-xs text-white mt-2 text-center">
                    HR Agent dapat membantu dengan data karyawan, absensi, payroll, CV, dan surat peringatan
                </p>
            </div>
        </div>
    );
}

export default InputArea;
