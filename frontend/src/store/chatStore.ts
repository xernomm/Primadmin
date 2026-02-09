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
    stageData: StageData[];  // For processing block display

    initSocket: () => void;
    disconnectSocket: () => void;
    sendMessage: (content: string, conversationId?: number) => Promise<void>;
    loadConversation: (conversationId: number) => Promise<void>;
    loadConversations: () => Promise<void>;
    deleteConversation: (conversationId: number) => Promise<void>;
    createNewConversation: () => void;
    clearError: () => void;
    clearStageData: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
    messages: [],
    conversations: [],
    currentConversationId: null,
    isLoading: false,
    error: null,
    statusText: '',
    socket: null,
    stageData: [],

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

        // Handle stage_complete events for processing block
        socket.on('stage_complete', (data: StageData) => {
            console.log('[Socket] Stage complete:', data);
            set((state) => ({
                stageData: [...state.stageData, data]
            }));
        });

        socket.on('error', (data: { message: string }) => {
            set({ error: data.message, isLoading: false, stageData: [] });
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

        set({ isLoading: true, error: null, statusText: 'Memproses...', stageData: [] });

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
                    stageData: []  // Clear stage data after response complete
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

    clearStageData: () => set({ stageData: [] }),
}));

export default useChatStore;
