import { create } from 'zustand';
import type { Message, Conversation, FileAttachment } from '../types';
import { chatApi } from '../api/chat';
import { io, Socket } from 'socket.io-client';

// Construct Socket URL
const SOCKET_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

// Stage data for processing block
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

interface ChatState {
    messages: Message[];
    conversations: Conversation[];
    currentConversationId: number | null;
    isLoading: boolean;
    isGeneratingResponse: boolean;  // true when Stage 5 starts (transition to TabbedResponse)
    error: string | null;
    statusText: string;
    socket: Socket | null;
    socketId: string | null;  // Current socket session ID (for abort)
    stageDataByConversation: Record<number, StageData[]>;
    subStatusByConversation: Record<number, SubStatusEvent[]>;
    processingConversationId: number | null;
    _pendingAssistantId: number | null;  // ID of the pre-created assistant message for stage 5

    initSocket: () => void;
    disconnectSocket: () => void;
    sendMessage: (content: string, conversationId?: number, fileAttachment?: FileAttachment) => Promise<void>;
    abortRequest: () => void;  // Stop the current agent run
    loadConversation: (conversationId: number) => Promise<void>;
    loadConversations: () => Promise<void>;
    deleteConversation: (conversationId: number) => Promise<void>;
    createNewConversation: () => void;
    clearError: () => void;
    clearStageData: (conversationId?: number) => void;
    getStageData: () => StageData[];
    getSubStatus: () => SubStatusEvent[];
}

