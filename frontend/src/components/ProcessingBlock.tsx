import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface StageData {
    stage: number;
    name: string;
    content: string;
    status: 'processing' | 'complete' | 'error';
}

export interface SubStatusEvent {
    type: 'tool_start' | 'tool_done' | 'plan_validated' | 'plan_invalid';
    tool?: string;
    step?: number;
    success?: boolean;
    valid?: boolean;
    steps?: number;
    attempt?: number;
    errors?: string[];
}

interface ProcessingBlockProps {
    stages: StageData[];
    currentStatus: string;
    subEvents?: SubStatusEvent[];
}

// Parse thinking content from LLM response
function parseThinkingContent(content: string): { thinking: string; main: string } {
    const completeMatch = content.match(/<think>([\s\S]*?)<\/think>/i);
    if (completeMatch) {
        return {
            thinking: completeMatch[1].trim(),
            main: content.replace(completeMatch[0], '').trim()
        };
    }
    const openMatch = content.match(/<think>([\s\S]*)$/i);
    if (openMatch) {
        return {
            thinking: openMatch[1].trim(),
            main: content.replace(openMatch[0], '').trim()
        };
    }
    return { thinking: '', main: content };
}

export default function ProcessingBlock({ stages, currentStatus, subEvents = [] }: ProcessingBlockProps) {
    const [displayedContent, setDisplayedContent] = useState<{ [key: number]: string }>({});
    const [expandedStages, setExpandedStages] = useState<{ [key: number]: boolean }>({});
    const animationRefs = useRef<{ [key: number]: NodeJS.Timeout | null }>({});

    // When a retry reset happens (stage 0 present), clear old animation state
    useEffect(() => {
        const hasRetryBanner = stages.some(s => s.stage === 0);
        if (hasRetryBanner) {
            Object.values(animationRefs.current).forEach(timer => {
                if (timer) clearInterval(timer);
            });
            animationRefs.current = {};
            setDisplayedContent({});
            setExpandedStages({});
        }
    }, [stages.some(s => s.stage === 0)]);

    const mountedRef = useRef(true);
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            Object.values(animationRefs.current).forEach(timer => {
                if (timer) clearInterval(timer);
            });
        };
    }, []);

    // Typing animation for each stage (skip stage 0 — retry banner)
    useEffect(() => {
        stages.forEach((stage) => {
            if (stage.stage === 0) return;
            const alreadyDisplayed = displayedContent[stage.stage] ?? '';
            const isFullyDisplayed = alreadyDisplayed === stage.content;

            if (stage.status === 'complete' && !isFullyDisplayed) {
                let charIndex = alreadyDisplayed.length;
                const fullContent = stage.content;

                if (animationRefs.current[stage.stage]) {
                    clearInterval(animationRefs.current[stage.stage]!);
                }

                animationRefs.current[stage.stage] = setInterval(() => {
                    if (!mountedRef.current) return;
                    charIndex += 8;
                    if (charIndex >= fullContent.length) {
                        charIndex = fullContent.length;
                        if (animationRefs.current[stage.stage]) {
                            clearInterval(animationRefs.current[stage.stage]!);
                            animationRefs.current[stage.stage] = null;
                        }
                    }
                    setDisplayedContent(prev => ({
                        ...prev,
                        [stage.stage]: fullContent.substring(0, charIndex)
                    }));
                }, 5);
            }
        });
    }, [stages]);

    const toggleExpand = (stageNum: number) => {
        setExpandedStages(prev => ({ ...prev, [stageNum]: !(prev[stageNum] ?? true) }));
    };

    if (stages.length === 0 && !currentStatus) return null;

    const retryBanner = stages.find(s => s.stage === 0);
    const regularStages = stages.filter(s => s.stage !== 0);

    // Derive tool timeline from sub-events for Stage 3
    const toolTimeline = subEvents.filter(e => e.type === 'tool_start' || e.type === 'tool_done');
    const planEvents = subEvents.filter(e => e.type === 'plan_validated' || e.type === 'plan_invalid');

    return (
        <div className="processing-block glass-glow rounded-xl p-4 mb-4 animate-fade-in w-full max-w-full">
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

            <div className="space-y-3 w-full">

                {/* ── Retry Banner (stage 0) ── */}
                {retryBanner && (
                    <div className={`
                        flex items-center gap-2 px-3 py-2 rounded-lg
                        border animate-fade-in
                        ${retryBanner.status === 'processing'
                            ? 'bg-amber-500/10 border-amber-500/40 animate-pulse-subtle'
                            : 'bg-amber-500/5 border-amber-500/20'}
                    `}>
                        <span className={`text-base ${retryBanner.status === 'processing' ? 'animate-spin-slow' : ''}`}>
                            ↺
                        </span>
                        <div>
                            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                                {retryBanner.name}
                            </span>
                            <p className="text-xs text-amber-300/70 mt-0.5">{retryBanner.content}</p>
                        </div>
                        {retryBanner.status === 'processing' && (
                            <div className="spinner-mini ml-auto border-amber-400/60" />
                        )}
                    </div>
                )}

                {/* ── Regular Stages ── */}
                {regularStages.map((stage) => {
                    const currentContent = displayedContent[stage.stage] || '';
                    const { thinking, main } = parseThinkingContent(currentContent);
                    const isExpanded = expandedStages[stage.stage] ?? true;
                    const hasThinking = thinking.length > 0;

                    return (
                        <div key={stage.stage} className="stage-item animate-fade-in w-full min-w-0">
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
                                    {stage.name}
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

                            {/* Plan Validation Indicator (between Stage 2 and 3) */}
                            {stage.stage === 2 && stage.status === 'complete' && planEvents.length > 0 && (
                                <div className="ml-7 mb-1">
                                    {planEvents.map((evt, i) => (
                                        <div key={i} className={`flex items-center gap-1.5 text-xs py-0.5 ${evt.valid ? 'text-emerald-400' : 'text-amber-400'}`}>
                                            <span>{evt.valid ? '✓' : '⟳'}</span>
                                            <span className="font-mono">
                                                {evt.valid
                                                    ? `Plan tervalidasi (${evt.steps} steps)`
                                                    : `Plan invalid, regenerating... (percobaan ${evt.attempt})`
                                                }
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Stage Content */}
                            {isExpanded && (currentContent || stage.status === 'processing') && (
                                <div className="mt-1 space-y-2 w-full min-w-0 pl-7">
                                    {stage.status === 'processing' ? (
                                        <div className="p-2 rounded-lg bg-black/20 border border-white/5">
                                            {/* ── Live Tool Timeline (Stage 3 only) ── */}
                                            {stage.stage === 3 && toolTimeline.length > 0 ? (
                                                <div className="space-y-1">
                                                    {renderToolTimeline(toolTimeline)}
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2 text-xs text-zinc-400">
                                                    <div className="typing-dots">
                                                        <span></span><span></span><span></span>
                                                    </div>
                                                    <span>Generating...</span>
                                                </div>
                                            )}
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
                                                    <div className="text-xs text-zinc-400 max-h-48 overflow-y-auto overflow-x-hidden font-mono whitespace-pre-wrap break-words">
                                                        {thinking}
                                                        {currentContent.length < stage.content.length && (
                                                            <span className="inline-block w-1 h-3 bg-violet-500 ml-0.5 animate-pulse" />
                                                        )}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Main Content Block */}
                                            {main && (
                                                <div className="p-2 rounded-lg bg-black/20 border border-white/5 w-full overflow-hidden">
                                                    <div className="prose prose-invert prose-xs max-w-none text-zinc-300 break-words [&_pre]:whitespace-pre-wrap [&_pre]:break-words [&_code]:break-words">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                            {stage.stage === 2 && main.trim().startsWith('{') && !main.includes('```')
                                                                ? `\`\`\`json\n${main}\n\`\`\``
                                                                : main}
                                                        </ReactMarkdown>
                                                        {currentContent.length < stage.content.length && !hasThinking && (
                                                            <span className="inline-block w-1.5 h-3 bg-primary-500 ml-0.5 animate-pulse" />
                                                        )}
                                                    </div>
                                                </div>
                                            )}

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
                {regularStages.length > 0 && regularStages.every(s => s.status === 'complete') && currentStatus && (
                    <div className="flex items-center gap-2 text-sm text-zinc-400 mt-2">
                        <div className="spinner-mini" />
                        <span>{currentStatus}</span>
                    </div>
                )}
            </div>
        </div>
    );
}


/**
 * Render the live tool execution timeline inside Stage 3.
 * Shows each tool as a row: spinner → running, check → done.
 */
function renderToolTimeline(events: SubStatusEvent[]) {
    // Build a map of tools: track which are started vs done
    const toolSteps: { tool: string; step: number; status: 'running' | 'success' | 'error' }[] = [];
    const seen = new Map<string, number>(); // tool+step → index in toolSteps

    for (const evt of events) {
        const key = `${evt.tool}_${evt.step}`;
        if (evt.type === 'tool_start') {
            seen.set(key, toolSteps.length);
            toolSteps.push({
                tool: evt.tool || 'unknown',
                step: evt.step || 0,
                status: 'running',
            });
        } else if (evt.type === 'tool_done') {
            const idx = seen.get(key);
            if (idx !== undefined) {
                toolSteps[idx].status = evt.success ? 'success' : 'error';
            }
        }
    }

    return toolSteps.map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-xs py-0.5 animate-fade-in">
            {item.status === 'running' ? (
                <div className="spinner-mini w-3 h-3 border" />
            ) : item.status === 'success' ? (
                <span className="text-green-400 w-3 text-center">✓</span>
            ) : (
                <span className="text-red-400 w-3 text-center">✗</span>
            )}
            <span className={`font-mono ${item.status === 'running' ? 'text-primary-300' :
                item.status === 'success' ? 'text-green-300/80' :
                    'text-red-300/80'
                }`}>
                {item.tool}
            </span>
            {item.status === 'success' && (
                <span className="text-green-500/60 ml-1">Berhasil</span>
            )}
            {item.status === 'error' && (
                <span className="text-red-500/60 ml-1">Error</span>
            )}
        </div>
    ));
}
