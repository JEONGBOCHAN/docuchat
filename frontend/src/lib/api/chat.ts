import apiClient, { API_BASE_URL } from './client';
import type { ChatSource } from './types';

export type { ChatSource };

export interface ChatResponse {
  response: string;
  sources: ChatSource[];
}

export interface ChatMessage {
  id: string;
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

export interface StreamOptions {
  timeout?: number; // Timeout in milliseconds (default: 60000)
  signal?: AbortSignal; // External abort signal
}

export interface StreamController {
  abort: () => void;
  signal: AbortSignal;
}

export const chatApi = {
  sendMessage: (channelId: string, message: string) => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.post<ChatResponse>(`/api/v1/channels/${encodeURIComponent(decodedId)}/chat`, {
      query: message,
    });
  },

  streamMessage: (
    channelId: string,
    message: string,
    callbacks: StreamCallbacks,
    options: StreamOptions = {}
  ): StreamController => {
    const { timeout = 60000 } = options;

    // Create internal AbortController
    const abortController = new AbortController();

    // Link external signal if provided
    if (options.signal) {
      options.signal.addEventListener('abort', () => {
        abortController.abort();
      });
    }

    // Timeout handling
    let timeoutId: NodeJS.Timeout | null = null;
    let lastActivityTime = Date.now();

    const resetTimeout = () => {
      lastActivityTime = Date.now();
    };

    const checkTimeout = () => {
      if (Date.now() - lastActivityTime > timeout) {
        abortController.abort();
        callbacks.onError?.(new Error('Stream timeout: No response received'));
        return true;
      }
      return false;
    };

    // Start streaming
    const startStream = async () => {
      // Set up periodic timeout check
      timeoutId = setInterval(() => {
        if (checkTimeout()) {
          if (timeoutId) clearInterval(timeoutId);
        }
      }, 5000);

      try {
        const decodedId = decodeURIComponent(channelId);
        const response = await fetch(
          `${API_BASE_URL}/api/v1/channels/${encodeURIComponent(decodedId)}/chat/stream`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: message }),
            signal: abortController.signal,
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

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // Reset timeout on each chunk
            resetTimeout();

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
        } finally {
          // Ensure reader is released
          reader.releaseLock();
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          // Check if it was a timeout or manual cancel
          if (Date.now() - lastActivityTime > timeout) {
            callbacks.onError?.(new Error('Stream timeout: No response received'));
          } else {
            callbacks.onError?.(new Error('Stream cancelled'));
          }
        } else {
          callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
        }
      } finally {
        if (timeoutId) clearInterval(timeoutId);
      }
    };

    // Start the stream
    startStream();

    // Return controller for external cancellation
    return {
      abort: () => abortController.abort(),
      signal: abortController.signal,
    };
  },

  getHistory: (channelId: string, limit?: number) => {
    const decodedId = decodeURIComponent(channelId);
    const params = limit ? `?limit=${limit}` : '';
    return apiClient.get<{ messages: ChatMessage[] }>(
      `/api/v1/channels/${encodeURIComponent(decodedId)}/chat/history${params}`
    );
  },

  clearHistory: (channelId: string) => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.delete<void>(`/api/v1/channels/${encodeURIComponent(decodedId)}/chat/history`);
  },

  summarizeChannel: (channelId: string, summaryType: 'short' | 'detailed' = 'short') => {
    const decodedId = decodeURIComponent(channelId);
    return apiClient.post<SummarizeResponse>(`/api/v1/channels/${encodeURIComponent(decodedId)}/summarize`, {
      summary_type: summaryType,
    });
  },

  summarizeDocument: (
    channelId: string,
    documentId: string,
    summaryType: 'short' | 'detailed' = 'short'
  ) => {
    const decodedChannelId = decodeURIComponent(channelId);
    const decodedDocId = decodeURIComponent(documentId);
    return apiClient.post<SummarizeResponse>(
      `/api/v1/channels/${encodeURIComponent(decodedChannelId)}/documents/${encodeURIComponent(decodedDocId)}/summarize`,
      { summary_type: summaryType }
    );
  },
};

export default chatApi;
