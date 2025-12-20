'use client';

import { useState, useRef, useCallback } from 'react';
import { documentsApi, type DocumentUploadResponse } from '@/lib/api/documents';
import { ApiClientError } from '@/lib/api';

interface DocumentUploaderProps {
  channelId: string;
  onUploadComplete: () => void;
}

type ErrorType = 'validation' | 'network' | 'upload' | 'processing' | 'timeout' | 'unknown';

interface UploadError {
  type: ErrorType;
  message: string;
  retryable: boolean;
}

interface UploadingFile {
  id: string;
  file: File;
  progress: number;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: UploadError;
}

function getErrorDetails(error: unknown, stage: 'upload' | 'processing'): UploadError {
  // Network error (fetch failed)
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      type: 'network',
      message: 'Network error. Please check your connection.',
      retryable: true,
    };
  }

  // API error with status code
  if (error instanceof ApiClientError) {
    if (error.status === 413) {
      return {
        type: 'validation',
        message: 'File too large for server.',
        retryable: false,
      };
    }
    if (error.status === 415) {
      return {
        type: 'validation',
        message: 'Unsupported file format.',
        retryable: false,
      };
    }
    if (error.status >= 500) {
      return {
        type: stage,
        message: `Server error during ${stage}. Please try again.`,
        retryable: true,
      };
    }
    if (error.status === 401 || error.status === 403) {
      return {
        type: stage,
        message: 'Authentication error. Please refresh the page.',
        retryable: false,
      };
    }
    return {
      type: stage,
      message: error.detail || `Failed during ${stage}.`,
      retryable: error.status >= 500,
    };
  }

  // Generic error
  if (error instanceof Error) {
    return {
      type: stage === 'upload' ? 'upload' : 'processing',
      message: error.message,
      retryable: true,
    };
  }

  return {
    type: 'unknown',
    message: `Unknown error during ${stage}.`,
    retryable: true,
  };
}

const SUPPORTED_FORMATS = [
  'PDF (.pdf)',
  'Text (.txt)',
  'Markdown (.md)',
  'Word (.docx)',
];

