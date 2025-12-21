'use client';

import { useState, useEffect, useCallback } from 'react';
import { documentsApi, type Document } from '@/lib/api/documents';
import DocumentItem from './DocumentItem';
import DeleteDocumentModal from './DeleteDocumentModal';

interface DocumentListProps {
  channelId: string;
  refreshTrigger?: number;
}

export default function DocumentList({ channelId, refreshTrigger }: DocumentListProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDocument, setDeleteDocument] = useState<Document | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      setError(null);
      const response = await documentsApi.list(channelId);
      setDocuments(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  }, [channelId]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments, refreshTrigger]);

  const handleDeleteDocument = async () => {
    if (!deleteDocument) return;
    await documentsApi.delete(deleteDocument.id);
    await fetchDocuments();
    setDeleteDocument(null);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="flex flex-col items-center gap-2">
          <svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading documents...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-3">
          <svg className="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
          Failed to load documents
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">{error}</p>
        <button
          onClick={() => {
            setIsLoading(true);
            fetchDocuments();
          }}
          className="px-3 py-1.5 text-xs border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          Try again
        </button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="w-12 h-12 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mb-3">
          <svg className="w-6 h-6 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
          No documents yet
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Upload documents to start chatting with AI
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Documents ({documents.length})
          </h3>
        </div>
        {documents.map((doc) => (
          <DocumentItem
            key={doc.id}
            document={doc}
            onDelete={setDeleteDocument}
          />
        ))}
      </div>

      <DeleteDocumentModal
        isOpen={!!deleteDocument}
        document={deleteDocument}
        onClose={() => setDeleteDocument(null)}
        onConfirm={handleDeleteDocument}
      />
    </>
  );
}
