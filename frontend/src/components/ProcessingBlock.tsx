import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface StageData {
    stage: number;
    name: string;
    content: string;
    status: 'processing' | 'complete' | 'error';
}

interface ProcessingBlockProps {
    stages: StageData[];
    currentStatus: string;
}

// Parse thinking content from LLM response
function parseThinkingContent(content: string): { thinking: string; main: string } {
    // 1. Check for complete block first
    const completeMatch = content.match(/<think>([\s\S]*?)<\/think>/i);
    if (completeMatch) {
        return {
            thinking: completeMatch[1].trim(),
            main: content.replace(completeMatch[0], '').trim()
        };
    }

    // 2. Check for open block (streaming case) - ensures we don't show <think> content in main
    const openMatch = content.match(/<think>([\s\S]*)$/i);
    if (openMatch) {
        return {
            thinking: openMatch[1].trim(),
            main: content.replace(openMatch[0], '').trim()
        };
    }

    // 3. Fallback: if no tags found, everything is main content
    return { thinking: '', main: content };
}

export default function ProcessingBlock({ stages, currentStatus }: ProcessingBlockProps) {
    const [displayedContent, setDisplayedContent] = useState<{ [key: number]: string }>({});
    const [expandedStages, setExpandedStages] = useState<{ [key: number]: boolean }>({});
    const animationRefs = useRef<{ [key: number]: NodeJS.Timeout | null }>({});

    // Typing animation for each stage
    useEffect(() => {
        stages.forEach((stage) => {
            if (stage.status === 'complete' && !displayedContent[stage.stage]) {
                // Start typing animation for this stage
                let charIndex = 0;
                const fullContent = stage.content;

                // Clear any existing animation
                if (animationRefs.current[stage.stage]) {
                    clearInterval(animationRefs.current[stage.stage]!);
                }

                animationRefs.current[stage.stage] = setInterval(() => {
                    charIndex += 8; // Speed: 8 chars at a time for faster display
                    if (charIndex >= fullContent.length) {
                        charIndex = fullContent.length;
                        if (animationRefs.current[stage.stage]) {
                            clearInterval(animationRefs.current[stage.stage]!);
                        }
                    }
                    setDisplayedContent(prev => ({
                        ...prev,
                        [stage.stage]: fullContent.substring(0, charIndex)
                    }));
                }, 5); // 5ms interval for faster typing
            }
        });

        return () => {
            Object.values(animationRefs.current).forEach(timer => {
                if (timer) clearInterval(timer);
            });
        };
    }, [stages]);

    // Toggle stage expansion
    const toggleExpand = (stageNum: number) => {
        setExpandedStages(prev => ({ ...prev, [stageNum]: !prev[stageNum] }));
    };

    if (stages.length === 0 && !currentStatus) return null;

    return (
        <div className="processing-block glass-glow rounded-xl p-4 mb-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/10">
                <div className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary-500"></span>
                </div>
                <span className="text-xs font-mono text-zinc-300 uppercase tracking-wider">
                    Agent Processing
                </span>
            </div>

            {/* Stages */}
            <div className="space-y-3">
                {stages.map((stage) => {
                    const currentContent = displayedContent[stage.stage] || '';
                    const { thinking, main } = parseThinkingContent(currentContent);
                    const isExpanded = expandedStages[stage.stage] ?? true;
                    const hasThinking = thinking.length > 0;

                    return (
                        <div key={stage.stage} className="stage-item">
                            {/* Stage Header */}
                            <div
                                className="flex items-center gap-2 mb-1 cursor-pointer hover:opacity-80"
                                onClick={() => toggleExpand(stage.stage)}
                            >
                                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold
                                    ${stage.status === 'complete' ? 'bg-green-500/20 text-green-400' :
                                        stage.status === 'error' ? 'bg-red-500/20 text-red-400' :
                                            'bg-primary-500/20 text-primary-400'}`}
                                >
                                    {stage.status === 'complete' ? '✓' :
                                        stage.status === 'error' ? '✗' : stage.stage}
                                </div>
                                <span className="text-sm font-medium text-zinc-200">
                                    Stage {stage.stage}: {stage.name}
                                </span>
                                {stage.status === 'processing' && (
                                    <div className="spinner-mini ml-auto" />
                                )}
                                {stage.status === 'complete' && (
                                    <span className="ml-auto text-xs text-zinc-500">
                                        {isExpanded ? '▼' : '▶'}
                                    </span>
                                )}
                            </div>

                            {/* Stage Content */}
                            {isExpanded && (currentContent || stage.status === 'processing') && (
                                <div className="ml-7 mt-1 space-y-2">
                                    {stage.status === 'processing' ? (
                                        <div className="p-2 rounded-lg bg-black/20 border border-white/5">
                                            <div className="flex items-center gap-2 text-xs text-zinc-400">
                                                <div className="typing-dots">
                                                    <span></span><span></span><span></span>
                                                </div>
                                                <span>Generating...</span>
                                            </div>
                                        </div>
                                    ) : (
                                        <>
                                            {/* Thinking Block */}
                                            {hasThinking && (
                                                <div className="p-2 rounded-lg bg-violet-500/10 border border-violet-500/20">
                                                    <div className="flex items-center gap-1 mb-1 text-xs text-violet-400 font-mono">
                                                        <span>🧠</span>
                                                        <span>Thinking...</span>
                                                    </div>
                                                    <div className="text-xs text-zinc-400 max-h-48 overflow-y-auto font-mono whitespace-pre-wrap">
                                                        {thinking}
                                                        {currentContent.length < stage.content.length && (
                                                            <span className="inline-block w-1 h-3 bg-violet-500 ml-0.5 animate-pulse" />
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Main Content Block */}
                                            {main && (
                                                <div className="p-2 rounded-lg bg-black/20 border border-white/5">
                                                    <div className="prose prose-invert prose-xs max-w-none text-zinc-300">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                            {main}
                                                        </ReactMarkdown>
                                                        {currentContent.length < stage.content.length && !hasThinking && (
                                                            <span className="inline-block w-1.5 h-3 bg-primary-500 ml-0.5 animate-pulse" />
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Show cursor if still typing and has thinking only */}
                                            {!main && hasThinking && currentContent.length >= stage.content.length && null}
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}

                {/* Show current status if no stages yet */}
                {stages.length === 0 && currentStatus && (
                    <div className="flex items-center gap-2 text-sm text-zinc-400">
                        <div className="spinner-mini" />
                        <span>{currentStatus}</span>
                    </div>
                )}

                {/* Show next stage loading indicator */}
                {stages.length > 0 && stages.every(s => s.status === 'complete') && currentStatus && (
                    <div className="flex items-center gap-2 text-sm text-zinc-400 mt-2">
                        <div className="spinner-mini" />
                        <span>{currentStatus}</span>
                    </div>
                )}
            </div>
        </div>
    );
}

