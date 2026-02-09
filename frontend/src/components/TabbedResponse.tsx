import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { StageData } from './ProcessingBlock';
import type { WidgetData } from '../types';
import DownloadWidget from './DownloadWidget';

interface TabbedResponseProps {
    answer: string;
    stageLogs?: StageData[];
    toolCalls?: number;
    widget?: WidgetData;
}

export default function TabbedResponse({ answer, stageLogs, toolCalls, widget }: TabbedResponseProps) {
    const [activeTab, setActiveTab] = useState<'answer' | 'process'>('answer');

    // Parse thinking content helper (duplicated from ProcessingBlock to keep self-contained or could be moved to utils)
    const parseThinkingContent = (content: string): { thinking: string; main: string } => {
        // Handle complete tags
        const completeMatch = content.match(/<think>([\s\S]*?)<\/think>/i);
        if (completeMatch) {
            return {
                thinking: completeMatch[1].trim(),
                main: content.replace(completeMatch[0], '').trim()
            };
        }
        // Handle potentially unclosed tags (though stage logs in TabbedResponse should be complete, safe to keep robust)
        const openMatch = content.match(/<think>([\s\S]*)$/i);
        if (openMatch) {
            return {
                thinking: openMatch[1].trim(),
                main: content.replace(openMatch[0], '').trim()
            };
        }
        return { thinking: '', main: content };
    };

    return (
        <div className="tabbed-response w-full">
            {/* Tab Headers */}
            <div className="flex gap-1 mb-3 border-b border-white/10 pb-1">
                <button
                    onClick={() => setActiveTab('answer')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-all
                        ${activeTab === 'answer'
                            ? 'bg-primary-600/30 text-primary-400 border-b-2 border-primary-500'
                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'}`}
                >
                    <span className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                        Answer
                    </span>
                </button>
                <button
                    onClick={() => setActiveTab('process')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-all
                        ${activeTab === 'process'
                            ? 'bg-primary-600/30 text-primary-400 border-b-2 border-primary-500'
                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'}`}
                >
                    <span className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        Process
                        {stageLogs && stageLogs.length > 0 && (
                            <span className="text-xs bg-zinc-700 px-1.5 py-0.5 rounded-full">
                                {stageLogs.length}
                            </span>
                        )}
                    </span>
                </button>
            </div>

            {/* Tab Content */}
            <div className="tab-content">
                {activeTab === 'answer' && (
                    <div className="prose prose-invert max-w-none prose-base md:prose-lg font-medium tracking-tight text-zinc-100">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {answer}
                        </ReactMarkdown>

                        {/* Download Widget */}
                        {widget && widget.type === 'download' && (
                            <div className="mt-4">
                                <DownloadWidget
                                    filename={widget.filename}
                                    size={widget.size}
                                    downloadUrl={widget.download_url}
                                    icon={widget.icon}
                                />
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'process' && (
                    <div className="process-content">
                        <div className="max-h-[500px] overflow-y-auto custom-scrollbar p-3 rounded-lg bg-black/20 space-y-4">
                            {!stageLogs || stageLogs.length === 0 ? (
                                <p className="text-zinc-500 italic">No processing logs available.</p>
                            ) : (
                                stageLogs.map((stage) => {
                                    const { thinking, main } = parseThinkingContent(stage.content);
                                    return (
                                        <div key={stage.stage} className="border-b border-white/5 last:border-0 pb-4 last:pb-0">
                                            <h3 className="text-sm font-bold text-primary-400 mb-2">
                                                Stage {stage.stage}: {stage.name}
                                            </h3>

                                            {/* Thinking Block */}
                                            {thinking && (
                                                <div className="mb-2 p-2 rounded-lg bg-violet-500/10 border border-violet-500/20">
                                                    <div className="flex items-center gap-1 mb-1 text-xs text-violet-400 font-mono">
                                                        <span>🧠</span>
                                                        <span>Thinking</span>
                                                    </div>
                                                    <div className="text-xs text-zinc-400 font-mono whitespace-pre-wrap">
                                                        {thinking}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Main Content */}
                                            {main && (
                                                <div className="prose prose-invert prose-sm max-w-none text-zinc-300">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {main}
                                                    </ReactMarkdown>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            )}
                        </div>

                        {/* Tools summary */}
                        {toolCalls !== undefined && toolCalls > 0 && (
                            <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                                <span>{toolCalls} tool{toolCalls > 1 ? 's' : ''} executed</span>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
