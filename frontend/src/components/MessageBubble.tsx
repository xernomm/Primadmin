import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '../types';
import TabbedResponse from './TabbedResponse';
import { useChatStore } from '../store/chatStore';
import PrimaLogo from '../img/primalogo.png';

interface MessageBubbleProps {
    message: Message;
}

// Helper to strip <think> blocks from content for clean display
function stripThinkTags(content: string): string {
    return content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
}

// Parse [file_attached: path] from message content
function parseFileAttachment(content: string): { cleanContent: string; filePath: string | null; fileName: string | null; fileExt: string | null } {
    const match = content.match(/\[file_attached:\s*(.+?)\]/i);
    if (!match) return { cleanContent: content, filePath: null, fileName: null, fileExt: null };

    const filePath = match[1].trim();
    const cleanContent = content.replace(match[0], '').trim();
    // Extract filename from path (handle both / and \\)
    const fileName = filePath.split(/[/\\]/).pop() || filePath;
    const fileExt = fileName.includes('.') ? fileName.split('.').pop()?.toLowerCase() || null : null;

    return { cleanContent, filePath, fileName, fileExt };
}

// File type icon component
function FileIcon({ ext }: { ext: string | null }) {
    const color = ext === 'pdf' ? 'text-red-400' : ext === 'docx' || ext === 'doc' ? 'text-white' : 'text-zinc-400';
    return (
        <svg className={`w-5 h-5 ${color}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
    );
}

export function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';

    // Determine if this assistant message is currently streaming
    const isStreaming = useChatStore((state) => {
        if (isUser) return false;
        return state.isGeneratingResponse && state._pendingAssistantId === message.id;
    });

    // Parse file attachment from user messages
    const { cleanContent: userCleanContent, fileName, fileExt } = isUser
        ? parseFileAttachment(message.content)
        : { cleanContent: message.content, fileName: null, fileExt: null };

    // Clean content (strip <think> tags for Answer tab)
    const cleanContent = stripThinkTags(isUser ? userCleanContent : message.content);

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in mb-6 min-w-0 w-full`}>
            <div className={`min-w-0 ${isUser ? 'max-w-[85%] md:max-w-[65%] order-2' : 'max-w-full order-1'} flex flex-col items-${isUser ? 'end' : 'start'}`}>
                {/* Avatar */}
                <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse w-full' : ''}`}>
                    {/* <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${isUser
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
                    </div> */}

                    <div className={`flex-1 ${isUser ? 'flex flex-col items-end' : ''}`}>

                        {/* File attachment widget — above the bubble */}
                        {isUser && fileName && (
                            <div className="mb-2 inline-flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-zinc-800/80 border border-zinc-700/60 backdrop-blur-sm shadow-lg max-w-[280px]">
                                <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-zinc-700/60 flex items-center justify-center">
                                    <FileIcon ext={fileExt} />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-zinc-200 font-medium truncate" title={fileName}>
                                        {fileName}
                                    </p>
                                    <p className="text-[11px] text-zinc-500 uppercase tracking-wide">
                                        {fileExt || 'FILE'}
                                    </p>
                                </div>
                            </div>
                        )}

                        <div className={`${isUser
                            ? 'bg-primary-600 text-white shadow-primary-500/20 px-5 py-4 rounded-2xl rounded-br-none shadow-xl'
                            : 'text-zinc-100 w-full'} 
                            transition-all`}>

                            {/* User message - simple markdown (with file path stripped) */}
                            {isUser && (
                                <div className="prose prose-invert max-w-none break-words text-white prose-sm">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                        {cleanContent}
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
                                    isStreaming={isStreaming}
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

