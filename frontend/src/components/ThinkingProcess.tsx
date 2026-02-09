import { useRef, useEffect, useState } from 'react';

interface ThinkingProcessProps {
    thinking: string;
}

export default function ThinkingProcess({ thinking }: ThinkingProcessProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const [isExpanded, setIsExpanded] = useState(false);

    // Auto-scroll to bottom of thinking process while typing (only if expanded)
    useEffect(() => {
        if (scrollRef.current && isExpanded) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [thinking, isExpanded]);

    if (!thinking) return null;

    return (
        <div className="mb-4 w-full max-w-none">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 mb-2 px-1 hover:opacity-80 transition-opacity group"
            >
                <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-primary-500"></span>
                    </span>
                    <span className="text-xs font-mono text-zinc-400 uppercase tracking-wider group-hover:text-zinc-200 transition-colors">
                        Thinking Process
                    </span>
                </div>
                <svg
                    className={`w-3.5 h-3.5 text-zinc-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {isExpanded && (
                <div className="overflow-hidden">
                    <div
                        ref={scrollRef}
                        className="max-h-60 overflow-y-auto pt-1 pb-4 font-mono text-xs text-zinc-200/80 leading-relaxed custom-scrollbar border-l-2 border-primary-500/20 pl-4 ml-1"
                    >
                        <div className="whitespace-pre-wrap">{thinking}</div>
                        <div className="w-2 h-4 bg-primary-500/50 inline-block align-middle animate-pulse ml-1"></div>
                    </div>
                </div>
            )}
        </div>
    );
}
