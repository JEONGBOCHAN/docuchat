'use client';

import { useState } from 'react';
import type { ChatSource } from '@/lib/api/chat';

interface SourceCitationProps {
  sources: ChatSource[];
}

export default function SourceCitation({ sources }: SourceCitationProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
        Sources ({sources.length})
      </p>
      <div className="space-y-2">
        {sources.map((source, index) => (
          <div
            key={index}
            className="bg-gray-50 dark:bg-gray-800 rounded-md border border-gray-100 dark:border-gray-700"
          >
            <button
              onClick={() => setExpandedIndex(expandedIndex === index ? null : index)}
              className="w-full px-3 py-2 flex items-center justify-between text-left"
            >
              <div className="flex items-center gap-2 min-w-0">
                <svg
                  className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
                  {source.source}
                </span>
              </div>
              <svg
                className={`w-4 h-4 text-gray-400 transition-transform ${
                  expandedIndex === index ? 'rotate-180' : ''
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
            {expandedIndex === index && (
              <div className="px-3 pb-3">
                <p className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                  {source.content}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
