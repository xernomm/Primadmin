import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../types';
import TabbedResponse from './TabbedResponse';
import PrimaLogo from '../img/primalogo.png';

interface MessageBubbleProps {
    message: Message;
}

// Helper to strip <think> blocks from content for clean display
function stripThinkTags(content: string): string {
    return content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
}

export function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';

    // Clean content (strip <think> tags for Answer tab)
    const cleanContent = stripThinkTags(message.content);

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in mb-6`}>
            <div className={`max-w-[85%] md:max-w-[75%] ${isUser ? 'order-2' : 'order-1'} flex flex-col items-${isUser ? 'end' : 'start'}`}>
                {/* Avatar */}
                <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse w-full' : ''}`}>
                    <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${isUser
                        ? 'bg-gradient-to-br from-primary-600 to-primary-800 shadow-lg'
                        : ''
                        }`}>
                        {isUser ? (
                            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                        ) : (
                            <img src={PrimaLogo} alt="Primassistant" className="w-7 h-7 object-contain" />
                        )}
                    </div>

                    <div className={`flex-1 ${isUser ? 'flex flex-col items-end' : ''}`}>

                        <div className={`${isUser
                            ? 'bg-primary-600 text-white shadow-primary-500/20 px-5 py-4 rounded-2xl rounded-tr-none shadow-xl'
                            : 'text-zinc-100 w-full'} 
                            transition-all`}>

                            {/* User message - simple markdown */}
                            {isUser && (
                                <div className="prose prose-invert max-w-none break-words text-white prose-sm">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {message.content}
                                    </ReactMarkdown>
                                </div>
                            )}

                            {/* Assistant message - Tabbed Response with Answer/Process */}
                            {!isUser && (
                                <TabbedResponse
                                    answer={cleanContent}
                                    stageLogs={message.metadata?.stage_logs}
                                    toolCalls={message.tool_calls?.length || message.metadata?.total_tool_calls}
                                    widget={message.metadata?.widget}
                                />
                            )}

                            {/* RAG indicator */}
                            {message.metadata?.rag_used && (
                                <div className="mt-2 flex items-center gap-1.5 text-xs text-primary-400 font-medium">
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <span>Berdasarkan dokumen kebijakan</span>
                                </div>
                            )}
                        </div>

                        {/* Timestamp */}
                        {message.created_at && (
                            <p className={`text-[10px] text-zinc-500 mt-1.5 font-medium ${isUser ? 'mr-1' : 'ml-1'}`}>
                                {formatTime(message.created_at)}
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function formatTime(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleTimeString('id-ID', {
        hour: '2-digit',
        minute: '2-digit',
    });
}

export default MessageBubble;

