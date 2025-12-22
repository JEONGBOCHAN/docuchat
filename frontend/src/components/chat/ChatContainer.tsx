'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { chatApi, type ChatMessage as ChatMessageType, type ChatSource, type StreamController } from '@/lib/api/chat';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';

// Generate unique message ID
let messageIdCounter = 0;
const generateMessageId = () => `msg_${Date.now()}_${++messageIdCounter}`;

interface ChatContainerProps {
  channelId: string;
  onSaveAsNote?: (content: string, sources: ChatSource[]) => void;
}

export default function ChatContainer({ channelId, onSaveAsNote }: ChatContainerProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingSources, setStreamingSources] = useState<ChatSource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamingContentRef = useRef('');
  const streamingSourcesRef = useRef<ChatSource[]>([]);
  const streamControllerRef = useRef<StreamController | null>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, scrollToBottom]);

  const fetchHistory = useCallback(async () => {
    try {
      setError(null);
      const response = await chatApi.getHistory(channelId);
      // Add IDs to messages from backend if they don't have one
      const messagesWithIds = (response.messages || []).map((msg) => ({
        ...msg,
        id: msg.id || generateMessageId(),
      }));
      setMessages(messagesWithIds);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chat history');
    } finally {
      setIsLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleSendMessage = (content: string) => {
    // Add user message immediately
    const userMessage: ChatMessageType = {
      id: generateMessageId(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setStreamingContent('');
    setStreamingSources([]);
    streamingContentRef.current = '';
    streamingSourcesRef.current = [];
    setError(null);

    // Start streaming and save controller for cancellation
    streamControllerRef.current = chatApi.streamMessage(
      channelId,
      content,
      {
        onChunk: (chunk) => {
          streamingContentRef.current += chunk;
          setStreamingContent(streamingContentRef.current);
        },
        onSources: (sources) => {
          streamingSourcesRef.current = sources;
          setStreamingSources(sources);
        },
        onError: (err) => {
          console.error('Streaming error:', err.message);
          setError(err.message);
          setIsStreaming(false);
          streamControllerRef.current = null;
          // Fetch history in case the backend saved a partial response
          fetchHistory();
        },
        onComplete: () => {
          // Capture values before resetting to avoid race conditions
          const finalContent = streamingContentRef.current;
          const finalSources = [...streamingSourcesRef.current];

          // Add the complete AI message
          if (finalContent) {
            setMessages((prev) => [
              ...prev,
              {
                id: generateMessageId(),
                role: 'assistant',
                content: finalContent,
                sources: finalSources,
                created_at: new Date().toISOString(),
              },
            ]);
          } else {
            // Fallback: if streaming completed but no content captured,
            // refresh history to get the saved message from backend
            console.warn('Streaming completed with empty content, fetching history...');
            fetchHistory();
          }
          setIsStreaming(false);
          setStreamingContent('');
          setStreamingSources([]);
          streamingContentRef.current = '';
          streamingSourcesRef.current = [];
          streamControllerRef.current = null;
        },
      },
      { timeout: 60000 } // 60 second timeout
    );
  };

  const handleCancelStream = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort();
      streamControllerRef.current = null;

      // Save partial content if any
      if (streamingContentRef.current) {
        setMessages((prev) => [
          ...prev,
          {
            id: generateMessageId(),
            role: 'assistant',
            content: streamingContentRef.current + '\n\n*[Response cancelled]*',
            sources: streamingSourcesRef.current,
            created_at: new Date().toISOString(),
          },
        ]);
      }

      setIsStreaming(false);
      setStreamingContent('');
      setStreamingSources([]);
      streamingContentRef.current = '';
      streamingSourcesRef.current = [];
    }
  };

  const handleClearHistory = async () => {
    if (!confirm('Are you sure you want to clear chat history?')) return;

    try {
      await chatApi.clearHistory(channelId);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear history');
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg
            className="animate-spin h-8 w-8 text-blue-600"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading chat...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Chat</h3>
        {messages.length > 0 && (
          <button
            onClick={handleClearHistory}
            className="text-xs text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
          >
            Clear history
          </button>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4">
        {error && (
          <div className="my-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {messages.length === 0 && !isStreaming ? (
          <div className="flex flex-col items-center justify-center h-full py-12">
            <div className="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-gray-400 dark:text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Start a conversation
            </h4>
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-sm">
              Ask questions about your documents and get AI-powered answers with citations.
            </p>
          </div>
        ) : (
          <div className="py-4">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                onSaveAsNote={onSaveAsNote}
              />
            ))}

            {/* Streaming message */}
            {isStreaming && streamingContent && (
              <ChatMessage
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingContent,
                  sources: streamingSources,
                }}
                onSaveAsNote={onSaveAsNote}
              />
            )}

            {/* Typing indicator when waiting for first chunk */}
            {isStreaming && !streamingContent && <TypingIndicator />}

            {/* Cancel button during streaming */}
            {isStreaming && (
              <div className="flex justify-center my-4">
                <button
                  onClick={handleCancelStream}
                  className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors flex items-center gap-2"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                  Stop generating
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <ChatInput onSend={handleSendMessage} disabled={isStreaming} />
    </div>
  );
}
