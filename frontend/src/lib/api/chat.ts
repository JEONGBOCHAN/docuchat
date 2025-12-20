import apiClient, { API_BASE_URL } from './client';
import type { ChatSource } from './types';

export type { ChatSource };

export interface ChatResponse {
  response: string;
  sources: ChatSource[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  created_at?: string;
}

export interface SummarizeRequest {
  summary_type: 'short' | 'detailed';
}

export interface SummarizeResponse {
  channel_id: string;
  document_id?: string;
  summary_type: 'short' | 'detailed';
  summary: string;
  generated_at: string;
}

export interface StreamCallbacks {
  onChunk: (chunk: string) => void;
  onSources?: (sources: ChatSource[]) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export const chatApi = {
  sendMessage: (channelId: string, message: string) => {
    return apiClient.post<ChatResponse>(`/api/v1/channels/${channelId}/chat`, {
      message,
    });
  },

  streamMessage: async (
    channelId: string,
    message: string,
    callbacks: StreamCallbacks
  ): Promise<void> => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/channels/${channelId}/chat/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              callbacks.onComplete?.();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.chunk) {
                callbacks.onChunk(parsed.chunk);
              }
              if (parsed.sources) {
                callbacks.onSources?.(parsed.sources);
              }
            } catch {
              // If not JSON, treat as raw chunk
              callbacks.onChunk(data);
            }
          }
        }
      }

      callbacks.onComplete?.();
    } catch (error) {
      callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  },

  getHistory: (channelId: string, limit?: number) => {
    const params = limit ? `?limit=${limit}` : '';
    return apiClient.get<{ messages: ChatMessage[] }>(
      `/api/v1/channels/${channelId}/chat/history${params}`
    );
  },

  clearHistory: (channelId: string) => {
    return apiClient.delete<void>(`/api/v1/channels/${channelId}/chat/history`);
  },

  summarizeChannel: (channelId: string, summaryType: 'short' | 'detailed' = 'short') => {
    return apiClient.post<SummarizeResponse>(`/api/v1/channels/${channelId}/summarize`, {
      summary_type: summaryType,
    });
  },

  summarizeDocument: (
    channelId: string,
    documentId: string,
    summaryType: 'short' | 'detailed' = 'short'
  ) => {
    return apiClient.post<SummarizeResponse>(
      `/api/v1/channels/${channelId}/documents/${documentId}/summarize`,
      { summary_type: summaryType }
    );
  },
};

export default chatApi;
