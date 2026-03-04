import { useState, useEffect } from 'react';
import client from '../api/client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Policy {
    id: string;
    title: string;
    icon: string;
    content: string;
}

interface PoliciesPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

export function PoliciesPanel({ isOpen, onClose }: PoliciesPanelProps) {
    const [policies, setPolicies] = useState<Policy[]>([]);
    const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && policies.length === 0) {
            fetchPolicies();
        }
    }, [isOpen]);

    const fetchPolicies = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await client.get('/policies');
            setPolicies(response.data);
            if (response.data.length > 0) {
                setSelectedPolicy(response.data[0]);
            }
        } catch (err: any) {
            setError(err.response?.data?.error || 'Gagal memuat kebijakan');
        } finally {
            setLoading(false);
        }
    };

    const getIcon = (iconType: string) => {
        switch (iconType) {
            case 'clock':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                );
            case 'calendar':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                );
            case 'book':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                );
            default:
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                );
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-5xl h-[85vh] m-4 flex overflow-hidden rounded-2xl bg-hr-dark border border-white/5 shadow-2xl">
                {/* Policy Tabs - Left Sidebar */}
                <div className="w-64 border-r border-white/5 flex flex-col bg-hr-accent">
                    <div className="p-4 border-b border-white/5">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-hr-highlight flex items-center justify-center shadow-lg shadow-hr-highlight/20">
                                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-white">Kebijakan</h2>
                                <p className="text-xs text-zinc-400">Dokumen Perusahaan</p>
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-3 space-y-2">
                        {loading ? (
                            <div className="flex items-center justify-center py-8">
                                <div className="spinner"></div>
                            </div>
                        ) : error ? (
                            <div className="text-red-400 text-sm text-center py-4">
                                {error}
                            </div>
                        ) : (
                            policies.map((policy) => (
                                <button
                                    key={policy.id}
                                    onClick={() => setSelectedPolicy(policy)}
                                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-left ${selectedPolicy?.id === policy.id
                                        ? 'bg-hr-card text-white border border-white/10 shadow-sm'
                                        : 'hover:bg-hr-card/50 text-zinc-300 border border-transparent'
                                        }`}
                                >
                                    <span className={selectedPolicy?.id === policy.id ? 'text-white' : 'text-zinc-500'}>
                                        {getIcon(policy.icon)}
                                    </span>
                                    <span className="text-sm font-medium truncate">{policy.title}</span>
                                </button>
                            ))
                        )}
                    </div>
                </div>

                {/* Policy Content - Main Area */}
                <div className="flex-1 flex flex-col bg-hr-dark">
                    {/* Header with close button */}
                    <div className="h-14 px-6 flex items-center justify-between border-b border-white/5 bg-hr-accent/50">
                        <h3 className="text-lg font-semibold text-white">
                            {selectedPolicy?.title || 'Pilih Kebijakan'}
                        </h3>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                        >
                            <svg className="w-5 h-5 text-zinc-400 hover:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {/* Scrollable Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {selectedPolicy ? (
                            <div className="prose prose-invert prose-zinc max-w-none 
                                prose-headings:text-white prose-headings:font-semibold
                                prose-h1:text-2xl prose-h1:mb-6 prose-h1:pb-3 prose-h1:border-b prose-h1:border-white/10
                                prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4 prose-h2:text-white
                                prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
                                prose-p:text-zinc-300 prose-p:leading-relaxed
                                prose-li:text-zinc-300 prose-li:marker:text-hr-highlight
                                prose-strong:text-white prose-strong:font-semibold
                                prose-table:border-collapse prose-table:w-full
                                prose-th:bg-hr-card prose-th:text-white prose-th:font-medium prose-th:px-4 prose-th:py-2 prose-th:border prose-th:border-white/10
                                prose-td:px-4 prose-td:py-2 prose-td:border prose-td:border-white/10 prose-td:text-zinc-300
                                prose-a:text-hr-highlight prose-a:no-underline hover:prose-a:underline">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedPolicy.content}</ReactMarkdown>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full text-zinc-500">
                                <p>Pilih kebijakan dari menu di sebelah kiri</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default PoliciesPanel;
