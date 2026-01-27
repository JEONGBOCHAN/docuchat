'use client';

import { useState } from 'react';
import type { ChatSource } from '@/lib/api/chat';

interface SourceCitationProps {
  sources: ChatSource[];
}

/**
 * Document icon for file sources
 */
function DocumentIcon() {
  return (
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
  );
}

/**
 * Globe icon for web sources
 */
function WebIcon() {
  return (
    <svg
      className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
      />
    </svg>
  );
}

/**
 * Academic/paper icon for arxiv sources
 */
function ArxivIcon() {
  return (
    <svg
      className="w-4 h-4 text-purple-600 dark:text-purple-400 flex-shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
      />
    </svg>
  );
}

/**
 * External link icon
 */
function ExternalLinkIcon() {
  return (
    <svg
      className="w-3 h-3 ml-1 inline-block"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  );
}

/**
 * Get icon component based on source type
 */
function getSourceIcon(sourceType?: string) {
  switch (sourceType) {
    case 'web':
      return <WebIcon />;
    case 'arxiv':
      return <ArxivIcon />;
    default:
      return <DocumentIcon />;
  }
}

/**
 * Get source type label for display
 */
function getSourceTypeLabel(sourceType?: string): string {
  switch (sourceType) {
    case 'web':
      return 'Web';
    case 'arxiv':
      return 'arXiv';
    default:
      return 'Document';
  }
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
              <div className="flex items-center gap-2 min-w-0 flex-1">
                {getSourceIcon(source.source_type)}
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300 truncate">
                    {source.source}
                  </span>
                  {source.source_type && source.source_type !== 'document' && (
                    <span className="text-[10px] text-gray-400 dark:text-gray-500">
                      {getSourceTypeLabel(source.source_type)}
                    </span>
                  )}
                </div>
              </div>
              <svg
                className={`w-4 h-4 text-gray-400 transition-transform flex-shrink-0 ${
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
              <div className="px-3 pb-3 space-y-2">
                {source.content && (
                  <p className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                    {source.content}
                  </p>
                )}
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {source.source_type === 'arxiv' ? 'View PDF' : 'Visit Website'}
                    <ExternalLinkIcon />
                  </a>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
