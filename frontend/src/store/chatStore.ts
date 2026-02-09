import { create } from 'zustand';
import type { Message, Conversation } from '../types';
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

interface ChatState {
    messages: Message[];
    conversations: Conversation[];
    currentConversationId: number | null;
    isLoading: boolean;
    error: string | null;
    statusText: string;
    socket: Socket | null;
    stageDataByConversation: Record<number, StageData[]>;  // For processing block display per conversation
    processingConversationId: number | null;  // Track which conversation is currently processing

    initSocket: () => void;
    disconnectSocket: () => void;
    sendMessage: (content: string, conversationId?: number) => Promise<void>;
    loadConversation: (conversationId: number) => Promise<void>;
    loadConversations: () => Promise<void>;
    deleteConversation: (conversationId: number) => Promise<void>;
    createNewConversation: () => void;
    clearError: () => void;
    clearStageData: (conversationId?: number) => void;
    getStageData: () => StageData[];  // Get stage data for current/processing conversation
}

export const useChatStore = create<ChatState>((set, get) => ({
    messages: [],
    conversations: [],
    currentConversationId: null,
    isLoading: false,
    error: null,
    statusText: '',
    socket: null,
    stageDataByConversation: {},
    processingConversationId: null,

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

        socket.on('connect', () => console.log('[Socket] Connected:', socket.id));
        socket.on('disconnect', (reason) => console.log('[Socket] Disconnected:', reason));

        socket.on('status_update', (data: { status: string }) => {
            set({ statusText: data.status });
        });

        socket.on('stage_complete', (data: StageData) => {
            console.log('[Socket] Stage complete:', data);
            const processingId = get().processingConversationId;
            if (processingId !== null) {
                set((state) => ({
                    stageDataByConversation: {
                        ...state.stageDataByConversation,
                        [processingId]: [...(state.stageDataByConversation[processingId] || []), data]
                    }
                }));
            }
        });

        socket.on('error', (data: { message: string }) => {
            const processingId = get().processingConversationId;
            set((state) => ({
                error: data.message,
                isLoading: false,
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

    sendMessage: async (content: string, conversationId?: number) => {
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
                [targetConversationId]: []  // Clear stage data for this conversation
            }
        });

        // Optimistic update
        const userMessage: Message = {
            role: 'user',
            content,
            created_at: new Date().toISOString(),
        };

        const assistantMessageId = Date.now();
        const initialAssistantMessage: Message = {
            id: assistantMessageId,
            role: 'assistant',
            content: '',
            thinking: '',
            created_at: new Date().toISOString(),
        };

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
                // Add assistant message now that we have a response
                set((state) => ({
                    messages: [...state.messages, initialAssistantMessage]
                }));

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
                            msg.id === assistantMessageId
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

                set((state) => ({
                    messages: state.messages.map(msg =>
                        msg.id === assistantMessageId
                            ? {
                                ...msg,
                                content: response.response,
                                thinking: response.thinking,
                                tool_calls: response.tool_calls,
                                metadata: {
                                    ...response.metadata,
                                    stage_logs: response.stage_logs,  // Include stage logs for Process tab
                                    total_tool_calls: response.metadata?.total_tool_calls,
                                    widget: response.metadata?.widget  // Include widget data for download button
                                }
                            }
                            : msg
                    ),
                    currentConversationId: response.conversation_id,
                    isLoading: false,
                    statusText: '',
                    processingConversationId: null  // Clear processing state
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
        // Prioritize processing conversation, then current conversation
        const targetId = state.processingConversationId ?? state.currentConversationId;
        if (targetId !== null && state.stageDataByConversation[targetId]) {
            return state.stageDataByConversation[targetId];
        }
        return [];
    },
}));

export default useChatStore;
