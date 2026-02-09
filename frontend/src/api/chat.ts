import client from './client';
import type { ChatRequest, ChatResponse, Conversation, Message } from '../types';

export const chatApi = {
    send: async (data: ChatRequest): Promise<ChatResponse> => {
        const response = await client.post<ChatResponse>('/chat', data);
        return response.data;
    },

    sendSimple: async (message: string): Promise<{ response: string }> => {
        const response = await client.post<{ response: string }>('/chat/simple', { message });
        return response.data;
    },

    getConversations: async (): Promise<Conversation[]> => {
        const response = await client.get<Conversation[]>('/conversations');
        return response.data;
    },

    getConversation: async (conversationId: number): Promise<{ conversation_id: number; messages: Message[] }> => {
        const response = await client.get<{ conversation_id: number; messages: Message[] }>(
            `/conversations/${conversationId}`
        );
        return response.data;
    },

    getMessages: async (conversationId: number): Promise<{ messages: Message[] }> => {
        const response = await client.get<{ messages: Message[] }>(
            `/conversations/${conversationId}/messages`
        );
        return response.data;
    },

    deleteConversation: async (conversationId: number): Promise<{ message: string }> => {
        const response = await client.delete<{ message: string }>(`/conversations/${conversationId}`);
        return response.data;
    },
};

export default chatApi;