const ACCEPTED_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export default function DocumentUploader({ channelId, onUploadComplete }: DocumentUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [urlInput, setUrlInput] = useState('');
  const [isUrlMode, setIsUrlMode] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [isUrlUploading, setIsUrlUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const generateId = () => Math.random().toString(36).substring(7);

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE) {
      return `File too large (max ${MAX_FILE_SIZE / 1024 / 1024}MB)`;
    }
    // Allow any file type for now, backend will validate
    return null;
  };

  const uploadFile = async (file: File, existingId?: string) => {
    const id = existingId || generateId();
    const uploadingFile: UploadingFile = {
      id,
      file,
      progress: 0,
      status: 'uploading',
    };

    // Step 1: Client-side validation
    const validationError = validateFile(file);
    if (validationError) {
      const error: UploadError = {
        type: 'validation',
        message: validationError,
        retryable: false,
      };
      if (existingId) {
        setUploadingFiles(prev => prev.map(f =>
          f.id === id ? { ...f, status: 'failed', error } : f
        ));
      } else {
        setUploadingFiles(prev => [...prev, { ...uploadingFile, status: 'failed', error }]);
      }
      return;
    }

    // Add or update file in list
    if (existingId) {
      setUploadingFiles(prev => prev.map(f =>
        f.id === id ? { ...f, status: 'uploading', progress: 0, error: undefined } : f
      ));
    } else {
      setUploadingFiles(prev => [...prev, uploadingFile]);
    }

    // Step 2: Upload file to server
    let response: DocumentUploadResponse;
    try {
      setUploadingFiles(prev =>
        prev.map(f => (f.id === id ? { ...f, progress: 30 } : f))
      );

      response = await documentsApi.upload(channelId, file);
    } catch (err) {
      const error = getErrorDetails(err, 'upload');
      setUploadingFiles(prev =>
        prev.map(f => (f.id === id ? { ...f, status: 'failed', error } : f))
      );
      return;
    }

    // Step 3: Poll for processing status
    setUploadingFiles(prev =>
      prev.map(f => (f.id === id ? { ...f, progress: 70, status: 'processing' } : f))
    );

    let attempts = 0;
    const maxAttempts = 30;
    let lastStatusError: unknown = null;

    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000));

      try {
        const status = await documentsApi.getStatus(response.id);

        if (status.done) {
          setUploadingFiles(prev =>
            prev.map(f => (f.id === id ? { ...f, progress: 100, status: 'completed' } : f))
          );
          onUploadComplete();

          setTimeout(() => {
            setUploadingFiles(prev => prev.filter(f => f.id !== id));
          }, 2000);

          return;
        }

        if (status.error) {
          const error: UploadError = {
            type: 'processing',
            message: status.error,
            retryable: false,
          };
          setUploadingFiles(prev =>
            prev.map(f => (f.id === id ? { ...f, status: 'failed', error } : f))
          );
          return;
        }

        lastStatusError = null;
      } catch (err) {
        lastStatusError = err;
        // Continue polling on transient status check errors
      }

      attempts++;
      setUploadingFiles(prev =>
        prev.map(f => (f.id === id ? { ...f, progress: 70 + (attempts / maxAttempts) * 25 } : f))
      );
    }

    // Handle timeout
    if (lastStatusError) {
      const error: UploadError = {
        type: 'timeout',
        message: 'Processing is taking too long. The file may still be processing.',
        retryable: false,
      };
      setUploadingFiles(prev =>
        prev.map(f => (f.id === id ? { ...f, status: 'failed', error } : f))
      );
    } else {
      // Assume completed if no errors
      setUploadingFiles(prev =>
        prev.map(f => (f.id === id ? { ...f, progress: 100, status: 'completed' } : f))
      );
      onUploadComplete();

      setTimeout(() => {
        setUploadingFiles(prev => prev.filter(f => f.id !== id));
      }, 2000);
    }
  };

  const retryUpload = (uploadingFile: UploadingFile) => {
    uploadFile(uploadingFile.file, uploadingFile.id);
  };

  const handleFiles = (files: FileList | File[]) => {
    Array.from(files).forEach((file) => uploadFile(file));
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
      // Reset input
      e.target.value = '';
    }
  };

  const handleUrlUpload = async () => {
    if (!urlInput.trim()) {
      setUrlError('Please enter a URL');
      return;
    }

    try {
      new URL(urlInput);
    } catch {
      setUrlError('Please enter a valid URL');
      return;
    }

    setIsUrlUploading(true);
    setUrlError(null);

    try {
      await documentsApi.uploadFromUrl(channelId, urlInput);
      setUrlInput('');
      setIsUrlMode(false);
      onUploadComplete();
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : 'Failed to fetch URL');
    } finally {
      setIsUrlUploading(false);
    }
  };

  const removeFailedFile = (id: string) => {
    setUploadingFiles(prev => prev.filter(f => f.id !== id));
  };

  return (
    <div className="space-y-4">
      {/* Upload Mode Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setIsUrlMode(false)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
            !isUrlMode
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          File Upload
        </button>
        <button
          onClick={() => setIsUrlMode(true)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
            isUrlMode
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
          }`}
        >
          URL
        </button>
      </div>

      {!isUrlMode ? (
        <>
          {/* Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                : 'border-gray-200 dark:border-gray-800 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-900'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleFileSelect}
              className="hidden"
              accept={ACCEPTED_TYPES.join(',')}
            />

            <div className="flex flex-col items-center gap-3">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                isDragging
                  ? 'bg-blue-100 dark:bg-blue-900/40'
                  : 'bg-gray-100 dark:bg-gray-800'
              }`}>
                <svg
                  className={`w-6 h-6 ${
                    isDragging
                      ? 'text-blue-600 dark:text-blue-400'
                      : 'text-gray-500 dark:text-gray-400'
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {isDragging ? 'Drop files here' : 'Drag & drop files here'}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  or click to browse
                </p>
              </div>

              <div className="text-xs text-gray-400 dark:text-gray-500">
                Supported: {SUPPORTED_FORMATS.join(', ')}
              </div>
            </div>
          </div>
        </>
      ) : (
        /* URL Input */
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => {
                setUrlInput(e.target.value);
                setUrlError(null);
              }}
              placeholder="https://example.com/document"
              className="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-800 rounded-md bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
            <button
              onClick={handleUrlUpload}
              disabled={isUrlUploading}
              className="px-4 py-2 bg-blue-600 text-sm text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isUrlUploading && (
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              )}
              Fetch
            </button>
          </div>
          {urlError && (
            <p className="text-sm text-red-600 dark:text-red-400">{urlError}</p>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Enter a URL to fetch and add as a document
          </p>
        </div>
      )}

      {/* Upload Progress List */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          {uploadingFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-900 rounded-md border border-gray-200 dark:border-gray-800"
            >
              <div className="flex-shrink-0">
                {file.status === 'failed' ? (
                  <div className="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                    <svg className="w-4 h-4 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                ) : file.status === 'completed' ? (
                  <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <svg className="w-4 h-4 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                ) : (
                  <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <svg className="animate-spin w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  </div>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                  {file.file.name}
                </p>
                {file.status === 'failed' ? (
                  <p className="text-xs text-red-600 dark:text-red-400">{file.error?.message}</p>
                ) : (
                  <div className="mt-1">
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-300 ${
                          file.status === 'completed'
                            ? 'bg-green-500'
                            : 'bg-blue-500'
                        }`}
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {file.status === 'uploading' && 'Uploading...'}
                      {file.status === 'processing' && 'Processing...'}
                      {file.status === 'completed' && 'Completed'}
                    </p>
                  </div>
                )}
              </div>

              {file.status === 'failed' && (
                <div className="flex items-center gap-1">
                  {file.error?.retryable && (
                    <button
                      onClick={() => retryUpload(file)}
                      className="p-1.5 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded transition-colors"
                      title="Retry upload"
                    >
                      <svg className="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </button>
                  )}
                  <button
                    onClick={() => removeFailedFile(file.id)}
                    className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
                    title="Remove"
                  >
                    <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