export const useChatStore = create<ChatState>((set, get) => ({
    messages: [],
    conversations: [],
    currentConversationId: null,
    isLoading: false,
    isGeneratingResponse: false,
    error: null,
    statusText: '',
    socket: null,
    socketId: null,
    stageDataByConversation: {},
    subStatusByConversation: {},
    processingConversationId: null,
    _pendingAssistantId: null,

    initSocket: () => {
        const existingSocket = get().socket;
        // Only create new socket if none exists or it's disconnected
        if (existingSocket?.connected) {
            console.log('[Socket] Already connected, skipping init');
            return;
        }

        // Disconnect any existing socket first
        if (existingSocket) {
            console.log('[Socket] Cleaning up existing socket');
            existingSocket.removeAllListeners();
            existingSocket.disconnect();
        }

        console.log('[Socket] Creating new socket connection...');
        const socket = io(SOCKET_URL, {
            transports: ['websocket'],
            autoConnect: true,
            reconnectionAttempts: 3,
            reconnectionDelay: 1000
        });

        socket.on('connect', () => {
            console.log('[Socket] Connected:', socket.id);
            set({ socketId: socket.id ?? null });
        });
        socket.on('disconnect', (reason) => {
            console.log('[Socket] Disconnected:', reason);
            set({ socketId: null });
        });

        socket.on('status_update', (data: { status: string }) => {
            set({ statusText: data.status });
        });

        socket.on('stage_complete', (data: StageData) => {
            console.log('[Socket] Stage complete:', data);
            const processingId = get().processingConversationId;
            if (processingId !== null) {
                set((state) => {
                    const existing = state.stageDataByConversation[processingId] || [];
                    // Upsert: replace if same stage number exists (handles retry loops),
                    // otherwise append
                    const updated = existing.some(s => s.stage === data.stage)
                        ? existing.map(s => s.stage === data.stage ? data : s)
                        : [...existing, data];
                    return {
                        stageDataByConversation: {
                            ...state.stageDataByConversation,
                            [processingId]: updated
                        }
                    };
                });

                // ── Stage 5 transition: pre-create assistant message & switch view ──
                if (data.stage === 5) {
                    const alreadyPending = get()._pendingAssistantId;
                    if (!alreadyPending) {
                        const pendingId = Date.now();
                        // Collect stage logs from stages 1-4 for the Process tab
                        const allStages = get().stageDataByConversation[processingId] || [];
                        const stageLogs = allStages
                            .filter(s => s.stage > 0 && s.stage < 5)
                            .map(s => ({ stage: s.stage, name: s.name, content: s.content, status: s.status }));

                        set((state) => ({
                            isGeneratingResponse: true,
                            _pendingAssistantId: pendingId,
                            messages: [...state.messages, {
                                id: pendingId,
                                role: 'assistant' as const,
                                content: '',
                                thinking: '',
                                created_at: new Date().toISOString(),
                                metadata: {
                                    stage_logs: stageLogs,
                                },
                            }],
                        }));
                    }
                }
            }
        });

        // Verification failed → agent is retrying from Stage 1.
        // Clear current stages and insert a 'reset' sentinel so ProcessingBlock
        // can render the retry banner, then incoming stage_complete events
        // will populate the fresh stages below it.
        socket.on('stage_retry_reset', (data: { retry_attempt: number; message: string }) => {
            console.log('[Socket] Stage retry reset:', data);
            const processingId = get().processingConversationId;
            if (processingId !== null) {
                const retryBanner: StageData = {
                    stage: 0,                    // sentinel: 0 = retry indicator
                    name: `Retry #${data.retry_attempt}`,
                    content: data.message,
                    status: 'processing'         // shows spinner briefly
                };
                set((state) => ({
                    stageDataByConversation: {
                        ...state.stageDataByConversation,
                        [processingId]: [retryBanner]
                    },
                    subStatusByConversation: {
                        ...state.subStatusByConversation,
                        [processingId]: []  // Clear sub-status on retry reset
                    }
                }));
                // After a short delay, mark the retry banner complete so it collapses
                setTimeout(() => {
                    set((state) => {
                        const current = state.stageDataByConversation[processingId] || [];
                        return {
                            stageDataByConversation: {
                                ...state.stageDataByConversation,
                                [processingId]: current.map(s =>
                                    s.stage === 0 ? { ...s, status: 'complete' } : s
                                )
                            }
                        };
                    });
                }, 1200);
            }
        });


        // Sub-status events (tool-level progress)
        socket.on('sub_status', (data: SubStatusEvent) => {
            const processingId = get().processingConversationId;
            if (processingId !== null) {
                set((state) => ({
                    subStatusByConversation: {
                        ...state.subStatusByConversation,
                        [processingId]: [...(state.subStatusByConversation[processingId] || []), data]
                    }
                }));
            }
        });


        socket.on('error', (data: { message: string }) => {
            const processingId = get().processingConversationId;
            set((state) => ({
                error: data.message,
                isLoading: false,
                isGeneratingResponse: false,
                _pendingAssistantId: null,
                stageDataByConversation: processingId !== null
                    ? { ...state.stageDataByConversation, [processingId]: [] }
                    : state.stageDataByConversation,
                processingConversationId: null
            }));
        });

        set({ socket });
    },

    disconnectSocket: () => {
        const socket = get().socket;
        if (socket) {
            console.log('[Socket] Disconnecting...');
            socket.removeAllListeners();
            socket.disconnect();
            set({ socket: null });
        }
    },

    sendMessage: async (content: string, conversationId?: number, fileAttachment?: FileAttachment) => {
        // Import getValidToken dynamically to avoid circular deps
        const { getValidToken } = await import('../utils/tokenUtils');

        let socket = get().socket;
        if (!socket) {
            get().initSocket();
            socket = get().socket;
        }

        if (!socket) {
            set({ error: 'WebSocket not initialized' });
            return;
        }

        // Get a valid token (will refresh if expiring soon)
        const token = await getValidToken();
        if (!token) {
            set({ error: 'Sesi telah berakhir, silakan login kembali' });
            return;
        }

        const targetConversationId = conversationId || get().currentConversationId || -1; // -1 for new conversation
        set({
            isLoading: true,
            error: null,
            statusText: 'Memproses...',
            processingConversationId: targetConversationId,
            stageDataByConversation: {
                ...get().stageDataByConversation,
                [targetConversationId]: []
            },
            subStatusByConversation: {
                ...get().subStatusByConversation,
                [targetConversationId]: []
            }
        });

        // Optimistic update
        const userMessage: Message = {
            role: 'user',
            content,
            created_at: new Date().toISOString(),
            ...(fileAttachment ? { file_attachment: fileAttachment } : {}),
        };

        const assistantMessageId = Date.now();

        set((state) => ({
            messages: [...state.messages, userMessage]
        }));

        return new Promise<void>((resolve) => {
            socket!.emit('chat_message', {
                message: content,
                conversation_id: conversationId || get().currentConversationId || undefined,
                token: token
            });

            socket!.once('chat_response', async (response: any) => {
                // Use pre-created assistant message from Stage 5 if available,
                // otherwise create a new one
                const pendingId = get()._pendingAssistantId;
                const targetMsgId = pendingId || assistantMessageId;

                if (!pendingId) {
                    // No stage 5 pre-creation happened (e.g. simple query), add message now
                    set((state) => ({
                        messages: [...state.messages, {
                            id: targetMsgId,
                            role: 'assistant' as const,
                            content: '',
                            thinking: '',
                            created_at: new Date().toISOString(),
                        }]
                    }));
                }

                if (response.error) {
                    set({ error: response.error, isLoading: false, statusText: '' });
                    resolve();
                    return;
                }

                const fullResponseWithThink = (response.thinking ? `<think>${response.thinking}</think>` : '') + response.response;

                // Typing Animation
                const CHUNK_SIZE = 8;
                const YIELD_DELAY_MS = 5;
                let buffer = '';
                let displayed = '';

                const updateMessageState = (currentText: string) => {
                    const thinkMatch = currentText.match(/<think>([\s\S]*?)<\/think>/i);
                    const unclosedThinkMatch = currentText.match(/<think>([\s\S]*)$/i);

                    let thinkContent = '';
                    let mainContent = '';

                    if (thinkMatch) {
                        thinkContent = thinkMatch[1];
                        mainContent = currentText.replace(thinkMatch[0], '');
                    } else if (unclosedThinkMatch) {
                        thinkContent = unclosedThinkMatch[1];
                        mainContent = '';
                    } else {
                        mainContent = currentText;
                    }

                    set((state) => ({
                        messages: state.messages.map(msg =>
                            msg.id === targetMsgId
                                ? { ...msg, content: mainContent, thinking: thinkContent }
                                : msg
                        )
                    }));
                };

                for (let i = 0; i < fullResponseWithThink.length; i++) {
                    buffer += fullResponseWithThink[i];
                    if (buffer.length >= CHUNK_SIZE || i === fullResponseWithThink.length - 1) {
                        displayed += buffer;
                        updateMessageState(displayed);
                        buffer = '';
                        await new Promise(r => setTimeout(r, YIELD_DELAY_MS));
                    }
                }

                // Merge stage_logs: prefer pre-collected logs (from stage 5 creation)
                // and fallback to response.stage_logs
                const existingMsg = get().messages.find(m => m.id === targetMsgId);
                const mergedStageLogs = existingMsg?.metadata?.stage_logs || response.stage_logs;

                set((state) => ({
                    messages: state.messages.map(msg =>
                        msg.id === targetMsgId
                            ? {
                                ...msg,
                                content: response.response,
                                thinking: response.thinking,
                                tool_calls: response.tool_calls,
                                metadata: {
                                    ...response.metadata,
                                    stage_logs: mergedStageLogs,
                                    total_tool_calls: response.metadata?.total_tool_calls,
                                    widget: response.metadata?.widget
                                }
                            }
                            : msg
                    ),
                    currentConversationId: response.conversation_id,
                    isLoading: false,
                    isGeneratingResponse: false,
                    _pendingAssistantId: null,
                    statusText: '',
                    processingConversationId: null
                }));

                get().loadConversations();
                resolve();
            });
        });

    },

    loadConversation: async (conversationId: number) => {
        set({ isLoading: true, error: null });
        try {
            const response = await chatApi.getConversation(conversationId);
            const messages: Message[] = response.messages.map((msg) => ({
                ...msg,
                role: msg.role as 'user' | 'assistant',
            }));

            // Check if the last message is from user (meaning assistant response is pending)
            const lastMessage = messages[messages.length - 1];
            const isPendingResponse = lastMessage && lastMessage.role === 'user';

            // If pending response, fetch processing stages from database
            if (isPendingResponse) {
                try {
                    const stagesResponse = await chatApi.getProcessingStages(conversationId);
                    const stages = stagesResponse.stages || [];

                    if (stages.length > 0) {
                        // We have saved processing stages - restore them and show processing UI
                        set({
                            messages,
                            currentConversationId: conversationId,
                            isLoading: true, // Keep loading true to show processing block
                            stageDataByConversation: {
                                ...get().stageDataByConversation,
                                [conversationId]: stages
                            },
                            processingConversationId: conversationId,
                            statusText: 'Melanjutkan proses...'
                        });
                        return;
                    }
                } catch (stagesError) {
                    console.error('Failed to load processing stages:', stagesError);
                }
            }

            set({
                messages,
                currentConversationId: conversationId,
                isLoading: false,
            });
        } catch (error: any) {
            set({ error: error.message || 'Gagal memuat percakapan', isLoading: false });
        }
    },

    loadConversations: async () => {
        try {
            const conversations = await chatApi.getConversations();
            set({ conversations });
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    },

    deleteConversation: async (conversationId: number) => {
        try {
            await chatApi.deleteConversation(conversationId);
            set((state) => ({
                conversations: state.conversations.filter((c) => c.id !== conversationId),
                ...(state.currentConversationId === conversationId
                    ? { messages: [], currentConversationId: null }
                    : {}),
            }));
        } catch (error) {
            console.error('Failed to delete conversation:', error);
        }
    },

    createNewConversation: () => {
        set({
            messages: [],
            currentConversationId: null,
        });
    },

    clearError: () => set({ error: null }),

    abortRequest: () => {
        const { socket, processingConversationId } = get();
        if (socket?.connected) {
            socket.emit('abort');  // tell backend to stop
        }
        // Reset UI state immediately without waiting for backend
        set((state) => ({
            isLoading: false,
            isGeneratingResponse: false,
            _pendingAssistantId: null,
            statusText: '',
            processingConversationId: null,
            stageDataByConversation: processingConversationId !== null
                ? { ...state.stageDataByConversation, [processingConversationId]: [] }
                : state.stageDataByConversation
        }));
    },

    clearStageData: (conversationId?: number) => {
        const targetId = conversationId || get().currentConversationId;
        if (targetId !== null) {
            set((state) => ({
                stageDataByConversation: {
                    ...state.stageDataByConversation,
                    [targetId]: []
                }
            }));
        }
    },

    getStageData: () => {
        const state = get();
        const targetId = state.processingConversationId ?? state.currentConversationId;
        if (targetId !== null && state.stageDataByConversation[targetId]) {
            return state.stageDataByConversation[targetId];
        }
        return [];
    },

    getSubStatus: () => {
        const state = get();
        const targetId = state.processingConversationId ?? state.currentConversationId;
        if (targetId !== null && state.subStatusByConversation[targetId]) {
            return state.subStatusByConversation[targetId];
        }
        return [];
    },
}));

export default useChatStore;
